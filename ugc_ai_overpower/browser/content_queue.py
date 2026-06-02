"""SQLite‑backed content queue.

This module provides a persistent queue for scheduling platform posts.
Every row in the ``content_queue`` table represents one piece of content
that is pending, in progress, done, or failed.

Example usage::

    from ugc_ai_overpower.browser.content_queue import ContentQueue

    q = ContentQueue()
    qid = q.enqueue(content_id=42, platform="tiktok")
    item = q.dequeue()          # → dict or None
    if item:
        q.mark_done(item["id"], post_url="https://...")
    q.get_stats()               # → dict of counts
"""

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default SQLite path – next to content_bank.db
# ---------------------------------------------------------------------------
_DB_DIR = Path(__file__).parents[2] / "core"
_DB_DIR.mkdir(parents=True, exist_ok=True)
_DEFAULT_DB_PATH = str(_DB_DIR / "content_bank.db")

# ---------------------------------------------------------------------------
# Queue schema (migrated automatically)
# ---------------------------------------------------------------------------
_QUEUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS content_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id    INTEGER NOT NULL,
    platform      TEXT    NOT NULL CHECK (platform IN ('tiktok','instagram','youtube')),
    status        TEXT    NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','processing','done','failed')),
    scheduled_at  TIMESTAMP,
    retry_count   INTEGER NOT NULL DEFAULT 0,
    max_retries   INTEGER NOT NULL DEFAULT 3,
    error         TEXT,
    post_url      TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_queue_status ON content_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_platform ON content_queue(platform);
"""

# ---------------------------------------------------------------------------
# Content queue
# ---------------------------------------------------------------------------

class ContentQueue:
    """Persistent content queue backed by a shared SQLite table.

    Thread‑safe: an internal ``threading.Lock`` serialises all write access.
    Read operations are **not** locked; they rely on SQLite's own concurrency
    model (which is sufficient for the typical single‑process use case).
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or _DEFAULT_DB_PATH
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_QUEUE_SCHEMA)
            conn.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(
        self,
        content_id: int,
        platform: str,
        scheduled_at: Optional[str] = None,
        max_retries: int = 3,
    ) -> int:
        """Insert a new item into the queue.

        Returns the auto‑generated ``id`` of the new row.
        """
        platform = platform.lower()
        if platform not in ("tiktok", "instagram", "youtube"):
            raise ValueError(f"Unsupported platform: {platform!r}")

        now = self._now()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """INSERT INTO content_queue
                       (content_id, platform, scheduled_at, max_retries, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (content_id, platform, scheduled_at, max_retries, now, now),
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def dequeue(self, platform: Optional[str] = None) -> Optional[dict]:
        """Atomically claim the next pending item.

        If *platform* is given only items matching that platform are
        considered. Items are ordered by ``scheduled_at`` (nulls first,
        then oldest).

        Returns a row dict, or ``None`` if the queue is empty.
        """
        with self._lock:
            conn = self._connect()
            try:
                # Build the query dynamically.
                platform_filter = ""
                params: list = []
                if platform:
                    platform_filter = "AND platform = ?"
                    params.append(platform.lower())

                # Pick one pending item (transactionally).
                row = conn.execute(
                    """SELECT id, content_id, platform, scheduled_at, retry_count, max_retries
                       FROM content_queue
                       WHERE status = 'pending'
                       AND (scheduled_at IS NULL OR scheduled_at <= datetime('now'))
                       {}
                       ORDER BY scheduled_at ASC, id ASC
                       LIMIT 1
                       FOR UPDATE""".format(platform_filter),
                    params,
                ).fetchone()

                if row is None:
                    return None

                # Mark as processing.
                now = self._now()
                conn.execute(
                    "UPDATE content_queue SET status = 'processing', updated_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                conn.commit()
                return dict(row)
            finally:
                conn.close()

    def mark_done(self, queue_id: int, post_url: str) -> None:
        """Mark an item as successfully posted."""
        now = self._now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """UPDATE content_queue
                       SET status = 'done', post_url = ?, updated_at = ?
                       WHERE id = ?""",
                    (post_url, now, queue_id),
                )
                conn.commit()
            finally:
                conn.close()
        log.info("Queue item %d marked done – %s", queue_id, post_url)

    def mark_failed(self, queue_id: int, error: str) -> None:
        """Mark an item as failed.

        If the retry count is below ``max_retries`` the item is reset to
        ``pending`` and its retry count incremented instead of being moved
        to ``failed``.
        """
        now = self._now()
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT retry_count, max_retries FROM content_queue WHERE id = ?",
                    (queue_id,),
                ).fetchone()
                if row is None:
                    log.warning("mark_failed: unknown queue id %d", queue_id)
                    return

                if row["retry_count"] < row["max_retries"]:
                    # Retry.
                    conn.execute(
                        """UPDATE content_queue
                           SET status = 'pending', retry_count = retry_count + 1,
                               error = ?, updated_at = ?
                           WHERE id = ?""",
                        (error, now, queue_id),
                    )
                    log.info(
                        "Queue item %d reset to pending (retry %d/%d)",
                        queue_id,
                        row["retry_count"] + 1,
                        row["max_retries"],
                    )
                else:
                    # Permanent failure.
                    conn.execute(
                        """UPDATE content_queue
                           SET status = 'failed', error = ?, updated_at = ?
                           WHERE id = ?""",
                        (error, now, queue_id),
                    )
                    log.warning("Queue item %d failed permanently: %s", queue_id, error)
                conn.commit()
            finally:
                conn.close()

    def get_stats(self) -> dict:
        """Return a count breakdown by status.

        Example return value::

            {
                "pending": 12,
                "processing": 1,
                "done": 45,
                "failed": 3,
                "total": 61,
            }
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT status, COUNT(*) as cnt
                   FROM content_queue
                   GROUP BY status"""
            ).fetchall()
            counts = {r["status"]: r["cnt"] for r in rows}
            stats = {
                "pending": counts.get("pending", 0),
                "processing": counts.get("processing", 0),
                "done": counts.get("done", 0),
                "failed": counts.get("failed", 0),
            }
            stats["total"] = sum(stats.values())
            return stats
        finally:
            conn.close()

    def list_items(
        self,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Return recent queue items, optionally filtered.

        Items are ordered by ``updated_at`` descending (most recent first).
        """
        conn = self._connect()
        try:
            conditions = []
            params: list = []
            if status:
                conditions.append("status = ?")
                params.append(status)
            if platform:
                conditions.append("platform = ?")
                params.append(platform.lower())

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            rows = conn.execute(
                """SELECT id, content_id, platform, status, scheduled_at,
                          retry_count, error, post_url, created_at, updated_at
                   FROM content_queue
                   {}
                   ORDER BY updated_at DESC
                   LIMIT ?""".format(where),
                params + [limit],
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def retry_failed(self, max_retries: int = 3) -> int:
        """Reset all permanently failed items back to ``pending``.

        The retry count is preserved so that the next failure will still
        land in the ``failed`` status again.

        Returns the number of items reset.
        """
        now = self._now()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """UPDATE content_queue
                       SET status = 'pending', error = NULL, updated_at = ?
                       WHERE status = 'failed' AND retry_count < ?""",
                    (now, max_retries),
                )
                conn.commit()
                return cur.rowcount
            finally:
                conn.close()

    def purge_done(self, older_than_days: int = 7) -> int:
        """Delete completed items older than *older_than_days*.

        Returns the number of deleted rows.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                """DELETE FROM content_queue
                   WHERE status = 'done'
                   AND updated_at < datetime('now', ?)""",
                (f"-{older_than_days} days",),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
