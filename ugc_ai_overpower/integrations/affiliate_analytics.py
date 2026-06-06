"""Revenue analytics and reporting for affiliate links.

Aggregates click and conversion data into daily/weekly/monthly reports,
niche and platform breakdowns, simple revenue forecasting, and anomaly
detection.

Typical usage:
    tracker = AffiliateTracker("affiliate.db")
    analytics = AffiliateAnalytics(tracker)
    report = analytics.daily_report("2026-06-01")
    print(report.total_revenue_usd, report.conversion_rate)
    analytics.export_csv(report, "report.csv")
"""
from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ugc_ai_overpower.integrations.affiliate import AffiliateTracker


@dataclass
class RevenueReport:
    """Aggregated revenue report for a period."""
    period: str
    total_clicks: int = 0
    unique_clicks: int = 0
    total_conversions: int = 0
    total_revenue_usd: float = 0.0
    total_commission_usd: float = 0.0
    avg_order_value_usd: float = 0.0
    conversion_rate: float = 0.0
    top_products: list[tuple[str, float]] = field(default_factory=list)
    top_platforms: list[tuple[str, float]] = field(default_factory=list)
    top_niches: list[tuple[str, float]] = field(default_factory=list)
    daily_breakdown: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AffiliateAnalytics:
    """Analytics engine over an AffiliateTracker instance."""

    def __init__(self, tracker: AffiliateTracker) -> None:
        self.tracker = tracker

    def _date_range(self, start: str, end: str) -> tuple[str, str]:
        """Return (start_iso, end_iso) for date filtering."""
        return (f"{start}T00:00:00", f"{end}T23:59:59")

    def _build_report(
        self,
        period: str,
        start_iso: str,
        end_iso: str,
    ) -> RevenueReport:
        """Build a RevenueReport for a given time window."""
        cur = self.tracker._conn.cursor()

        # Total clicks
        cur.execute(
            "SELECT COUNT(*) FROM click_events WHERE timestamp >= ? AND timestamp <= ?",
            (start_iso, end_iso),
        )
        total_clicks = int(cur.fetchone()[0])

        # Unique clicks (by ip_hash)
        cur.execute(
            "SELECT COUNT(DISTINCT ip_hash) FROM click_events WHERE timestamp >= ? AND timestamp <= ?",
            (start_iso, end_iso),
        )
        unique_clicks = int(cur.fetchone()[0])

        # Conversions
        cur.execute(
            """SELECT COUNT(*), COALESCE(SUM(order_value_usd), 0),
                      COALESCE(SUM(commission_usd), 0)
               FROM conversion_events WHERE timestamp >= ? AND timestamp <= ?""",
            (start_iso, end_iso),
        )
        row = cur.fetchone()
        total_conversions = int(row[0])
        total_revenue = round(float(row[1]), 2)
        total_commission = round(float(row[2]), 2)
        avg_ov = round(total_revenue / total_conversions, 2) if total_conversions > 0 else 0.0
        conv_rate = round(total_conversions / total_clicks, 4) if total_clicks > 0 else 0.0

        # Top products
        cur.execute(
            """SELECT product_id, COALESCE(SUM(order_value_usd), 0) AS rev
               FROM conversion_events
               WHERE timestamp >= ? AND timestamp <= ?
               GROUP BY product_id ORDER BY rev DESC LIMIT 5""",
            (start_iso, end_iso),
        )
        top_products = [(r["product_id"], round(float(r["rev"]), 2)) for r in cur.fetchall()]

        # Top platforms
        cur.execute(
            """SELECT platform, COALESCE(SUM(order_value_usd), 0) AS rev
               FROM conversion_events
               WHERE timestamp >= ? AND timestamp <= ?
               GROUP BY platform ORDER BY rev DESC LIMIT 5""",
            (start_iso, end_iso),
        )
        top_platforms = [(r["platform"], round(float(r["rev"]), 2)) for r in cur.fetchall()]

        # Daily breakdown
        cur.execute(
            """SELECT DATE(timestamp) AS day,
                      COUNT(DISTINCT click_id) AS clicks,
                      COUNT(DISTINCT conversion_id) AS conversions,
                      COALESCE(SUM(order_value_usd), 0) AS revenue
               FROM (
                   SELECT timestamp, click_id, NULL AS conversion_id, NULL AS order_value_usd
                   FROM click_events WHERE timestamp >= ? AND timestamp <= ?
                   UNION ALL
                   SELECT timestamp, NULL, conversion_id, order_value_usd
                   FROM conversion_events WHERE timestamp >= ? AND timestamp <= ?
               ) GROUP BY day ORDER BY day""",
            (start_iso, end_iso, start_iso, end_iso),
        )
        daily_breakdown = [dict(r) for r in cur.fetchall()]

        return RevenueReport(
            period=period,
            total_clicks=total_clicks,
            unique_clicks=unique_clicks,
            total_conversions=total_conversions,
            total_revenue_usd=total_revenue,
            total_commission_usd=total_commission,
            avg_order_value_usd=avg_ov,
            conversion_rate=conv_rate,
            top_products=top_products,
            top_platforms=top_platforms,
            daily_breakdown=daily_breakdown,
        )

    def daily_report(self, date: str) -> RevenueReport:
        """Generate a report for a single day (YYYY-MM-DD)."""
        start, end = self._date_range(date, date)
        return self._build_report(f"daily:{date}", start, end)

    def weekly_report(self, week: str) -> RevenueReport:
        """Generate a report for a week (ISO week string like 2026-W23)."""
        year, wnum = week.split("-W")
        # Approximate: Monday of ISO week
        jan4 = datetime(int(year), 1, 4, tzinfo=timezone.utc)
        start = jan4 + timedelta(weeks=int(wnum) - 1, days=-jan4.weekday())
        end = start + timedelta(days=6)
        start_iso, end_iso = self._date_range(
            start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
        )
        return self._build_report(f"weekly:{week}", start_iso, end_iso)

    def monthly_report(self, month: str) -> RevenueReport:
        """Generate a report for a month (YYYY-MM)."""
        y, m = month.split("-")
        start = datetime(int(y), int(m), 1, tzinfo=timezone.utc)
        if int(m) == 12:
            end = datetime(int(y) + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            end = datetime(int(y), int(m) + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        start_iso, end_iso = self._date_range(
            start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
        )
        return self._build_report(f"monthly:{month}", start_iso, end_iso)

    def niche_breakdown(self, days: int = 30) -> dict[str, float]:
        """Get revenue broken down by niche (derived from product metadata)."""
        # Use link metadata 'niche' if available, otherwise 'unknown'
        cur = self.tracker._conn.cursor()
        cur.execute(
            """SELECT a.metadata, COALESCE(SUM(c.order_value_usd), 0) AS rev
               FROM conversion_events c
               JOIN affiliate_links a ON c.link_id = a.link_id
               WHERE c.timestamp >= datetime('now', ?)
               GROUP BY a.link_id""",
            (f"-{days} days",),
        )
        niche_rev: dict[str, float] = {}
        for row in cur.fetchall():
            meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else {}
            niche = meta.get("niche", "unknown")
            niche_rev[niche] = niche_rev.get(niche, 0.0) + float(row["rev"])
        return {k: round(v, 2) for k, v in sorted(niche_rev.items(), key=lambda x: -x[1])}

    def platform_breakdown(self, days: int = 30) -> dict[str, float]:
        """Get revenue broken down by e-commerce platform."""
        cur = self.tracker._conn.cursor()
        cur.execute(
            """SELECT platform, COALESCE(SUM(order_value_usd), 0) AS rev
               FROM conversion_events
               WHERE timestamp >= datetime('now', ?)
               GROUP BY platform
               ORDER BY rev DESC""",
            (f"-{days} days",),
        )
        return {r["platform"]: round(float(r["rev"]), 2) for r in cur.fetchall()}

    def forecast_revenue(self, days_ahead: int = 30) -> float:
        """Simple linear forecast based on average daily revenue over last 30 days."""
        cur = self.tracker._conn.cursor()
        cur.execute(
            """SELECT DATE(timestamp) AS day, COALESCE(SUM(order_value_usd), 0) AS rev
               FROM conversion_events
               WHERE timestamp >= datetime('now', '-30 days')
               GROUP BY day""",
        )
        rows = cur.fetchall()
        if len(rows) < 2:
            return 0.0
        daily_values = [float(r["rev"]) for r in rows]
        avg_daily = statistics.mean(daily_values)
        return round(avg_daily * days_ahead, 2)

    def detect_anomalies(self, days: int = 30) -> list[dict]:
        """Detect anomalous days (revenue > 2 stddev from mean)."""
        cur = self.tracker._conn.cursor()
        cur.execute(
            """SELECT DATE(timestamp) AS day, COALESCE(SUM(order_value_usd), 0) AS rev
               FROM conversion_events
               WHERE timestamp >= datetime('now', ?)
               GROUP BY day ORDER BY day""",
            (f"-{days} days",),
        )
        rows = cur.fetchall()
        if len(rows) < 3:
            return []
        values = [float(r["rev"]) for r in rows]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0
        anomalies: list[dict] = []
        for r in rows:
            rev = float(r["rev"])
            if stdev > 0 and abs(rev - mean) > 2 * stdev:
                anomalies.append({
                    "day": r["day"],
                    "revenue": round(rev, 2),
                    "z_score": round((rev - mean) / stdev, 2),
                    "direction": "spike" if rev > mean else "drop",
                })
        return anomalies

    def export_csv(self, report: RevenueReport, path: str) -> None:
        """Export a RevenueReport to CSV."""
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value"])
            writer.writerow(["period", report.period])
            writer.writerow(["total_clicks", report.total_clicks])
            writer.writerow(["unique_clicks", report.unique_clicks])
            writer.writerow(["total_conversions", report.total_conversions])
            writer.writerow(["total_revenue_usd", report.total_revenue_usd])
            writer.writerow(["total_commission_usd", report.total_commission_usd])
            writer.writerow(["avg_order_value_usd", report.avg_order_value_usd])
            writer.writerow(["conversion_rate", report.conversion_rate])
            writer.writerow([])
            writer.writerow(["Top Products"])
            writer.writerow(["product_id", "revenue_usd"])
            for pid, rev in report.top_products:
                writer.writerow([pid, rev])
            writer.writerow([])
            writer.writerow(["Top Platforms"])
            writer.writerow(["platform", "revenue_usd"])
            for p, rev in report.top_platforms:
                writer.writerow([p, rev])
            writer.writerow([])
            writer.writerow(["Daily Breakdown"])
            writer.writerow(["day", "clicks", "conversions", "revenue"])
            for d in report.daily_breakdown:
                writer.writerow([
                    d.get("day", ""),
                    d.get("clicks", 0),
                    d.get("conversions", 0),
                    d.get("revenue", 0),
                ])

__all__ = [
    "RevenueReport",
    "AffiliateAnalytics",
]
