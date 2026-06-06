"""Affiliate link tracking and revenue attribution.

Tracks affiliate links, click events, and conversion events with
SQLite-backed storage. Generates short codes (base62) for link
shortening and builds redirect URLs for the ugc.ai domain.

Typical usage:
    tracker = AffiliateTracker("affiliate.db")
    link = tracker.create_link("prod-1", "shopee", "https://shopee.com/p", "aff-123")
    click = tracker.record_click(link.short_code, "Mozilla/5.0", "192.168.1.1", "https://google.com")
    conv = tracker.record_conversion(click.click_id, "ORD-001", 29.99, 2.99)
    print(tracker.get_total_revenue(link.link_id))
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _ulid() -> str:
    """Generate a ULID-like ID (26 chars, sortable, URL-safe)."""
    ts = int(time.time() * 1000)
    rand = uuid.uuid4().hex[:16]
    return f"{ts:012x}{rand}"


def _short_code(length: int = 6) -> str:
    """Generate a random base62 short code."""
    n = int.from_bytes(uuid.uuid4().bytes, "big")
    code = ""
    for _ in range(length):
        n, rem = divmod(n, 62)
        code = BASE62[rem] + code
    return code


def _hash_ip(ip: str) -> str:
    """SHA256 hash of IP for privacy."""
    return hashlib.sha256(ip.encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AffiliateLink:
    """An affiliate link with tracking metadata.

    Attributes:
        link_id: Auto-generated ULID.
        product_id: Product identifier from the product catalog.
        platform: E-commerce platform (shopee, tokopedia, tiktok_shop, lazada, bukalapak).
        base_url: Original product URL before affiliate params.
        affiliate_id: Creator/affiliate's identifier on the platform.
        short_code: 6-char base62 code used in redirect URLs.
        utm_source: UTM source parameter (default: "ugc").
        utm_medium: UTM medium parameter (default: "social").
        utm_campaign: UTM campaign identifier.
        utm_content: UTM content (typically content_id).
        created_at: ISO-8601 timestamp of creation.
        expires_at: Optional ISO-8601 expiration timestamp.
        metadata: Arbitrary key-value metadata dict.
    """
    link_id: str = ""
    product_id: str = ""
    platform: str = ""
    base_url: str = ""
    affiliate_id: str = ""
    short_code: str = ""
    utm_source: str = "ugc"
    utm_medium: str = "social"
    utm_campaign: str = ""
    utm_content: str = ""
    created_at: str = ""
    expires_at: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClickEvent:
    """A click on an affiliate link.

    Attributes:
        click_id: Auto-generated ULID.
        link_id: FK to AffiliateLink.link_id.
        timestamp: ISO-8601 timestamp.
        user_agent: Raw User-Agent string.
        ip_hash: SHA256 hash of visitor IP (privacy-safe).
        referrer: HTTP Referrer header.
        country: GeoIP country code (optional, populated async).
        device_type: Derived device type (optional).
    """
    click_id: str = ""
    link_id: str = ""
    timestamp: str = ""
    user_agent: str = ""
    ip_hash: str = ""
    referrer: str = ""
    country: str = ""
    device_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConversionEvent:
    """A conversion (sale) attributed to a click on an affiliate link.

    Attributes:
        conversion_id: Auto-generated ULID.
        link_id: FK to AffiliateLink.link_id.
        click_id: FK to ClickEvent.click_id.
        timestamp: ISO-8601 timestamp.
        order_id: Platform order ID.
        order_value_usd: Total order value in USD.
        commission_usd: Affiliate commission earned in USD.
        platform: E-commerce platform.
        product_id: Product identifier.
    """
    conversion_id: str = ""
    link_id: str = ""
    click_id: str = ""
    timestamp: str = ""
    order_id: str = ""
    order_value_usd: float = 0.0
    commission_usd: float = 0.0
    platform: str = ""
    product_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AffiliateTracker:
    """SQLite-backed affiliate link tracker with click + conversion attribution."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS affiliate_links (
                link_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                base_url TEXT NOT NULL,
                affiliate_id TEXT NOT NULL,
                short_code TEXT UNIQUE NOT NULL,
                utm_source TEXT DEFAULT 'ugc',
                utm_medium TEXT DEFAULT 'social',
                utm_campaign TEXT DEFAULT '',
                utm_content TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                expires_at TEXT,
                metadata TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS click_events (
                click_id TEXT PRIMARY KEY,
                link_id TEXT NOT NULL REFERENCES affiliate_links(link_id),
                timestamp TEXT NOT NULL,
                user_agent TEXT NOT NULL,
                ip_hash TEXT NOT NULL,
                referrer TEXT DEFAULT '',
                country TEXT DEFAULT '',
                device_type TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS conversion_events (
                conversion_id TEXT PRIMARY KEY,
                link_id TEXT NOT NULL REFERENCES affiliate_links(link_id),
                click_id TEXT NOT NULL REFERENCES click_events(click_id),
                timestamp TEXT NOT NULL,
                order_id TEXT NOT NULL,
                order_value_usd REAL NOT NULL,
                commission_usd REAL NOT NULL,
                platform TEXT DEFAULT '',
                product_id TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_clicks_link ON click_events(link_id);
            CREATE INDEX IF NOT EXISTS idx_clicks_time ON click_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_conversions_link ON conversion_events(link_id);
            CREATE INDEX IF NOT EXISTS idx_conversions_click ON conversion_events(click_id);
            CREATE INDEX IF NOT EXISTS idx_conversions_time ON conversion_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_links_short ON affiliate_links(short_code);
        """)
        self._conn.commit()

    def create_link(
        self,
        product_id: str,
        platform: str,
        base_url: str,
        affiliate_id: str,
        **utm: Any,
    ) -> AffiliateLink:
        """Create a new affiliate link with auto-generated ID and short code."""
        link = AffiliateLink(
            link_id=_ulid(),
            product_id=product_id,
            platform=platform,
            base_url=base_url,
            affiliate_id=affiliate_id,
            short_code=_short_code(),
            utm_source=str(utm.get("utm_source", "ugc")),
            utm_medium=str(utm.get("utm_medium", "social")),
            utm_campaign=str(utm.get("utm_campaign", "")),
            utm_content=str(utm.get("utm_content", "")),
            created_at=_now(),
            expires_at=utm.get("expires_at"),
            metadata=utm.get("metadata", {}),
        )
        cur = self._conn.cursor()
        cur.execute(
            """INSERT INTO affiliate_links
               (link_id, product_id, platform, base_url, affiliate_id,
                short_code, utm_source, utm_medium, utm_campaign, utm_content,
                created_at, expires_at, metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                link.link_id, link.product_id, link.platform, link.base_url,
                link.affiliate_id, link.short_code, link.utm_source, link.utm_medium,
                link.utm_campaign, link.utm_content, link.created_at, link.expires_at,
                json.dumps(link.metadata),
            ),
        )
        self._conn.commit()
        return link

    def _row_to_link(self, row: sqlite3.Row) -> AffiliateLink:
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        return AffiliateLink(**d)

    def get_link(self, link_id: str) -> Optional[AffiliateLink]:
        """Get an affiliate link by its link_id."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM affiliate_links WHERE link_id = ?", (link_id,))
        row = cur.fetchone()
        return self._row_to_link(row) if row else None

    def get_link_by_short(self, short_code: str) -> Optional[AffiliateLink]:
        """Get an affiliate link by its short code."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM affiliate_links WHERE short_code = ?", (short_code,))
        row = cur.fetchone()
        return self._row_to_link(row) if row else None

    def list_links(
        self,
        product_id: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> list[AffiliateLink]:
        """List affiliate links, optionally filtered by product_id or platform."""
        query = "SELECT * FROM affiliate_links"
        params: list[str] = []
        conditions: list[str] = []
        if product_id:
            conditions.append("product_id = ?")
            params.append(product_id)
        if platform:
            conditions.append("platform = ?")
            params.append(platform)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        cur = self._conn.cursor()
        cur.execute(query, params)
        return [self._row_to_link(row) for row in cur.fetchall()]

    def delete_link(self, link_id: str) -> bool:
        """Delete an affiliate link by link_id. Returns True if deleted."""
        cur = self._conn.cursor()
        cur.execute("DELETE FROM affiliate_links WHERE link_id = ?", (link_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def build_redirect_url(self, link: AffiliateLink) -> str:
        """Build the ugc.ai redirect URL for an affiliate link."""
        return f"https://ugc.ai/r/{link.short_code}"

    def record_click(
        self,
        short_code: str,
        user_agent: str,
        ip: str,
        referrer: str,
    ) -> Optional[ClickEvent]:
        """Record a click event for a short code. Returns ClickEvent or None."""
        link = self.get_link_by_short(short_code)
        if not link:
            return None
        event = ClickEvent(
            click_id=_ulid(),
            link_id=link.link_id,
            timestamp=_now(),
            user_agent=user_agent,
            ip_hash=_hash_ip(ip),
            referrer=referrer,
        )
        cur = self._conn.cursor()
        cur.execute(
            """INSERT INTO click_events
               (click_id, link_id, timestamp, user_agent, ip_hash, referrer)
               VALUES (?,?,?,?,?,?)""",
            (event.click_id, event.link_id, event.timestamp,
             event.user_agent, event.ip_hash, event.referrer),
        )
        self._conn.commit()
        return event

    def record_conversion(
        self,
        click_id: str,
        order_id: str,
        order_value_usd: float,
        commission_usd: float,
    ) -> Optional[ConversionEvent]:
        """Record a conversion attributed to a click. Returns ConversionEvent or None."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM click_events WHERE click_id = ?", (click_id,))
        click = cur.fetchone()
        if not click:
            return None
        click_dict = dict(click)
        event = ConversionEvent(
            conversion_id=_ulid(),
            link_id=click_dict["link_id"],
            click_id=click_id,
            timestamp=_now(),
            order_id=order_id,
            order_value_usd=order_value_usd,
            commission_usd=commission_usd,
            platform=click_dict.get("platform", ""),
            product_id="",
        )
        # Look up link for platform/product info
        cur.execute("SELECT * FROM affiliate_links WHERE link_id = ?",
                     (click_dict["link_id"],))
        link = cur.fetchone()
        if link:
            link_dict = dict(link)
            event.platform = link_dict.get("platform", "")
            event.product_id = link_dict.get("product_id", "")

        cur.execute(
            """INSERT INTO conversion_events
               (conversion_id, link_id, click_id, timestamp, order_id,
                order_value_usd, commission_usd, platform, product_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (event.conversion_id, event.link_id, event.click_id,
             event.timestamp, event.order_id, event.order_value_usd,
             event.commission_usd, event.platform, event.product_id),
        )
        self._conn.commit()
        return event

    def get_clicks_for_link(self, link_id: str, days: int = 30) -> list[ClickEvent]:
        """Get all click events for a link within the last N days."""
        cur = self._conn.cursor()
        cur.execute(
            """SELECT * FROM click_events
               WHERE link_id = ? AND timestamp >= datetime('now', ?)
               ORDER BY timestamp DESC""",
            (link_id, f"-{days} days"),
        )
        return [ClickEvent(**dict(r)) for r in cur.fetchall()]

    def get_conversions_for_link(self, link_id: str) -> list[ConversionEvent]:
        """Get all conversion events for a link."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM conversion_events WHERE link_id = ? ORDER BY timestamp DESC",
            (link_id,),
        )
        return [ConversionEvent(**dict(r)) for r in cur.fetchall()]

    def get_total_revenue(
        self, link_id: Optional[str] = None, days: int = 30,
    ) -> float:
        """Get total order value (revenue) optionally filtered by link and time window."""
        if link_id:
            cur = self._conn.cursor()
            cur.execute(
                """SELECT COALESCE(SUM(order_value_usd), 0) FROM conversion_events
                   WHERE link_id = ? AND timestamp >= datetime('now', ?)""",
                (link_id, f"-{days} days"),
            )
        else:
            cur = self._conn.cursor()
            cur.execute(
                """SELECT COALESCE(SUM(order_value_usd), 0) FROM conversion_events
                   WHERE timestamp >= datetime('now', ?)""",
                (f"-{days} days",),
            )
        return round(float(cur.fetchone()[0]), 2)

    def get_total_commission(
        self, link_id: Optional[str] = None, days: int = 30,
    ) -> float:
        """Get total commission earned optionally filtered by link and time window."""
        if link_id:
            cur = self._conn.cursor()
            cur.execute(
                """SELECT COALESCE(SUM(commission_usd), 0) FROM conversion_events
                   WHERE link_id = ? AND timestamp >= datetime('now', ?)""",
                (link_id, f"-{days} days"),
            )
        else:
            cur = self._conn.cursor()
            cur.execute(
                """SELECT COALESCE(SUM(commission_usd), 0) FROM conversion_events
                   WHERE timestamp >= datetime('now', ?)""",
                (f"-{days} days",),
            )
        return round(float(cur.fetchone()[0]), 2)

    def get_conversion_rate(self, link_id: str) -> float:
        """Get conversion rate (conversions / clicks) for a link."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM click_events WHERE link_id = ?", (link_id,),
        )
        clicks = float(cur.fetchone()[0])
        if clicks == 0:
            return 0.0
        cur.execute(
            "SELECT COUNT(*) FROM conversion_events WHERE link_id = ?", (link_id,),
        )
        conversions = float(cur.fetchone()[0])
        return round(conversions / clicks, 4)

    def get_top_links(
        self, metric: str = "revenue", limit: int = 10,
    ) -> list[tuple[AffiliateLink, float]]:
        """Get top-performing links by revenue or commission."""
        col = "order_value_usd" if metric == "revenue" else "commission_usd"
        cur = self._conn.cursor()
        cur.execute(
            f"""SELECT link_id, COALESCE(SUM({col}), 0) AS total
                FROM conversion_events
                GROUP BY link_id
                ORDER BY total DESC
                LIMIT ?""",
            (limit,),
        )
        results: list[tuple[AffiliateLink, float]] = []
        for row in cur.fetchall():
            link = self.get_link(row["link_id"])
            if link:
                results.append((link, round(float(row["total"]), 2)))
        return results

    def close(self) -> None:
        self._conn.close()


__all__ = [
    "AffiliateLink",
    "ClickEvent",
    "ConversionEvent",
    "AffiliateTracker",
]
