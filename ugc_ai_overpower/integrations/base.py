"""Integration adapter framework.

Base class + registry for all social media and e-commerce platform adapters.
Heavy work (scraping, API calls, video processing) runs in codespace — VPS
just dispatches and aggregates results.

Design principles:
  - One abstract base class, many concrete adapters
  - Auto-discovery via registry
  - All heavy operations marked @remote (runs in codespace)
  - VPS never blocks on network IO longer than 5s
  - Graceful degradation: if remote fails, use cached/fallback data
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

log = logging.getLogger(__name__)


class PlatformCategory(str, Enum):
    SOCIAL = "social"
    ECOMMERCE = "ecommerce"
    MESSAGING = "messaging"


class Region(str, Enum):
    INDONESIA = "id"
    GLOBAL = "global"
    SEA = "sea"


@dataclass
class EngagementMetrics:
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    clicks: int = 0
    engagement_score: float = 0.0
    fetched_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PostResult:
    platform: str
    post_id: str = ""
    post_url: str = ""
    status: str = ""
    error: Optional[str] = None
    published_at: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AccountInfo:
    platform: str
    username: str = ""
    display_name: str = ""
    followers: int = 0
    following: int = 0
    posts: int = 0
    verified: bool = False
    profile_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AffiliateLink:
    platform: str
    product_id: str
    original_url: str
    affiliate_url: str = ""
    commission_rate: float = 0.0
    short_url: str = ""
    expires_at: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlatformAdapter(ABC):
    """Abstract base for all platform adapters.

    Subclasses MUST implement the abstract methods. Heavy methods (anything
    that makes network calls or does CPU-intensive work) should be marked
    with @remote so the dispatcher routes them to codespace.
    """

    platform: str = ""
    category: PlatformCategory = PlatformCategory.SOCIAL
    region: Region = Region.INDONESIA
    requires_auth: bool = True

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._client: Any = None

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required env vars/credentials are present."""
        ...

    @abstractmethod
    async def post(self, content: str, media_urls: list[str] = None,
                   metadata: dict[str, Any] = None) -> PostResult:
        """Publish content to the platform. Heavy — runs in codespace."""
        ...

    @abstractmethod
    async def get_engagement(self, post_url: str) -> EngagementMetrics:
        """Fetch real engagement metrics. Heavy — runs in codespace."""
        ...

    @abstractmethod
    async def get_account(self, username: str = "") -> AccountInfo:
        """Get account info. Heavy — runs in codespace."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Lightweight check. Runs on VPS."""
        return {
            "platform": self.platform,
            "configured": self.is_configured(),
            "category": self.category.value,
            "region": self.region.value,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "category": self.category.value,
            "region": self.region.value,
            "configured": self.is_configured(),
        }
