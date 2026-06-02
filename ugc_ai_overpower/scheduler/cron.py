"""
Scheduler module for content posting.
"""
import sqlite3
import os
from datetime import datetime, timedelta

class ContentScheduler:
    """Simple SQLite‑backed scheduler for posting content.

    The table schema is created on first use.  All timestamps are stored as ISO strings.
    """

    def __init__(self, db_path: str = "data/scheduler.db"):
        self.db_path = db_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._ensure_schema()

    def _get_conn(self):
        # Use Row factory to allow name‑based column access.
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        conn = self._get_conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    post_url TEXT,
                    error TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def schedule_post(self, content_id: int, platform: str, scheduled_time: datetime) -> int:
        """Insert a new schedule entry and return its generated id."""
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO schedules (content_id, platform, scheduled_time) VALUES (?, ?, ?)",
                (content_id, platform, scheduled_time.isoformat()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_pending_posts(self):
        """Return a list of pending schedule rows as plain ``dict`` objects.

        Using ``sqlite3.Row`` enables dict‑like access, so we can simply
        ``dict(row)`` for each result.
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE status = 'pending' ORDER BY scheduled_time"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def mark_as_posted(self, schedule_id: int, post_url: str):
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE schedules SET status = 'posted', post_url = ? WHERE id = ?",
                (post_url, schedule_id),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_as_failed(self, schedule_id: int, error: str):
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE schedules SET status = 'failed', error = ? WHERE id = ?",
                (error, schedule_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_optimal_time(self, platform: str) -> datetime:
        """Placeholder optimal‑time logic – returns now + 2 hours for any platform."""
        # In a real system this would look up analytics.  Here we provide a deterministic value.
        return datetime.utcnow() + timedelta(hours=2)

    def cleanup_old_schedules(self, days: int = 30):
        """Delete schedule rows older than *days* from now."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        conn = self._get_conn()
        try:
            conn.execute(
                "DELETE FROM schedules WHERE datetime(scheduled_time) < ?",
                (cutoff.isoformat(),),
            )
            conn.commit()
        finally:
            conn.close()
