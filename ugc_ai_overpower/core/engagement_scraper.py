"""Engagement scraper — update and simulate engagement metrics for content
items in the local ContentBankV2 SQLite database.

Provides single/batch updates and a simulation mode for testing.
"""

from __future__ import annotations

import logging
import random
import sqlite3
from typing import Optional

from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2

log = logging.getLogger(__name__)


class EngagementScraper:
    """Scrape and update engagement metrics (views, likes, comments, shares, clicks)
    for content items in the bank.
    """

    def __init__(self, bank: Optional[ContentBankV2] = None):
        self.bank = bank or ContentBankV2()

    def update_single(self, content_id: int, views: int = 0, likes: int = 0,
                      comments: int = 0, shares: int = 0, clicks: int = 0) -> dict:
        eng_score = self._calc_engagement_score(views, likes, comments, shares, clicks)
        conn = sqlite3.connect(self.bank.db_path)
        try:
            conn.execute(
                """UPDATE content_v2 SET views=?, likes=?, comments=?, shares=?,
                   clicks=?, engagement_score=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (views, likes, comments, shares, clicks, eng_score, content_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM content_v2 WHERE id=?", (content_id,)
            ).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def update_batch(self, updates: list[dict]) -> dict:
        conn = sqlite3.connect(self.bank.db_path)
        try:
            for u in updates:
                cid = u.get("content_id")
                if not cid:
                    continue
                views = u.get("views", 0)
                likes = u.get("likes", 0)
                comments = u.get("comments", 0)
                shares = u.get("shares", 0)
                clicks = u.get("clicks", 0)
                score = self._calc_engagement_score(views, likes, comments, shares, clicks)
                conn.execute(
                    """UPDATE content_v2 SET views=?, likes=?, comments=?, shares=?,
                       clicks=?, engagement_score=?, updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (views, likes, comments, shares, clicks, score, cid),
                )
            conn.commit()
            return {"updated": len(updates), "status": "ok"}
        finally:
            conn.close()

    def simulate_engagement(self, content_id: int) -> dict:
        conn = sqlite3.connect(self.bank.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM content_v2 WHERE id=?", (content_id,)
            ).fetchone()
            if not row:
                return {"error": f"Content {content_id} not found"}
            row = dict(row)
            base_views = row.get("views", 0) or random.randint(100, 5000)
            base = max(base_views, 1)
            likes = int(base * random.uniform(0.02, 0.15))
            comments = int(base * random.uniform(0.005, 0.03))
            shares = int(base * random.uniform(0.01, 0.05))
            clicks = int(base * random.uniform(0.03, 0.10))
            return self.update_single(content_id, base, likes, comments, shares, clicks)
        finally:
            conn.close()

    def simulate_all(self, posted_only: bool = True) -> dict:
        conn = sqlite3.connect(self.bank.db_path)
        try:
            if posted_only:
                where = ("WHERE post_url != '' OR posted_at IS NOT NULL "
                         "OR status = 'posted'")
            else:
                where = ""
            rows = conn.execute(
                f"SELECT id FROM content_v2 {where} ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

        results = []
        for r in rows:
            results.append(self.simulate_engagement(r["id"]))
        return {"simulated": len(results), "items": results[:10]}

    @staticmethod
    def _calc_engagement_score(views: int, likes: int, comments: int,
                                shares: int, clicks: int) -> float:
        if views == 0:
            return 0.0
        total_eng = likes + comments + shares + clicks
        return round(total_eng / views * 100, 2)
