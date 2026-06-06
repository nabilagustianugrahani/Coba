"""Trend detector — OpenFuego algorithm ported to Python.

Original OpenFuego (MIT, niemanlab):
  - Curate 15 "authority" accounts
  - Auto-follow their network
  - Rank shared URLs by freshness x quality
  - 24/7 collector + separate consumer

Our Python port:
  - Configurable per-niche authority accounts
  - Pluggable collectors: Twitter, Reddit, TikTok, RSS
  - Scoring: recency_decay x unique_sharers x engagement
  - Outputs to Notion Inbox + graph (Trend node)
  - APScheduler integration
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


DEFAULT_DB_PATH = Path.home() / ".9router" / "trends.db"


class TrendCategory(str, Enum):
    PRODUCT = "product"
    MEME = "meme"
    NEWS = "news"
    HASHTAG = "hashtag"
    SOUND = "sound"
    CHALLENGE = "challenge"


class SourcePlatform(str, Enum):
    TWITTER = "twitter"
    REDDIT = "reddit"
    TIKTOK = "tiktok"
    RSS = "rss"
    YOUTUBE = "youtube"


@dataclass
class AuthorityAccount:
    platform: str
    handle: str
    niche: str
    weight: float = 1.0
    followers: int = 0
    is_active: bool = True


@dataclass
class TrendSignal:
    signal_id: str
    url: str
    title: str
    category: str
    platform: str
    niche: str
    shared_by: list[str] = field(default_factory=list)
    engagement_count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    score: float = 0.0
    decay_rate: float = 0.05
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NicheAuthorityConfig:
    niche: str
    accounts: list[AuthorityAccount] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    decay_rate: float = 0.05
    min_unique_sharers: int = 2
    min_score: float = 1.0


NICHE_AUTHORITIES: dict[str, NicheAuthorityConfig] = {
    "beauty": NicheAuthorityConfig(
        niche="beauty",
        accounts=[
            AuthorityAccount("twitter", "sephora", "beauty", 0.9, 500000),
            AuthorityAccount("twitter", "allure", "beauty", 0.85, 200000),
            AuthorityAccount("tiktok", "mikaylanogueira", "beauty", 1.0, 15000000),
            AuthorityAccount("tiktok", "jamescharles", "beauty", 0.95, 22000000),
            AuthorityAccount("reddit", "r/SkincareAddiction", "beauty", 0.8, 1500000),
        ],
        keywords=["skincare", "makeup", "haul", "review", "tutorial", "swatches"],
        decay_rate=0.05,
    ),
    "tech": NicheAuthorityConfig(
        niche="tech",
        accounts=[
            AuthorityAccount("twitter", "MKBHD", "tech", 1.0, 6000000),
            AuthorityAccount("twitter", "verge", "tech", 0.9, 3000000),
            AuthorityAccount("youtube", "mkbhd", "tech", 1.0, 20000000),
            AuthorityAccount("reddit", "r/technology", "tech", 0.8, 14000000),
            AuthorityAccount("reddit", "r/gadgets", "tech", 0.85, 2000000),
        ],
        keywords=["review", "unboxing", "benchmark", "specs", "launch", "leak"],
        decay_rate=0.04,
    ),
    "fashion": NicheAuthorityConfig(
        niche="fashion",
        accounts=[
            AuthorityAccount("tiktok", "chloeszepanski", "fashion", 1.0, 8000000),
            AuthorityAccount("instagram", "fashionblogger", "fashion", 0.7, 1000000),
            AuthorityAccount("reddit", "r/streetwear", "fashion", 0.85, 1500000),
        ],
        keywords=["outfit", "lookbook", "fit", "haul", "thrifted", "ootd"],
        decay_rate=0.06,
    ),
    "food": NicheAuthorityConfig(
        niche="food",
        accounts=[
            AuthorityAccount("tiktok", "gaborbaross", "food", 0.95, 5000000),
            AuthorityAccount("tiktok", "joshuaweissman", "food", 1.0, 16000000),
            AuthorityAccount("reddit", "r/food", "food", 0.9, 22000000),
        ],
        keywords=["recipe", "taste test", "viral", "review", "homemade"],
        decay_rate=0.07,
    ),
}


class TrendDetector:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        import os
        env_path = os.environ.get("UGC_TREND_DB", "")
        self.path = db_path or (Path(env_path) if env_path else DEFAULT_DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.configs: dict[str, NicheAuthorityConfig] = NICHE_AUTHORITIES.copy()
        self._init_db()

    @contextmanager
    def _conn(self) -> Any:
        conn = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    niche TEXT NOT NULL,
                    shared_by TEXT NOT NULL,
                    engagement_count INTEGER NOT NULL DEFAULT 0,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    score REAL NOT NULL DEFAULT 0,
                    decay_rate REAL NOT NULL DEFAULT 0.05,
                    metadata TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_niche ON signals(niche)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_score ON signals(score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_first_seen ON signals(first_seen)")
            conn.commit()

    def add_niche_config(self, config: NicheAuthorityConfig) -> None:
        self.configs[config.niche] = config
        log.info("trend.add_niche %s accounts=%d", config.niche, len(config.accounts))

    def get_config(self, niche: str) -> NicheAuthorityConfig:
        if niche not in self.configs:
            self.configs[niche] = NicheAuthorityConfig(niche=niche)
        return self.configs[niche]

    def record_signal(
        self,
        url: str,
        title: str,
        category: str,
        platform: str,
        niche: str,
        shared_by: str,
        engagement_count: int = 0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TrendSignal:
        import hashlib
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]
        signal_id = f"{niche}_{platform}_{url_hash}"
        with self._lock:
            with self._conn() as conn:
                existing = conn.execute(
                    "SELECT signal_id, shared_by, first_seen, score, last_seen FROM signals WHERE signal_id=?",
                    (signal_id,),
                ).fetchone()
                now = datetime.now(timezone.utc).isoformat()
                if existing:
                    sharers = json.loads(existing["shared_by"])
                    if shared_by not in sharers:
                        sharers.append(shared_by)
                    last_seen = now
                    first_seen = existing["first_seen"]
                    cfg = self.get_config(niche)
                    new_score = self._compute_score(
                        sharers, last_seen, first_seen, engagement_count, cfg
                    )
                    conn.execute(
                        "UPDATE signals SET shared_by=?, engagement_count=?, last_seen=?, score=? WHERE signal_id=?",
                        (json.dumps(sharers), engagement_count, last_seen, new_score, signal_id),
                    )
                else:
                    cfg = self.get_config(niche)
                    sharers = [shared_by]
                    score = self._compute_score(
                        sharers, now, now, engagement_count, cfg
                    )
                    conn.execute(
                        """INSERT INTO signals
                        (signal_id, url, title, category, platform, niche, shared_by,
                         engagement_count, first_seen, last_seen, score, decay_rate, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            signal_id, url, title, category, platform, niche,
                            json.dumps(sharers), engagement_count, now, now,
                            score, cfg.decay_rate, json.dumps(metadata or {}),
                        ),
                    )
                return self._load_signal(signal_id)

    def _compute_score(
        self,
        sharers: list[str],
        last_seen: str,
        first_seen: str,
        engagement: int,
        cfg: NicheAuthorityConfig,
    ) -> float:
        now = datetime.now(timezone.utc)
        try:
            last_dt = datetime.fromisoformat(last_seen)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
        except Exception:
            last_dt = now
        try:
            first_dt = datetime.fromisoformat(first_seen)
            if first_dt.tzinfo is None:
                first_dt = first_dt.replace(tzinfo=timezone.utc)
        except Exception:
            first_dt = now
        age_hours = max(0.0, (now - last_dt).total_seconds() / 3600.0)
        recency_factor = math.exp(-cfg.decay_rate * age_hours)
        unique_sharers = len(set(sharers))
        sharer_score = math.log1p(unique_sharers) * 2.0
        engagement_score = math.log1p(engagement) * 0.5
        velocity_bonus = 1.0
        if first_dt != last_dt:
            elapsed_h = max(0.1, (last_dt - first_dt).total_seconds() / 3600.0)
            velocity_bonus = math.log1p(unique_sharers / elapsed_h) * 0.5
        score = (recency_factor * 100) + (sharer_score * 5) + engagement_score + velocity_bonus
        return round(score, 4)

    def _load_signal(self, signal_id: str) -> TrendSignal:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM signals WHERE signal_id=?", (signal_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Signal {signal_id} not found")
            return TrendSignal(
                signal_id=row["signal_id"],
                url=row["url"],
                title=row["title"],
                category=row["category"],
                platform=row["platform"],
                niche=row["niche"],
                shared_by=json.loads(row["shared_by"]),
                engagement_count=row["engagement_count"],
                first_seen=row["first_seen"],
                last_seen=row["last_seen"],
                score=row["score"],
                decay_rate=row["decay_rate"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )

    def get_trending(
        self, niche: Optional[str] = None, category: Optional[str] = None,
        min_score: Optional[float] = None, hours: int = 48, limit: int = 20,
    ) -> list[TrendSignal]:
        with self._lock:
            sql = "SELECT signal_id FROM signals WHERE 1=1"
            params: list[Any] = []
            if niche:
                sql += " AND niche=?"
                params.append(niche)
            if category:
                sql += " AND category=?"
                params.append(category)
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            sql += " AND last_seen >= ?"
            params.append(cutoff)
            sql += " ORDER BY score DESC LIMIT ?"
            params.append(limit)
            out: list[TrendSignal] = []
            with self._conn() as conn:
                rows = conn.execute(sql, params).fetchall()
                for r in rows:
                    try:
                        sig = self._load_signal(r["signal_id"])
                        if min_score is None or sig.score >= min_score:
                            out.append(sig)
                    except Exception as e:
                        log.warning("Failed to load signal: %s", e)
            return out

    def decay_scores(self) -> int:
        count = 0
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute("SELECT signal_id, decay_rate FROM signals").fetchall()
                for r in rows:
                    sig = self._load_signal(r["signal_id"])
                    cfg = self.get_config(sig.niche)
                    new_score = self._compute_score(
                        sig.shared_by, sig.last_seen, sig.first_seen,
                        sig.engagement_count, cfg,
                    )
                    conn.execute(
                        "UPDATE signals SET score=? WHERE signal_id=?",
                        (new_score, sig.signal_id),
                    )
                    count += 1
        return count

    def stats(self) -> dict[str, Any]:
        with self._lock:
            with self._conn() as conn:
                total = conn.execute("SELECT COUNT(*) as c FROM signals").fetchone()["c"]
                by_niche = conn.execute(
                    "SELECT niche, COUNT(*) as c FROM signals GROUP BY niche"
                ).fetchall()
                by_category = conn.execute(
                    "SELECT category, COUNT(*) as c FROM signals GROUP BY category"
                ).fetchall()
        return {
            "total_signals": total,
            "by_niche": {r["niche"]: r["c"] for r in by_niche},
            "by_category": {r["category"]: r["c"] for r in by_category},
            "niches_configured": list(self.configs.keys()),
        }


__all__ = [
    "TrendSignal",
    "AuthorityAccount",
    "NicheAuthorityConfig",
    "TrendDetector",
    "TrendCategory",
    "SourcePlatform",
    "NICHE_AUTHORITIES",
    "DEFAULT_DB_PATH",
]
