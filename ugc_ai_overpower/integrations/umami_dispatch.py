"""Umami analytics integration for UGC post tracking.

umami (MIT, 37k stars) is a self-hosted Google Analytics alternative.
We send per-post events via their HTTP API:
  POST /api/send
  { "type": "event", "payload": { "website": "...", "url": "...", "name": "cta_click" } }

This module:
  - Sends per-post tracking events
  - Aggregates daily engagement rollups
  - Pushes to Notion Analytics database
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


DEFAULT_DB_PATH = Path.home() / ".9router" / "umami_tracking.db"
DEFAULT_BASE_URL = "https://umami.example.com"


@dataclass
class TrackingEvent:
    event_id: str
    website_id: str
    url: str
    event_name: str
    session_id: str = ""
    user_id: str = ""
    referrer: str = ""
    screen_width: int = 0
    language: str = "id-ID"
    country: str = "ID"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_payload(self) -> dict[str, Any]:
        return {
            "website": self.website_id,
            "url": self.url,
            "name": self.event_name,
            "data": {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "referrer": self.referrer,
                "screen": str(self.screen_width) if self.screen_width else "",
                "language": self.language,
                "country": self.country,
                **self.metadata,
            },
        }


class UmamiDispatcher:
    def __init__(
        self,
        base_url: Optional[str] = None,
        website_id: Optional[str] = None,
        api_key: Optional[str] = None,
        db_path: Optional[Path] = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("UMAMI_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.website_id = website_id or os.environ.get("UMAMI_WEBSITE_ID", "")
        self.api_key = api_key or os.environ.get("UMAMI_API_KEY", "")
        env_db = os.environ.get("UGC_UMAMI_DB", "")
        self.path = db_path or (Path(env_db) if env_db else DEFAULT_DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def is_configured(self) -> bool:
        return bool(self.website_id)

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
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    website_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    session_id TEXT,
                    user_id TEXT,
                    referrer TEXT,
                    metadata TEXT,
                    sent INTEGER NOT NULL DEFAULT 0,
                    response_status INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON events(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_name ON events(event_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sent ON events(sent)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON events(created_at)")
            conn.commit()

    def track(
        self,
        url: str,
        event_name: str,
        session_id: str = "",
        user_id: str = "",
        referrer: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> TrackingEvent:
        import uuid
        event = TrackingEvent(
            event_id=f"ev_{uuid.uuid4().hex[:16]}",
            website_id=self.website_id,
            url=url,
            event_name=event_name,
            session_id=session_id,
            user_id=user_id,
            referrer=referrer,
            metadata=metadata or {},
        )
        with self._lock:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO events
                    (event_id, website_id, url, event_name, session_id, user_id, referrer, metadata, sent, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                    (
                        event.event_id, event.website_id, event.url, event.event_name,
                        event.session_id, event.user_id, event.referrer,
                        json.dumps(event.metadata), event.created_at,
                    ),
                )
        self._flush_pending()
        return event

    def track_ugc_post(
        self,
        post_url: str,
        platform: str,
        content_id: str,
        character_id: str = "",
        niche: str = "",
    ) -> TrackingEvent:
        return self.track(
            url=post_url,
            event_name="ugc_post_published",
            user_id=character_id,
            referrer=platform,
            metadata={
                "platform": platform,
                "content_id": content_id,
                "character_id": character_id,
                "niche": niche,
            },
        )

    def track_engagement(
        self,
        post_url: str,
        platform: str,
        views: int = 0,
        likes: int = 0,
        shares: int = 0,
        comments: int = 0,
    ) -> TrackingEvent:
        return self.track(
            url=post_url,
            event_name="ugc_engagement_update",
            referrer=platform,
            metadata={
                "platform": platform,
                "views": views,
                "likes": likes,
                "shares": shares,
                "comments": comments,
            },
        )

    def track_affiliate_click(
        self,
        affiliate_url: str,
        platform: str,
        product_id: str,
        character_id: str = "",
    ) -> TrackingEvent:
        return self.track(
            url=affiliate_url,
            event_name="affiliate_click",
            user_id=character_id,
            referrer=platform,
            metadata={
                "platform": platform,
                "product_id": product_id,
                "character_id": character_id,
            },
        )

    def _flush_pending(self) -> int:
        if not self.is_configured():
            log.debug("umami not configured, skipping flush")
            return 0
        sent = 0
        try:
            import urllib.request
            import urllib.error
        except ImportError:
            return 0
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM events WHERE sent=0 ORDER BY created_at LIMIT 50"
                ).fetchall()
                for r in rows:
                    try:
                        payload = {
                            "type": "event",
                            "payload": {
                                "website": r["website_id"],
                                "url": r["url"],
                                "name": r["event_name"],
                                "data": json.loads(r["metadata"]) if r["metadata"] else {},
                            },
                        }
                        data = json.dumps(payload).encode("utf-8")
                        req = urllib.request.Request(
                            f"{self.base_url}/api/send",
                            data=data,
                            headers={
                                "Content-Type": "application/json",
                                "User-Agent": "ugc-ai-overpower/1.0",
                            },
                            method="POST",
                        )
                        if self.api_key:
                            req.add_header("Authorization", f"Bearer {self.api_key}")
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            status = resp.status
                    except (urllib.error.URLError, urllib.error.HTTPError) as e:
                        log.warning("umami send failed: %s", e)
                        status = 0
                    except Exception as e:
                        log.warning("umami send error: %s", e)
                        status = -1
                    conn.execute(
                        "UPDATE events SET sent=?, response_status=? WHERE event_id=?",
                        (1 if status and status < 400 else 0, status, r["event_id"]),
                    )
                    if status and 200 <= status < 400:
                        sent += 1
        if sent:
            log.info("umami.flush sent %d events", sent)
        return sent

    def daily_rollup(self, date: Optional[str] = None) -> dict[str, Any]:
        date = date or datetime.now(timezone.utc).date().isoformat()
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute(
                    """SELECT url, event_name, COUNT(*) as cnt
                    FROM events
                    WHERE substr(created_at, 1, 10) = ?
                    GROUP BY url, event_name""",
                    (date,),
                ).fetchall()
        by_url: dict[str, dict[str, int]] = {}
        for r in rows:
            by_url.setdefault(r["url"], {})[r["event_name"]] = r["cnt"]
        return {
            "date": date,
            "total_events": sum(r["cnt"] for r in rows),
            "unique_urls": len(by_url),
            "by_url": by_url,
        }

    def stats(self) -> dict[str, Any]:
        with self._lock:
            with self._conn() as conn:
                total = conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"]
                sent = conn.execute("SELECT COUNT(*) as c FROM events WHERE sent=1").fetchone()["c"]
                pending = conn.execute("SELECT COUNT(*) as c FROM events WHERE sent=0").fetchone()["c"]
        return {
            "configured": self.is_configured(),
            "base_url": self.base_url,
            "website_id": self.website_id,
            "total_events": total,
            "sent": sent,
            "pending": pending,
        }


__all__ = [
    "TrackingEvent",
    "UmamiDispatcher",
    "DEFAULT_DB_PATH",
    "DEFAULT_BASE_URL",
]
