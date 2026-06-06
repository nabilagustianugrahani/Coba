"""Social media platform dispatcher.

Supports 16+ platforms via TikHub unified API (single API key) + Instagram via
instagrapi. Auto-detects platform from URL, manages sessions, and falls back
gracefully when a platform is unavailable.

TikHub docs: https://docs.tiktokhub.io
instagrapi: https://github.com/subzeroid/instagrapi
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from ugc_ai_overpower.integrations.base import (
    AccountInfo,
    EngagementMetrics,
    PlatformCategory,
    PlatformAdapter,
    PostResult,
    Region,
)
from ugc_ai_overpower.integrations.registry import get_adapter, register_adapter
from ugc_ai_overpower.integrations.session_manager import (
    Session,
    SessionManager,
    SessionStatus,
)
from ugc_ai_overpower.core.errors import ConfigError

log = logging.getLogger(__name__)


TIKHUB_BASE_URL = "https://api.tiktokhub.io/v2"


PLATFORMS_TIKHUB: dict[str, str] = {
    "tiktok": "tiktok",
    "douyin": "douyin",
    "instagram": "instagram",
    "youtube": "youtube",
    "twitter": "twitter",
    "x": "twitter",
    "threads": "threads",
    "linkedin": "linkedin",
    "reddit": "reddit",
    "pinterest": "pinterest",
    "xiaohongshu": "xiaohongshu",
    "bilibili": "bilibili",
    "weibo": "weibo",
    "kuaishou": "kuaishou",
}

PLATFORMS_INSTAGRAPI: set[str] = {"instagram"}
PLATFORMS_NATIVE: set[str] = {"facebook", "shopee", "tiktokshop", "lazada", "tokopedia"}


URL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("tiktok", re.compile(r"https?://(?:www\.)?tiktok\.com/@[\w.-]+/(?:video|photo)/(\d+)")),
    ("douyin", re.compile(r"https?://(?:www\.)?douyin\.com/video/(\d+)")),
    ("instagram", re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel)/([\w-]+)")),
    ("youtube", re.compile(r"https?://(?:www\.)?youtube\.com/(?:watch\?v=|shorts/)([\w-]+)")),
    ("twitter", re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[\w.-]+/status/(\d+)")),
    ("threads", re.compile(r"https?://(?:www\.)?threads\.net/@[\w.-]+/post/([\w-]+)")),
    ("linkedin", re.compile(r"https?://(?:www\.)?linkedin\.com/posts/[\w-]+-(\d+)")),
    ("reddit", re.compile(r"https?://(?:www\.)?reddit\.com/r/[\w]+/comments/(\w+)")),
    ("pinterest", re.compile(r"https?://(?:www\.)?pinterest\.com/pin/(\d+)")),
    ("xiaohongshu", re.compile(r"https?://(?:www\.)?xiaohongshu\.com/explore/(\w+)")),
    ("bilibili", re.compile(r"https?://(?:www\.)?bilibili\.com/video/([\w]+)")),
    ("weibo", re.compile(r"https?://(?:www\.)?weibo\.com/\d+/(\w+)")),
    ("kuaishou", re.compile(r"https?://(?:www\.)?kuaishou\.com/short-video/(\w+)")),
    ("facebook", re.compile(r"https?://(?:www\.)?facebook\.com/[\w.-]+/posts/(\d+)")),
]


def detect_platform(url: str) -> Optional[str]:
    if not url:
        return None
    url_lower = url.lower()
    for platform, pattern in URL_PATTERNS:
        if pattern.search(url_lower):
            return platform
    return None


@dataclass
class TikHubConfig:
    api_key: str = ""
    base_url: str = TIKHUB_BASE_URL
    timeout_sec: int = 30


@dataclass
class SocialDispatch:
    """Top-level social media dispatcher.

    Routes to:
      - TikHub (16 platforms via single API key)
      - instagrapi (Instagram with full session support)
      - Native (e-commerce platforms in ecom_dispatch.py)
    """
    tiktokhub_config: Optional[TikHubConfig] = None
    session_manager: Optional[SessionManager] = None
    use_instagrapi_for_instagram: bool = True

    def __post_init__(self) -> None:
        if self.tiktokhub_config is None:
            self.tiktokhub_config = TikHubConfig(
                api_key=os.environ.get("TIKHUB_API_KEY", ""),
            )
        if self.session_manager is None:
            self.session_manager = SessionManager()

    def is_configured(self) -> bool:
        return bool(self.tiktokhub_config and self.tiktokhub_config.api_key)

    def _require_tikhub(self) -> TikHubConfig:
        """Return the loaded TikHub config or raise :class:`ConfigError`.

        Centralises the ``is None`` guard so mypy sees the narrowed type and
        individual methods stay readable.
        """
        if self.tiktokhub_config is None:
            raise ConfigError("TikHub config not loaded")
        return self.tiktokhub_config

    def _require_session_manager(self) -> SessionManager:
        if self.session_manager is None:
            raise ConfigError("SessionManager not configured")
        return self.session_manager

    def supported_platforms(self) -> list[str]:
        out = sorted(PLATFORMS_TIKHUB.keys())
        out.extend(["shopee", "tiktokshop", "lazada", "tokopedia"])
        return sorted(set(out))

    async def post(
        self,
        platform: str,
        username: str,
        content: str,
        media_urls: Optional[list[str]] = None,
        hashtags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> PostResult:
        platform = platform.lower().strip()
        if platform not in self.supported_platforms():
            return PostResult(
                platform=platform,
                status="error",
                error=f"Unsupported platform. Supported: {self.supported_platforms()}",
            )
        if not self.is_configured():
            return PostResult(
                platform=platform,
                status="error",
                error="TikHub not configured. Set TIKHUB_API_KEY env var.",
            )
        session = self._require_session_manager().get(platform, username)
        if not session or session.status != SessionStatus.ACTIVE.value:
            return PostResult(
                platform=platform,
                status="error",
                error=f"No active session for {platform}/{username}. Import cookies first.",
            )
        log.info("social.post platform=%s user=%s content_len=%d",
                 platform, username, len(content))
        if platform == "instagram" and self.use_instagrapi_for_instagram:
            return await self._post_instagrapi(session, content, media_urls, hashtags, metadata)
        return await self._post_tikhub(platform, session, content, media_urls, hashtags, metadata)

    async def get_engagement(self, post_url: str) -> EngagementMetrics:
        platform = detect_platform(post_url)
        if not platform:
            return EngagementMetrics()
        if platform == "instagram" and self.use_instagrapi_for_instagram:
            return await self._engagement_instagrapi(post_url)
        return await self._engagement_tikhub(platform, post_url)

    async def get_account(self, platform: str, username: str) -> AccountInfo:
        platform = platform.lower().strip()
        if platform == "instagram" and self.use_instagrapi_for_instagram:
            return await self._account_instagrapi(username)
        return await self._account_tikhub(platform, username)

    async def _post_tikhub(
        self,
        platform: str,
        session: Session,
        content: str,
        media_urls: Optional[list[str]],
        hashtags: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
    ) -> PostResult:
        try:
            import aiohttp
        except ImportError as e:
            return PostResult(
                platform=platform,
                status="error",
                error="aiohttp not installed. Run: pip install aiohttp",
            )
        cfg = self._require_tikhub()
        endpoint = f"{cfg.base_url}/post/{PLATFORMS_TIKHUB.get(platform, platform)}/create"
        payload = {
            "content": content,
            "media_urls": media_urls or [],
            "hashtags": hashtags or [],
            "cookies": session.cookies,
            "user_agent": session.user_agent,
            "proxy": session.proxy,
            "metadata": metadata or {},
        }
        try:
            async with aiohttp.ClientSession() as http:
                async with http.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {cfg.api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": session.user_agent or "ugc-ai-overpower/1.0",
                    },
                    timeout=aiohttp.ClientTimeout(total=cfg.timeout_sec),
                ) as resp:
                    body = await resp.json()
                    if resp.status != 200:
                        return PostResult(
                            platform=platform,
                            status="error",
                            error=f"TikHub HTTP {resp.status}: {body}",
                        )
                    return PostResult(
                        platform=platform,
                        post_id=str(body.get("post_id", "")),
                        post_url=str(body.get("url", "")),
                        status="published",
                        raw=body,
                    )
        except Exception as e:
            log.error("tikhub post failed: %s", e)
            return PostResult(platform=platform, status="error", error=str(e))

    async def _engagement_tikhub(self, platform: str, post_url: str) -> EngagementMetrics:
        try:
            import aiohttp
        except ImportError:
            return EngagementMetrics()
        cfg = self._require_tikhub()
        endpoint = f"{cfg.base_url}/engagement/{PLATFORMS_TIKHUB.get(platform, platform)}/fetch"
        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(
                    endpoint,
                    params={"url": post_url},
                    headers={"Authorization": f"Bearer {cfg.api_key}"},
                    timeout=aiohttp.ClientTimeout(total=cfg.timeout_sec),
                ) as resp:
                    if resp.status != 200:
                        return EngagementMetrics()
                    body = await resp.json()
                    return EngagementMetrics(
                        views=int(body.get("views", 0)),
                        likes=int(body.get("likes", 0)),
                        comments=int(body.get("comments", 0)),
                        shares=int(body.get("shares", 0)),
                        saves=int(body.get("saves", 0)),
                        clicks=int(body.get("clicks", 0)),
                        engagement_score=float(body.get("engagement_score", 0.0)),
                        fetched_at=body.get("fetched_at", ""),
                    )
        except Exception as e:
            log.warning("tikhub engagement fetch failed: %s", e)
            return EngagementMetrics()

    async def _account_tikhub(self, platform: str, username: str) -> AccountInfo:
        try:
            import aiohttp
        except ImportError:
            return AccountInfo(platform=platform, username=username)
        cfg = self._require_tikhub()
        endpoint = f"{cfg.base_url}/user/{PLATFORMS_TIKHUB.get(platform, platform)}/info"
        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(
                    endpoint,
                    params={"username": username},
                    headers={"Authorization": f"Bearer {cfg.api_key}"},
                    timeout=aiohttp.ClientTimeout(total=cfg.timeout_sec),
                ) as resp:
                    if resp.status != 200:
                        return AccountInfo(platform=platform, username=username)
                    body = await resp.json()
                    return AccountInfo(
                        platform=platform,
                        username=username,
                        display_name=body.get("display_name", ""),
                        followers=int(body.get("followers", 0)),
                        following=int(body.get("following", 0)),
                        posts=int(body.get("posts", 0)),
                        verified=bool(body.get("verified", False)),
                        profile_url=body.get("profile_url", ""),
                        raw=body,
                    )
        except Exception as e:
            log.warning("tikhub account fetch failed: %s", e)
            return AccountInfo(platform=platform, username=username)

    async def _post_instagrapi(
        self,
        session: Session,
        content: str,
        media_urls: Optional[list[str]],
        hashtags: Optional[list[str]],
        metadata: Optional[dict[str, Any]],
    ) -> PostResult:
        try:
            from instagrapi import Client
        except ImportError as e:
            return PostResult(
                platform="instagram",
                status="error",
                error="instagrapi not installed. Run: pip install instagrapi",
            )
        try:
            cl = Client(session.local_settings) if hasattr(session, "local_settings") else Client()
            cl.set_settings({
                "cookies": session.cookies,
                "user_agent": session.user_agent,
                "device_id": session.device_id or session.fingerprint.get("device_id", ""),
            })
            if not cl.login_by_sessionid:
                if "sessionid" in session.cookies:
                    cl.login_by_sessionid(session.cookies["sessionid"])
            full_text = content
            if hashtags:
                full_text += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)
            if media_urls:
                media = await self._download_media(media_urls)
                if media:
                    media_path = media[0]
                    if any(p in media_path.lower() for p in [".mp4", ".mov"]):
                        media_pk = cl.video_upload(media_path, caption=full_text)
                    else:
                        media_pk = cl.photo_upload(media_path, caption=full_text)
                    return PostResult(
                        platform="instagram",
                        post_id=str(media_pk.pk),
                        post_url=f"https://instagram.com/p/{media_pk.code}/",
                        status="published",
                        raw={"pk": str(media_pk.pk), "code": media_pk.code},
                    )
            return PostResult(
                platform="instagram",
                status="error",
                error="Instagram via instagrapi requires media_urls",
            )
        except Exception as e:
            log.error("instagrapi post failed: %s", e)
            return PostResult(platform="instagram", status="error", error=str(e))

    async def _engagement_instagrapi(self, post_url: str) -> EngagementMetrics:
        try:
            from instagrapi import Client
            cl = Client()
            match = re.search(r"instagram\.com/(?:p|reel)/([\w-]+)", post_url)
            if not match:
                return EngagementMetrics()
            code = match.group(1)
            media = cl.media_pk_from_code(code)
            info = cl.media_info(media)
            return EngagementMetrics(
                views=getattr(info, "view_count", 0) or 0,
                likes=getattr(info, "like_count", 0) or 0,
                comments=getattr(info, "comment_count", 0) or 0,
                shares=0,
                saves=0,
                engagement_score=0.0,
                fetched_at=info.taken_at.isoformat() if hasattr(info, "taken_at") else "",
            )
        except Exception as e:
            log.warning("instagrapi engagement failed: %s", e)
            return EngagementMetrics()

    async def _account_instagrapi(self, username: str) -> AccountInfo:
        try:
            from instagrapi import Client
            cl = Client()
            user = cl.user_info_by_username(username)
            return AccountInfo(
                platform="instagram",
                username=username,
                display_name=user.full_name,
                followers=user.follower_count,
                following=user.following_count,
                posts=user.media_count,
                verified=user.is_verified,
                profile_url=f"https://instagram.com/{username}/",
                raw={"pk": str(user.pk)},
            )
        except Exception as e:
            log.warning("instagrapi account fetch failed: %s", e)
            return AccountInfo(platform="instagram", username=username)

    async def _download_media(self, urls: list[str]) -> list[str]:
        import tempfile
        paths: list[str] = []
        try:
            import aiohttp
        except ImportError:
            return paths
        try:
            async with aiohttp.ClientSession() as http:
                for url in urls[:4]:
                    async with http.get(url) as resp:
                        if resp.status == 200:
                            suffix = ".mp4" if ".mp4" in url.lower() else ".jpg"
                            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                                f.write(await resp.read())
                                paths.append(f.name)
        except Exception as e:
            log.warning("media download failed: %s", e)
        return paths


__all__ = [
    "SocialDispatch",
    "TikHubConfig",
    "PLATFORMS_TIKHUB",
    "PLATFORMS_INSTAGRAPI",
    "PLATFORMS_NATIVE",
    "URL_PATTERNS",
    "detect_platform",
]
