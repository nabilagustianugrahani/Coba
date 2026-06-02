"""
Engagement tracking module.
"""
import sqlite3
import os
from datetime import datetime

class EngagementTracker:
    """Simple SQLite‑backed engagement tracker."""

    def __init__(self, db_path: str = "data/engagement.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._ensure_schema()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        conn = self._get_conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS post_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    recorded_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    product_id TEXT NOT NULL,
                    revenue REAL NOT NULL,
                    recorded_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def track_post_metrics(self, post_id: int, views: int = 0, likes: int = 0, comments: int = 0, shares: int = 0, clicks: int = 0):
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO post_metrics (post_id, views, likes, comments, shares, clicks, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (post_id, views, likes, comments, shares, clicks, datetime.utcnow().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def calculate_engagement_rate(self, post_id: int) -> float:
        """Engagement rate = (likes + comments + shares) / views, returns 0 if views == 0."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT views, likes, comments, shares FROM post_metrics WHERE post_id = ? ORDER BY recorded_at DESC LIMIT 1",
                (post_id,),
            ).fetchone()
            if not row:
                return 0.0
            views, likes, comments, shares = row
            if views == 0:
                return 0.0
            return (likes + comments + shares) / views
        finally:
            conn.close()

    def get_top_performing_posts(self, limit: int = 10):
        """Return top posts by engagement rate (descending)."""
        conn = self._get_conn()
        try:
            # We'll compute engagement rate in SQL for simplicity, but we can also do in Python.
            # Since we need the latest metrics per post, we use a subquery.
            query = """
                SELECT pm.post_id,
                       pm.views,
                       pm.likes,
                       pm.comments,
                       pm.shares,
                       pm.clicks,
                       pm.recorded_at,
                       CASE WHEN pm.views = 0 THEN 0
                            ELSE (pm.likes + pm.comments + pm.shares) * 1.0 / pm.views
                       END AS engagement_rate
                FROM post_metrics pm
                INNER JOIN (
                    SELECT post_id, MAX(recorded_at) AS max_recorded_at
                    FROM post_metrics
                    GROUP BY post_id
                ) latest ON pm.post_id = latest.post_id AND pm.recorded_at = latest.max_recorded_at
                ORDER BY engagement_rate DESC
                LIMIT ?
            """
            rows = conn.execute(query, (limit,)).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_platform_stats(self, platform: str):
        """Placeholder: return dummy stats for a platform.
        In a real system we would join with posts table to filter by platform.
        Since we don't have that, we return empty dict.
        """
        # For now, we don't store platform in metrics, so we cannot filter.
        # Return a dict with zeros.
        return {
            "platform": platform,
            "total_posts": 0,
            "total_views": 0,
            "total_likes": 0,
            "total_comments": 0,
            "total_shares": 0,
            "average_engagement_rate": 0.0,
        }

    def track_conversion(self, post_id: int, product_id: str, revenue: float) -> int:
        conn = self._get_conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO conversions (post_id, product_id, revenue, recorded_at)
                VALUES (?, ?, ?, ?)
                """,
                (post_id, product_id, revenue, datetime.utcnow().isoformat()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_roi_stats(self, campaign_id: str):
        """Placeholder ROI stats.
        Since we don't have a campaign table, we return empty dict.
        """
        return {
            "campaign_id": campaign_id,
            "total_revenue": 0.0,
            "total_cost": 0.0,
            "roi": 0.0,
        }
