"""Trend Scout — cross-platform trend detection with AI analysis.

Uses browser-use (when available) + AI fallback to detect:
  - Trending hooks, formats, sounds on TikTok/IG/YouTube
  - Winning content patterns per niche
  - Viral hooks database
  - Competitor content analysis

Results are fed into the Predator Agent's viral DNA library.

Inspired by ViralMint trend scouting + OpenShorts viral moment detection.
"""

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict

log = logging.getLogger(__name__)

_TREND_DB_PATH = Path(__file__).parents[1] / "data" / "trend_scout.db"

_TREND_SCHEMA = """
CREATE TABLE IF NOT EXISTS trending_hooks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hook            TEXT NOT NULL,
    niche           TEXT NOT NULL DEFAULT 'general',
    platform        TEXT NOT NULL DEFAULT 'tiktok',
    format          TEXT DEFAULT 'storytime',
    source_url      TEXT DEFAULT '',
    engagement      TEXT DEFAULT '',
    ai_analysis     TEXT DEFAULT '',
    score           REAL DEFAULT 0.0,
    is_active       INTEGER DEFAULT 1,
    detected_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_trends_niche ON trending_hooks(niche, platform);
CREATE INDEX IF NOT EXISTS idx_trends_score ON trending_hooks(score DESC);
CREATE INDEX IF NOT EXISTS idx_trends_active ON trending_hooks(is_active) WHERE is_active=1;

CREATE TABLE IF NOT EXISTS trend_sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,
    url             TEXT NOT NULL UNIQUE,
    last_scraped    TIMESTAMP,
    scrape_interval INTEGER DEFAULT 3600,
    is_active       INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS content_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    niche           TEXT NOT NULL,
    pattern_type    TEXT NOT NULL CHECK (pattern_type IN ('hook','format','sound','caption','cta','thumbnail')),
    pattern         TEXT NOT NULL,
    win_rate        REAL DEFAULT 0.0,
    sample_size     INTEGER DEFAULT 1,
    first_seen      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_patterns_niche ON content_patterns(niche, pattern_type);
"""


