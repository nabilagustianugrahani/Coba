"""Real engagement analytics — aggregates views/likes/comments/shares/clicks from
``ContentBankV2.content_v2`` and pushes them to the Notion Analytics database
via :meth:`NotionDashboard.add_analytics`.

Why a dedicated collector?
    The ``add_analytics`` method on :class:`NotionDashboard` exists but has no
    producer. Engagement data is already accumulated in the local SQLite bank
    by the posters / queue / recycler pipeline — this module is the bridge
    that turns that data into Notion rows for the analytics dashboard.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2

log = logging.getLogger(__name__)


class AnalyticsCollector:
    """Collect engagement metrics from the bank and push to Notion.

    The collector owns no state of its own beyond a reference to a
    :class:`ContentBankV2`; it queries the underlying SQLite database
    directly so it can join ``content_v2`` with ``products_v2`` without
    widening the bank's public API.
    """

    def __init__(self, bank: Optional[ContentBankV2] = None):
        self.bank = bank or ContentBankV2()

    # ── Bank → rows ─────────────────────────────────────────────────
    def collect_from_bank(self, posted_only: bool = True) -> list:
        """Return aggregated engagement rows grouped by (product, platform).

        Each row::

            {
                "product_id": int | None,
                "product_name": str,
                "platform": str,
                "views": int, "likes": int, "comments": int,
                "shares": int, "clicks": int,
                "engagement_score": float,
                "content_count": int,
            }
        """
        conn = sqlite3.connect(self.bank.db_path)
        conn.row_factory = sqlite3.Row
        try:
            if posted_only:
                where = ("WHERE c.post_url != '' OR c.posted_at IS NOT NULL "
                         "OR c.status = 'posted'")
            else:
                where = ""
            sql = f"""
                SELECT
                    COALESCE(p.id, c.product_id)        AS product_id,
                    COALESCE(p.name, 'Unknown')         AS product_name,
                    c.platform                          AS platform,
                    SUM(COALESCE(c.views, 0))           AS views,
                    SUM(COALESCE(c.likes, 0))           AS likes,
                    SUM(COALESCE(c.comments, 0))        AS comments,
                    SUM(COALESCE(c.shares, 0))          AS shares,
                    SUM(COALESCE(c.clicks, 0))          AS clicks,
                    ROUND(AVG(COALESCE(c.engagement_score, 0)), 2)
                                                     AS engagement_score,
                    COUNT(c.id)                         AS content_count
                FROM content_v2 c
                LEFT JOIN products_v2 p ON p.id = c.product_id
                {where}
                GROUP BY COALESCE(p.id, c.product_id), c.platform
                ORDER BY views DESC
            """
            rows = conn.execute(sql).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def collect_per_content(self) -> list:
        """One row per ``content_v2`` entry that has any engagement signal."""
        conn = sqlite3.connect(self.bank.db_path)
        conn.row_factory = sqlite3.Row
        try:
            base = """
                SELECT c.id, c.product_id,
                       COALESCE(p.name, 'Unknown')  AS product_name,
                       c.platform, c.hook, c.post_url,
                       COALESCE(c.views, 0)        AS views,
                       COALESCE(c.likes, 0)        AS likes,
                       COALESCE(c.comments, 0)     AS comments,
                       COALESCE(c.shares, 0)       AS shares,
                       COALESCE(c.clicks, 0)       AS clicks,
                       COALESCE(c.engagement_score, 0) AS engagement_score,
                       c.posted_at, c.status
                FROM content_v2 c
                LEFT JOIN products_v2 p ON p.id = c.product_id
                WHERE (c.post_url != '' OR c.posted_at IS NOT NULL
                       OR c.status = 'posted'
                       OR c.views > 0 OR c.likes > 0)
                ORDER BY COALESCE(c.posted_at, c.created_at) DESC, c.id DESC
            """
            rows = conn.execute(base).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Daily totals ────────────────────────────────────────────────
    def daily_aggregate(self) -> dict:
        """Sum of all engagement metrics across posted content.

        Returns a dict with keys:
            content_count, views, likes, comments, shares, clicks,
            avg_engagement_score, engagement_rate, collected_at
        """
        conn = sqlite3.connect(self.bank.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """
                SELECT
                    COUNT(*)                          AS content_count,
                    COALESCE(SUM(views), 0)           AS views,
                    COALESCE(SUM(likes), 0)           AS likes,
                    COALESCE(SUM(comments), 0)        AS comments,
                    COALESCE(SUM(shares), 0)          AS shares,
                    COALESCE(SUM(clicks), 0)          AS clicks,
                    ROUND(AVG(NULLIF(engagement_score, 0)), 2)
                                                  AS avg_engagement_score
                FROM content_v2
                WHERE post_url != '' OR posted_at IS NOT NULL OR status = 'posted'
                """,
            ).fetchone()
            d = dict(row) if row else {}
            d.setdefault("content_count", 0)
            d.setdefault("views", 0)
            d.setdefault("likes", 0)
            d.setdefault("comments", 0)
            d.setdefault("shares", 0)
            d.setdefault("clicks", 0)
            d.setdefault("avg_engagement_score", 0.0)

            total_eng = d["likes"] + d["comments"] + d["shares"] + d["clicks"]
            views = max(d["views"], 1)
            d["engagement_rate"] = round(total_eng / views * 100, 2)
            d["collected_at"] = datetime.now(timezone.utc).isoformat()
            return d
        finally:
            conn.close()

    # ── Notion push ─────────────────────────────────────────────────
    def push_to_notion(self) -> dict:
        """Push aggregated bank metrics into the Notion Analytics database.

        For each Notion campaign whose product name matches a product in the
        bank, write one Analytics row per content item using the campaign's
        aggregated engagement numbers.
        """
        from ugc_ai_overpower.core.notion_sync import NotionDashboard

        nd = NotionDashboard()
        if not nd.ready:
            return {"status": "error", "message": "Notion not configured"}
        if not nd.analytics_db:
            return {"status": "error", "message": "Analytics DB not configured"}

        aggregates = self.collect_from_bank()
        if not aggregates:
            return {"status": "ok", "synced": 0,
                    "message": "No engagement data in bank"}

        campaigns = nd.get_all_campaigns()
        if not campaigns:
            return {"status": "ok", "synced": 0,
                    "message": "No campaigns in Notion"}

        # Index bank aggregates by product name (lowercased) for O(1) lookup.
        agg_by_name: dict = {a["product_name"].lower(): a for a in aggregates}

        results = []
        matched_campaigns = 0
        for c in campaigns:
            product_key = (c.get("product") or "").lower()
            agg = agg_by_name.get(product_key)
            if not agg:
                continue
            matched_campaigns += 1

            content_items = nd.get_content_for_campaign(c["id"])
            for item in content_items:
                aid = nd.add_analytics(
                    content_id=item["id"],
                    campaign_id=c["id"],
                    views=int(agg["views"] or 0),
                    likes=int(agg["likes"] or 0),
                    comments=int(agg["comments"] or 0),
                    shares=int(agg["shares"] or 0),
                    clicks=int(agg["clicks"] or 0),
                    platform=item.get("platform") or agg.get("platform") or "tiktok",
                    post_url=item.get("post_url", ""),
                )
                if aid:
                    results.append({
                        "campaign_id": c["id"],
                        "content_id": item["id"],
                        "analytics_id": aid,
                    })

        return {
            "status": "ok",
            "synced": len(results),
            "campaigns_matched": matched_campaigns,
            "items": results,
        }
