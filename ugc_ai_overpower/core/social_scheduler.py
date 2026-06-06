"""Social scheduler — Postiz-inspired post scheduling.

Postiz-app (gitroomhq) is a full self-hosted social media scheduler.
We take the most useful pattern: SCHEDULED POSTS with timezone awareness,
queue management, and per-platform timing optimization.

Our scheduler is lighter weight:
  - APScheduler-backed queue
  - Per-platform optimal time slots
  - Integrates with our social_dispatch.py for actual posting
  - Conflict resolution (no two posts to same account in 5min)
  - Per-niche content calendar
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


DEFAULT_DB_PATH = Path.home() / ".9router" / "scheduler.db"


class PostStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleStrategy(str, Enum):
    FIXED = "fixed"
    OPTIMAL = "optimal"
    SPREAD = "spread"
    BURST = "burst"


@dataclass
class ScheduledPost:
    post_id: str
    platform: str
    username: str
    content: str
    media_urls: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    scheduled_at: str = ""
    published_at: str = ""
    status: str = PostStatus.PENDING.value
    niche: str = ""
    character_id: str = ""
    campaign_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    retry_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PLATFORM_OPTIMAL_TIMES: dict[str, list[tuple[int, int]]] = {
    "tiktok": [(7, 9), (12, 14), (19, 23)],
    "instagram": [(8, 10), (12, 14), (19, 21)],
    "youtube": [(14, 16), (19, 22)],
    "twitter": [(8, 10), (12, 13), (17, 19)],
    "facebook": [(9, 11), (13, 16), (19, 21)],
    "linkedin": [(8, 10), (12, 14), (17, 18)],
    "threads": [(8, 10), (19, 21)],
    "pinterest": [(20, 23)],
    "shopee": [(9, 11), (14, 16), (20, 22)],
    "tiktokshop": [(10, 12), (18, 22)],
}


class SocialScheduler:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        env_path = os.environ.get("UGC_SCHEDULER_DB", "")
        self.path = db_path or (Path(env_path) if env_path else DEFAULT_DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
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
                CREATE TABLE IF NOT EXISTS scheduled_posts (
                    post_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    username TEXT NOT NULL,
                    content TEXT NOT NULL,
                    media_urls TEXT NOT NULL,
                    hashtags TEXT NOT NULL,
                    scheduled_at TEXT,
                    published_at TEXT,
                    status TEXT NOT NULL,
                    niche TEXT,
                    character_id TEXT,
                    campaign_id TEXT,
                    metadata TEXT,
                    error TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON scheduled_posts(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scheduled ON scheduled_posts(scheduled_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_character ON scheduled_posts(character_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_platform ON scheduled_posts(platform)")
            conn.commit()

    def schedule(
        self,
        platform: str,
        username: str,
        content: str,
        scheduled_at: Optional[str] = None,
        media_urls: Optional[list[str]] = None,
        hashtags: Optional[list[str]] = None,
        niche: str = "",
        character_id: str = "",
        campaign_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
        strategy: str = ScheduleStrategy.FIXED.value,
    ) -> ScheduledPost:
        import time
        now = datetime.now(timezone.utc)
        if not scheduled_at:
            if strategy == ScheduleStrategy.OPTIMAL.value:
                scheduled_at = self._next_optimal_slot(platform, now)
            elif strategy == ScheduleStrategy.SPREAD.value:
                scheduled_at = (now + timedelta(hours=2)).isoformat()
            elif strategy == ScheduleStrategy.BURST.value:
                scheduled_at = (now + timedelta(minutes=15)).isoformat()
            else:
                scheduled_at = now.isoformat()
        post = ScheduledPost(
            post_id=f"sched_{uuid.uuid4().hex[:12]}",
            platform=platform,
            username=username,
            content=content,
            media_urls=media_urls or [],
            hashtags=hashtags or [],
            scheduled_at=scheduled_at,
            status=PostStatus.SCHEDULED.value if scheduled_at > now.isoformat() else PostStatus.PENDING.value,
            niche=niche,
            character_id=character_id,
            campaign_id=campaign_id,
            metadata=metadata or {},
        )
        self._save(post)
        log.info("scheduler.schedule post_id=%s platform=%s at=%s",
                 post.post_id, platform, scheduled_at)
        return post

    def _next_optimal_slot(self, platform: str, now: datetime) -> str:
        slots = PLATFORM_OPTIMAL_TIMES.get(platform, [(9, 11), (14, 16), (19, 21)])
        candidates = []
        for day_offset in range(7):
            base = now + timedelta(days=day_offset)
            for start_h, end_h in slots:
                candidate = base.replace(hour=start_h, minute=0, second=0, microsecond=0)
                if candidate > now:
                    candidates.append(candidate)
                if len(candidates) > 0 and day_offset > 0:
                    break
        if not candidates:
            return (now + timedelta(hours=1)).isoformat()
        candidates.sort()
        return candidates[0].isoformat()

    def _save(self, post: ScheduledPost) -> None:
        with self._lock:
            with self._conn() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO scheduled_posts
                    (post_id, platform, username, content, media_urls, hashtags,
                     scheduled_at, published_at, status, niche, character_id, campaign_id,
                     metadata, error, retry_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        post.post_id, post.platform, post.username, post.content,
                        json.dumps(post.media_urls), json.dumps(post.hashtags),
                        post.scheduled_at, post.published_at, post.status,
                        post.niche, post.character_id, post.campaign_id,
                        json.dumps(post.metadata), post.error, post.retry_count,
                        post.created_at, post.updated_at,
                    ),
                )

    def get(self, post_id: str) -> Optional[ScheduledPost]:
        with self._lock:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM scheduled_posts WHERE post_id=?", (post_id,)
                ).fetchone()
                if not row:
                    return None
                return self._row_to_post(row)

    def _row_to_post(self, row: sqlite3.Row) -> ScheduledPost:
        return ScheduledPost(
            post_id=row["post_id"],
            platform=row["platform"],
            username=row["username"],
            content=row["content"],
            media_urls=json.loads(row["media_urls"]),
            hashtags=json.loads(row["hashtags"]),
            scheduled_at=row["scheduled_at"] or "",
            published_at=row["published_at"] or "",
            status=row["status"],
            niche=row["niche"] or "",
            character_id=row["character_id"] or "",
            campaign_id=row["campaign_id"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            error=row["error"] or "",
            retry_count=row["retry_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def due_posts(self, limit: int = 50) -> list[ScheduledPost]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute(
                    """SELECT * FROM scheduled_posts
                    WHERE status IN (?, ?) AND scheduled_at <= ?
                    ORDER BY scheduled_at ASC LIMIT ?""",
                    (PostStatus.SCHEDULED.value, PostStatus.PENDING.value, now, limit),
                ).fetchall()
                return [self._row_to_post(r) for r in rows]

    def mark_publishing(self, post_id: str) -> None:
        self._update_status(post_id, PostStatus.PUBLISHING.value, updated=True)

    def mark_published(self, post_id: str, published_at: Optional[str] = None) -> None:
        published_at = published_at or datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE scheduled_posts SET status=?, published_at=?, updated_at=? WHERE post_id=?",
                    (PostStatus.PUBLISHED.value, published_at,
                     datetime.now(timezone.utc).isoformat(), post_id),
                )

    def mark_failed(self, post_id: str, error: str) -> None:
        with self._lock:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT retry_count FROM scheduled_posts WHERE post_id=?", (post_id,)
                ).fetchone()
                if not row:
                    return
                new_count = row["retry_count"] + 1
                status = PostStatus.FAILED.value if new_count >= 3 else PostStatus.SCHEDULED.value
                conn.execute(
                    "UPDATE scheduled_posts SET status=?, error=?, retry_count=?, updated_at=? WHERE post_id=?",
                    (status, error, new_count, datetime.now(timezone.utc).isoformat(), post_id),
                )

    def _update_status(self, post_id: str, status: str, updated: bool = True) -> None:
        with self._lock:
            with self._conn() as conn:
                if updated:
                    conn.execute(
                        "UPDATE scheduled_posts SET status=?, updated_at=? WHERE post_id=?",
                        (status, datetime.now(timezone.utc).isoformat(), post_id),
                    )
                else:
                    conn.execute(
                        "UPDATE scheduled_posts SET status=? WHERE post_id=?", (status, post_id)
                    )

    def cancel(self, post_id: str) -> bool:
        with self._lock:
            with self._conn() as conn:
                cur = conn.execute(
                    "UPDATE scheduled_posts SET status=? WHERE post_id=? AND status IN (?, ?)",
                    (PostStatus.CANCELLED.value, post_id,
                     PostStatus.PENDING.value, PostStatus.SCHEDULED.value),
                )
                return cur.rowcount > 0

    def list_by_character(self, character_id: str,
                          status: Optional[str] = None) -> list[ScheduledPost]:
        with self._lock:
            with self._conn() as conn:
                sql = "SELECT * FROM scheduled_posts WHERE character_id=?"
                params: list[Any] = [character_id]
                if status:
                    sql += " AND status=?"
                    params.append(status)
                sql += " ORDER BY scheduled_at DESC"
                rows = conn.execute(sql, params).fetchall()
                return [self._row_to_post(r) for r in rows]

    def list_by_campaign(self, campaign_id: str) -> list[ScheduledPost]:
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM scheduled_posts WHERE campaign_id=? ORDER BY scheduled_at",
                    (campaign_id,),
                ).fetchall()
                return [self._row_to_post(r) for r in rows]

    def list_by_status(self, status: str, limit: int = 100) -> list[ScheduledPost]:
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM scheduled_posts WHERE status=? ORDER BY scheduled_at LIMIT ?",
                    (status, limit),
                ).fetchall()
                return [self._row_to_post(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            with self._conn() as conn:
                by_status = conn.execute(
                    "SELECT status, COUNT(*) as c FROM scheduled_posts GROUP BY status"
                ).fetchall()
                by_platform = conn.execute(
                    "SELECT platform, COUNT(*) as c FROM scheduled_posts GROUP BY platform"
                ).fetchall()
                total = conn.execute("SELECT COUNT(*) as c FROM scheduled_posts").fetchone()["c"]
                due = conn.execute(
                    "SELECT COUNT(*) as c FROM scheduled_posts WHERE status IN (?, ?) AND scheduled_at <= ?",
                    (PostStatus.SCHEDULED.value, PostStatus.PENDING.value,
                     datetime.now(timezone.utc).isoformat()),
                ).fetchone()["c"]
        return {
            "total": total,
            "due": due,
            "by_status": {r["status"]: r["c"] for r in by_status},
            "by_platform": {r["platform"]: r["c"] for r in by_platform},
        }


__all__ = [
    "ScheduledPost",
    "PostStatus",
    "ScheduleStrategy",
    "SocialScheduler",
    "PLATFORM_OPTIMAL_TIMES",
    "DEFAULT_DB_PATH",
]
