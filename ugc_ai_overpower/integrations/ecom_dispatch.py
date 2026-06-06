"""E-commerce platform dispatcher.

Supports Indonesian + SEA e-commerce affiliate programs:
  - Shopee Affiliate API (Open Platform)
  - TikTok Shop Affiliate API
  - Lazada Affiliate API (via Lazada Open Platform)
  - Tokopedia (TikTok Shop by Tokopedia since 2024)

Caches affiliate links in SQLite for 24h to avoid redundant API calls.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional

from ugc_ai_overpower.integrations.base import (
    AccountInfo,
    AffiliateLink,
    EngagementMetrics,
    PlatformCategory,
    PlatformAdapter,
    PostResult,
    Region,
)
from ugc_ai_overpower.integrations.session_manager import Session, SessionManager
from ugc_ai_overpower.core.errors import ConfigError

log = logging.getLogger(__name__)


SHOPEE_BASE_URL = "https://open-api.affiliate.shopee.co.id/graphql"
TIKTOKSHOP_BASE_URL = "https://open-api.tiktokglobalshop.com"
LAZADA_BASE_URL = "https://api.lazada.co.id/rest"
TOKOPEDIA_BASE_URL = "https://affiliate.tokopedia.com/api/v1"


DEFAULT_CACHE_PATH = Path.home() / ".9router" / "ecom_cache.db"
CACHE_TTL_HOURS = 24


@dataclass
class EcomConfig:
    shopee_affiliate_id: str = ""
    shopee_affiliate_token: str = ""
    tiktokshop_app_key: str = ""
    tiktokshop_app_secret: str = ""
    tiktokshop_access_token: str = ""
    lazada_app_key: str = ""
    lazada_app_secret: str = ""
    lazada_access_token: str = ""
    tokopedia_affiliate_id: str = ""
    tokopedia_affiliate_token: str = ""
    timeout_sec: int = 30


class AffiliateCache:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or DEFAULT_CACHE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
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
                CREATE TABLE IF NOT EXISTS affiliate_links (
                    platform TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    original_url TEXT NOT NULL,
                    affiliate_url TEXT,
                    commission_rate REAL,
                    short_url TEXT,
                    expires_at TEXT,
                    fetched_at TEXT NOT NULL,
                    raw TEXT,
                    PRIMARY KEY (platform, product_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON affiliate_links(expires_at)")
            conn.commit()

    def get(self, platform: str, product_id: str) -> Optional[AffiliateLink]:
        with self._lock:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM affiliate_links WHERE platform=? AND product_id=?",
                    (platform, product_id),
                ).fetchone()
                if not row:
                    return None
                expires_at = row["expires_at"] or ""
                if expires_at:
                    try:
                        exp = datetime.fromisoformat(expires_at)
                        if datetime.now(timezone.utc) > exp.replace(tzinfo=timezone.utc):
                            return None
                    except Exception:
                        pass
                raw = json.loads(row["raw"]) if row["raw"] else {}
                return AffiliateLink(
                    platform=platform,
                    product_id=product_id,
                    original_url=row["original_url"],
                    affiliate_url=row["affiliate_url"] or "",
                    commission_rate=row["commission_rate"] or 0.0,
                    short_url=row["short_url"] or "",
                    expires_at=expires_at,
                    raw=raw,
                )

    def put(self, link: AffiliateLink) -> None:
        with self._lock:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO affiliate_links
                    (platform, product_id, original_url, affiliate_url, commission_rate, short_url, expires_at, fetched_at, raw)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        link.platform, link.product_id, link.original_url,
                        link.affiliate_url, link.commission_rate, link.short_url,
                        link.expires_at or "",
                        datetime.now(timezone.utc).isoformat(),
                        json.dumps(link.raw),
                    ),
                )
                conn.commit()

    def cleanup_expired(self) -> int:
        count = 0
        with self._lock:
            with self._conn() as conn:
                now = datetime.now(timezone.utc).isoformat()
                cur = conn.execute(
                    "DELETE FROM affiliate_links WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (now,),
                )
                count = cur.rowcount
        return count

    def stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as total, COUNT(DISTINCT platform) as platforms FROM affiliate_links"
            ).fetchone()
        return {"total": row["total"], "platforms": row["platforms"]}


@dataclass
class EcomDispatch:
    config: Optional[EcomConfig] = None
    cache: Optional[AffiliateCache] = None
    session_manager: Optional[SessionManager] = None

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = EcomConfig(
                shopee_affiliate_id=os.environ.get("SHOPEE_AFFILIATE_ID", ""),
                shopee_affiliate_token=os.environ.get("SHOPEE_AFFILIATE_TOKEN", ""),
                tiktokshop_app_key=os.environ.get("TIKTOKSHOP_APP_KEY", ""),
                tiktokshop_app_secret=os.environ.get("TIKTOKSHOP_APP_SECRET", ""),
                tiktokshop_access_token=os.environ.get("TIKTOKSHOP_ACCESS_TOKEN", ""),
                lazada_app_key=os.environ.get("LAZADA_APP_KEY", ""),
                lazada_app_secret=os.environ.get("LAZADA_APP_SECRET", ""),
                lazada_access_token=os.environ.get("LAZADA_ACCESS_TOKEN", ""),
                tokopedia_affiliate_id=os.environ.get("TOKOPEDIA_AFFILIATE_ID", ""),
                tokopedia_affiliate_token=os.environ.get("TOKOPEDIA_AFFILIATE_TOKEN", ""),
            )
        if self.cache is None:
            self.cache = AffiliateCache()
        if self.session_manager is None:
            self.session_manager = SessionManager()

    def _require_config(self) -> EcomConfig:
        """Return the loaded EcomConfig or raise :class:`ConfigError`."""
        if self.config is None:
            raise ConfigError("Ecom config not loaded")
        return self.config

    def _require_cache(self) -> "AffiliateCache":
        if self.cache is None:
            raise ConfigError("Affiliate cache not initialised")
        return self.cache

    def is_configured(self, platform: str) -> bool:
        cfg = self.config
        platform = platform.lower()
        if cfg is None:
            return False
        if platform == "shopee":
            return bool(cfg.shopee_affiliate_id and cfg.shopee_affiliate_token)
        if platform == "tiktokshop":
            return bool(cfg.tiktokshop_app_key and cfg.tiktokshop_access_token)
        if platform == "lazada":
            return bool(cfg.lazada_app_key and cfg.lazada_access_token)
        if platform == "tokopedia":
            return bool(cfg.tokopedia_affiliate_id and cfg.tokopedia_affiliate_token)
        return False

    def configured_platforms(self) -> list[str]:
        return [p for p in ["shopee", "tiktokshop", "lazada", "tokopedia"] if self.is_configured(p)]

    async def get_affiliate_link(
        self,
        platform: str,
        product_id: str,
        original_url: str,
        sub_id: str = "",
        force_refresh: bool = False,
    ) -> AffiliateLink:
        platform = platform.lower().strip()
        if not self.is_configured(platform):
            return AffiliateLink(
                platform=platform,
                product_id=product_id,
                original_url=original_url,
                error=f"Platform {platform} not configured. Check env vars.",
            )
        if not force_refresh:
            cached = self._require_cache().get(platform, product_id)
            if cached:
                log.debug("ecom.cache.hit platform=%s product=%s", platform, product_id)
                return cached
        if platform == "shopee":
            link = await self._shopee_link(product_id, original_url, sub_id)
        elif platform == "tiktokshop":
            link = await self._tiktokshop_link(product_id, original_url, sub_id)
        elif platform == "lazada":
            link = await self._lazada_link(product_id, original_url, sub_id)
        elif platform == "tokopedia":
            link = await self._tokopedia_link(product_id, original_url, sub_id)
        else:
            link = AffiliateLink(
                platform=platform, product_id=product_id, original_url=original_url,
                error=f"Platform {platform} not supported",
            )
        if link.affiliate_url:
            self._require_cache().put(link)
        return link

    async def get_affiliate_links_batch(
        self,
        platform: str,
        items: list[dict[str, str]],
    ) -> list[AffiliateLink]:
        out: list[AffiliateLink] = []
        for item in items:
            link = await self.get_affiliate_link(
                platform=platform,
                product_id=item["product_id"],
                original_url=item["original_url"],
                sub_id=item.get("sub_id", ""),
            )
            out.append(link)
        return out

    async def _shopee_link(self, product_id: str, original_url: str,
                           sub_id: str) -> AffiliateLink:
        try:
            import aiohttp
        except ImportError as e:
            return AffiliateLink(
                platform="shopee", product_id=product_id, original_url=original_url,
                error="aiohttp not installed",
            )
        query = """
        query generateShortLink($affiliateId: Int!, $productId: Int!) {
          generateShortLink(input: {
            affiliateId: $affiliateId
            productIdList: [$productId]
          }) {
            shortLinkList {
              productId
              shortLink
            }
            errorMsg
          }
        }
        """
        try:
            cfg = self._require_config()
            async with aiohttp.ClientSession() as http:
                async with http.post(
                    SHOPEE_BASE_URL,
                    json={
                        "query": query,
                        "variables": {
                            "affiliateId": int(cfg.shopee_affiliate_id),
                            "productId": int(product_id),
                        },
                    },
                    headers={
                        "Authorization": f"Bearer {cfg.shopee_affiliate_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=cfg.timeout_sec),
                ) as resp:
                    body = await resp.json()
                    if resp.status != 200:
                        return AffiliateLink(
                            platform="shopee", product_id=product_id,
                            original_url=original_url, error=f"HTTP {resp.status}",
                            raw=body,
                        )
                    data = (body.get("data") or {}).get("generateShortLink") or {}
                    short_list = data.get("shortLinkList") or []
                    if not short_list:
                        err = data.get("errorMsg") or "no shortlink returned"
                        return AffiliateLink(
                            platform="shopee", product_id=product_id,
                            original_url=original_url, error=err, raw=body,
                        )
                    short_url = short_list[0].get("shortLink", "")
                    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                    return AffiliateLink(
                        platform="shopee", product_id=product_id,
                        original_url=original_url, affiliate_url=short_url,
                        short_url=short_url, expires_at=expires,
                        commission_rate=self._shopee_commission(product_id),
                        raw=body,
                    )
        except Exception as e:
            log.error("shopee link failed: %s", e)
            return AffiliateLink(
                platform="shopee", product_id=product_id,
                original_url=original_url, error=str(e),
            )

    def _shopee_commission(self, product_id: str) -> float:
        return 0.05

    async def _tiktokshop_link(self, product_id: str, original_url: str,
                                sub_id: str) -> AffiliateLink:
        try:
            import aiohttp
        except ImportError as e:
            return AffiliateLink(
                platform="tiktokshop", product_id=product_id, original_url=original_url,
                error="aiohttp not installed",
            )
        url = f"{TIKTOKSHOP_BASE_URL}/affiliate/202407/shop/affiliate_links"
        params = {
            "shop_cipher": product_id,
            "sub_id": sub_id or "",
        }
        try:
            cfg = self._require_config()
            async with aiohttp.ClientSession() as http:
                async with http.get(
                    url,
                    params=params,
                    headers={
                        "x-tts-access-token": cfg.tiktokshop_access_token,
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=cfg.timeout_sec),
                ) as resp:
                    body = await resp.json()
                    if resp.status != 200:
                        return AffiliateLink(
                            platform="tiktokshop", product_id=product_id,
                            original_url=original_url, error=f"HTTP {resp.status}", raw=body,
                        )
                    data = body.get("data") or {}
                    aff_url = data.get("affiliate_link") or ""
                    commission = float(data.get("commission_rate", 0.0) or 0.0)
                    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                    return AffiliateLink(
                        platform="tiktokshop", product_id=product_id,
                        original_url=original_url, affiliate_url=aff_url,
                        short_url=aff_url, expires_at=expires,
                        commission_rate=commission, raw=body,
                    )
        except Exception as e:
            log.error("tiktokshop link failed: %s", e)
            return AffiliateLink(
                platform="tiktokshop", product_id=product_id,
                original_url=original_url, error=str(e),
            )

    async def _lazada_link(self, product_id: str, original_url: str,
                            sub_id: str) -> AffiliateLink:
        try:
            import aiohttp
        except ImportError as e:
            return AffiliateLink(
                platform="lazada", product_id=product_id, original_url=original_url,
                error="aiohttp not installed",
            )
        import time as _t
        cfg = self._require_config()
        params = {
            "app_key": cfg.lazada_app_key,
            "access_token": cfg.lazada_access_token,
            "timestamp": str(int(_t.time() * 1000)),
            "product_id": product_id,
            "sub_id": sub_id or "",
            "format": "json",
            "v": "2.0",
            "sign_method": "sha256",
        }
        params["sign"] = self._lazada_sign(params)
        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(
                    f"{LAZADA_BASE_URL}/affiliate/link/generate",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=cfg.timeout_sec),
                ) as resp:
                    body = await resp.json()
                    if resp.status != 200:
                        return AffiliateLink(
                            platform="lazada", product_id=product_id,
                            original_url=original_url, error=f"HTTP {resp.status}", raw=body,
                        )
                    data = body.get("data") or {}
                    aff_url = data.get("affiliate_url") or data.get("short_url") or ""
                    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                    return AffiliateLink(
                        platform="lazada", product_id=product_id,
                        original_url=original_url, affiliate_url=aff_url,
                        short_url=aff_url, expires_at=expires,
                        commission_rate=0.05, raw=body,
                    )
        except Exception as e:
            log.error("lazada link failed: %s", e)
            return AffiliateLink(
                platform="lazada", product_id=product_id,
                original_url=original_url, error=str(e),
            )

    def _lazada_sign(self, params: dict[str, str]) -> str:
        import hmac
        import hashlib
        sorted_keys = sorted(params.keys())
        msg = "".join(f"{k}{params[k]}" for k in sorted_keys)
        return hmac.new(
            self._require_config().lazada_app_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()

    async def _tokopedia_link(self, product_id: str, original_url: str,
                                sub_id: str) -> AffiliateLink:
        try:
            import aiohttp
        except ImportError as e:
            return AffiliateLink(
                platform="tokopedia", product_id=product_id, original_url=original_url,
                error="aiohttp not installed",
            )
        try:
            cfg = self._require_config()
            async with aiohttp.ClientSession() as http:
                async with http.get(
                    f"{TOKOPEDIA_BASE_URL}/link/generate",
                    params={
                        "aff_id": cfg.tokopedia_affiliate_id,
                        "product_id": product_id,
                        "sub_id": sub_id or "",
                    },
                    headers={
                        "Authorization": f"Bearer {cfg.tokopedia_affiliate_token}",
                    },
                    timeout=aiohttp.ClientTimeout(total=cfg.timeout_sec),
                ) as resp:
                    body = await resp.json()
                    if resp.status != 200:
                        return AffiliateLink(
                            platform="tokopedia", product_id=product_id,
                            original_url=original_url, error=f"HTTP {resp.status}", raw=body,
                        )
                    data = body.get("data") or {}
                    aff_url = data.get("affiliate_link") or ""
                    return AffiliateLink(
                        platform="tokopedia", product_id=product_id,
                        original_url=original_url, affiliate_url=aff_url,
                        short_url=aff_url, expires_at="",
                        commission_rate=0.06, raw=body,
                    )
        except Exception as e:
            log.error("tokopedia link failed: %s", e)
            return AffiliateLink(
                platform="tokopedia", product_id=product_id,
                original_url=original_url, error=str(e),
            )

    def summary(self) -> dict[str, Any]:
        return {
            "configured_platforms": self.configured_platforms(),
            "cache_stats": self._require_cache().stats(),
            "config_status": {
                p: self.is_configured(p)
                for p in ["shopee", "tiktokshop", "lazada", "tokopedia"]
            },
        }


__all__ = [
    "EcomConfig",
    "EcomDispatch",
    "AffiliateCache",
    "DEFAULT_CACHE_PATH",
    "CACHE_TTL_HOURS",
    "SHOPEE_BASE_URL",
    "TIKTOKSHOP_BASE_URL",
    "LAZADA_BASE_URL",
    "TOKOPEDIA_BASE_URL",
]