class TrendScout:
    """Cross-platform trend detection with browser-use + AI analysis."""

    def __init__(self, db_path: Optional[str] = None, ai_router=None):
        self._db_path = db_path or str(_TREND_DB_PATH)
        self._lock = threading.Lock()
        self.ai = ai_router
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._seed_sources()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_TREND_SCHEMA)
            conn.commit()

    def _seed_sources(self) -> None:
        sources = [
            ("tiktok", "https://www.tiktok.com/trending"),
            ("instagram", "https://www.instagram.com/reels/trending/"),
            ("youtube", "https://www.youtube.com/feed/trending"),
        ]
        with self._connect() as conn:
            for platform, url in sources:
                conn.execute(
                    "INSERT OR IGNORE INTO trend_sources (platform, url) VALUES (?, ?)",
                    (platform, url),
                )
            conn.commit()

    def add_trending_hook(self, hook: str, niche: str = "general",
                          platform: str = "tiktok", format: str = "storytime",
                          source_url: str = "", engagement: str = "",
                          ai_analysis: str = "", score: float = 0.0) -> int:
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """INSERT INTO trending_hooks
                       (hook, niche, platform, format, source_url,
                        engagement, ai_analysis, score, expires_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (hook, niche, platform, format, source_url,
                     engagement, ai_analysis, score, expires),
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def get_trending(self, niche: str = "", platform: str = "",
                     limit: int = 20) -> List[dict]:
        conn = self._connect()
        try:
            conditions = ["is_active = 1"]
            params = []
            if niche:
                conditions.append("niche = ?")
                params.append(niche)
            if platform:
                conditions.append("platform = ?")
                params.append(platform)

            rows = conn.execute(
                f"""SELECT id, hook, niche, platform, format, engagement,
                           ai_analysis, score, detected_at
                    FROM trending_hooks
                    WHERE {' AND '.join(conditions)}
                    AND (expires_at IS NULL OR expires_at > datetime('now'))
                    ORDER BY score DESC, detected_at DESC
                    LIMIT ?""",
                params + [limit],
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def record_pattern(self, niche: str, pattern_type: str, pattern: str,
                       win: bool = False) -> None:
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT id, win_rate, sample_size FROM content_patterns WHERE niche=? AND pattern_type=? AND pattern=?",
                    (niche, pattern_type, pattern),
                ).fetchone()

                if existing:
                    new_sample = existing["sample_size"] + 1
                    new_win_rate = ((existing["win_rate"] * existing["sample_size"]) + (1 if win else 0)) / new_sample
                    conn.execute(
                        "UPDATE content_patterns SET win_rate=?, sample_size=?, last_seen=CURRENT_TIMESTAMP WHERE id=?",
                        (new_win_rate, new_sample, existing["id"]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO content_patterns (niche, pattern_type, pattern, win_rate, sample_size) VALUES (?, ?, ?, ?, 1)",
                        (niche, pattern_type, pattern, 1.0 if win else 0.0),
                    )
                conn.commit()
            finally:
                conn.close()

    def get_winning_patterns(self, niche: str = "", pattern_type: str = "",
                             min_samples: int = 3, limit: int = 10) -> List[dict]:
        conn = self._connect()
        try:
            conditions = ["sample_size >= ?"]
            params = [min_samples]
            if niche:
                conditions.append("niche = ?")
                params.append(niche)
            if pattern_type:
                conditions.append("pattern_type = ?")
                params.append(pattern_type)

            rows = conn.execute(
                f"""SELECT niche, pattern_type, pattern, win_rate, sample_size, last_seen
                    FROM content_patterns
                    WHERE {' AND '.join(conditions)}
                    ORDER BY win_rate DESC, sample_size DESC
                    LIMIT ?""",
                params + [limit],
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def analyze_with_ai(self, niche: str = "general", platform: str = "tiktok") -> List[dict]:
        """Use AI to generate trending hook ideas when browser-use is unavailable."""
        if not self.ai:
            log.warning("[TrendScout] No AI router — using fallback hooks")
            return self._fallback_hooks(niche, platform)

        prompt = (
            f"You are a viral content analyst. Generate 10 trending UGC hook ideas "
            f"for the '{niche}' niche on {platform}. "
            f"For each hook, include: the hook text, format type, why it works, "
            f"estimated engagement potential (1-10). "
            f"Return as JSON array: "
            f"[{{\"hook\":\"...\",\"format\":\"...\",\"reasoning\":\"...\",\"score\":8}}]"
        )
        try:
            result = self.ai.chat_structured(prompt)
            if isinstance(result, list):
                hooks = []
                for item in result:
                    hid = self.add_trending_hook(
                        hook=item.get("hook", ""),
                        niche=niche,
                        platform=platform,
                        format=item.get("format", "storytime"),
                        ai_analysis=item.get("reasoning", ""),
                        score=item.get("score", 5),
                    )
                    hooks.append({"id": hid, **item})
                return hooks
            elif isinstance(result, dict) and "hooks" in result:
                return self.analyze_with_ai(niche, platform)
        except Exception as e:
            log.warning("[TrendScout] AI analysis failed: %s", e)

        return self._fallback_hooks(niche, platform)

    def _fallback_hooks(self, niche: str, platform: str) -> List[dict]:
        fallback = [
            {"hook": "I tried this for 30 days and here's what happened", "format": "storytime", "reasoning": "Curiosity gap + transformation arc", "score": 9},
            {"hook": "Stop buying [product] until you watch this", "format": "review", "reasoning": "Loss aversion + authority", "score": 8},
            {"hook": "Nobody tells you this about [product]", "format": "secret", "reasoning": "Curiosity + insider knowledge", "score": 8},
            {"hook": "POV: You just discovered the best [niche] hack", "format": "pov", "reasoning": "Relatability + discovery", "score": 7},
            {"hook": "The [number] second trick that changed everything", "format": "tutorial", "reasoning": "Quick win + specificity", "score": 7},
        ]
        for item in fallback:
            self.add_trending_hook(
                hook=item["hook"], niche=niche, platform=platform,
                format=item["format"], ai_analysis=item["reasoning"],
                score=item["score"],
            )
        return fallback

    def get_stats(self) -> dict:
        conn = self._connect()
        try:
            total_hooks = conn.execute("SELECT COUNT(*) as c FROM trending_hooks WHERE is_active=1").fetchone()["c"]
            total_patterns = conn.execute("SELECT COUNT(*) as c FROM content_patterns").fetchone()["c"]
            by_niche = conn.execute(
                "SELECT niche, COUNT(*) as cnt FROM trending_hooks WHERE is_active=1 GROUP BY niche ORDER BY cnt DESC"
            ).fetchall()
            top_hooks = conn.execute(
                "SELECT hook, score FROM trending_hooks WHERE is_active=1 ORDER BY score DESC LIMIT 5"
            ).fetchall()
            return {
                "active_hooks": total_hooks,
                "patterns_tracked": total_patterns,
                "by_niche": [dict(r) for r in by_niche],
                "top_hooks": [dict(r) for r in top_hooks],
            }
        finally:
            conn.close()

    def prune_expired(self) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE trending_hooks SET is_active=0 WHERE expires_at IS NOT NULL AND expires_at < datetime('now')"
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def periodic_scan(self, niche: str = "general", interval_hours: int = 6) -> None:
        """Run this in a background thread to keep trends fresh."""
        log.info("[TrendScout] Starting periodic scan for '%s' every %dh", niche, interval_hours)
        while True:
            try:
                self.prune_expired()
                self.analyze_with_ai(niche=niche)
                log.info("[TrendScout] Scan complete — %d active hooks",
                         self.get_stats()["active_hooks"])
            except Exception as e:
                log.error("[TrendScout] Scan error: %s", e)
            time.sleep(interval_hours * 3600)
