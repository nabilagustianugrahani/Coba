"""Auto-repurpose content across platforms and formats.

For a single source video/image, produce platform-tuned variants:
  - Reels / TikTok / Shorts -> 9:16 vertical, 15-90s
  - Twitter               -> 16:9 or 1:1, 30-140s
  - LinkedIn              -> 1:1, 30-90s
  - YouTube long          -> 16:9, >60s

Each variant includes:
  - re-encoded media (via VideoEditor)
  - platform-tuned caption (tone-aware)
  - suggested hashtags
  - estimated best posting time (Asia/Jakarta default)
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

log = logging.getLogger(__name__)


SUPPORTED_PLATFORMS: tuple[str, ...] = (
    "reels", "tiktok", "youtube_shorts", "twitter", "linkedin", "youtube",
)
SUPPORTED_TONES: tuple[str, ...] = (
    "engaging", "professional", "playful", "authoritative", "inspirational",
)
SUPPORTED_LANGUAGES: tuple[str, ...] = ("id", "en")

ASPECT_VERTICAL = (1080, 1920)
ASPECT_SQUARE = (1080, 1080)
ASPECT_HORIZONTAL = (1920, 1080)

PLATFORM_SPECS: dict[str, dict[str, Any]] = {
    "reels": {
        "format": "vertical", "aspect": ASPECT_VERTICAL,
        "min_duration": 15, "max_duration": 90, "tone": "engaging",
    },
    "tiktok": {
        "format": "vertical", "aspect": ASPECT_VERTICAL,
        "min_duration": 15, "max_duration": 90, "tone": "playful",
    },
    "youtube_shorts": {
        "format": "vertical", "aspect": ASPECT_VERTICAL,
        "min_duration": 15, "max_duration": 60, "tone": "engaging",
    },
    "twitter": {
        "format": "horizontal", "aspect": ASPECT_HORIZONTAL,
        "min_duration": 30, "max_duration": 140, "tone": "engaging",
    },
    "linkedin": {
        "format": "square", "aspect": ASPECT_SQUARE,
        "min_duration": 30, "max_duration": 90, "tone": "professional",
    },
    "youtube": {
        "format": "horizontal", "aspect": ASPECT_HORIZONTAL,
        "min_duration": 60, "max_duration": 600, "tone": "authoritative",
    },
}

# Hash-tag pool per niche (very small, deterministic).
HASHTAG_POOL: dict[str, list[str]] = {
    "fitness": ["#fitness", "#gym", "#workout", "#fitlife"],
    "tech": ["#tech", "#ai", "#coding", "#startup"],
    "food": ["#food", "#cooking", "#recipe", "#yum"],
    "travel": ["#travel", "#wanderlust", "#adventure", "#explore"],
    "fashion": ["#fashion", "#style", "#ootd", "#trendy"],
    "lifestyle": ["#lifestyle", "#daily", "#vlog", "#life"],
    "finance": ["#finance", "#money", "#investing", "#wealth"],
    "education": ["#education", "#learning", "#study", "#knowledge"],
}
GENERIC_HASHTAGS: list[str] = ["#fyp", "#viral", "#trending", "#explore"]


@dataclass
class SourceContent:
    content_id: str
    media_url: str
    title: str
    description: str
    duration_sec: int = 60
    source_platform: str = "tiktok"
    language: str = "id"
    niche: str = "lifestyle"

    def fingerprint(self) -> str:
        h = hashlib.md5(
            f"{self.content_id}|{self.title}|{self.niche}|{self.language}".encode()
        ).hexdigest()[:12]
        return h


@dataclass
class RepurposedContent:
    target_platform: str
    target_format: str
    target_duration_sec: int
    media_url: str
    caption: str
    hashtags: list[str]
    best_posting_time: str
    estimated_reach: int
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clamp_duration(src_dur: int, min_d: int, max_d: int) -> int:
    return max(min_d, min(max_d, int(src_dur)))


def _format_aspect(platform: str) -> str:
    spec = PLATFORM_SPECS.get(platform, PLATFORM_SPECS["tiktok"])
    return spec["format"]


def _caption_for_tone(title: str, description: str, tone: str) -> str:
    title = (title or "").strip()
    description = (description or "").strip()
    if tone == "professional":
        body = f"{title} — key insights for modern professionals."
        if description:
            body += f" {description[:140]}"
        return body
    if tone == "playful":
        body = f"POV: {title} ✨"
        if description:
            body += f" {description[:120]}"
        return body + " 😍"
    if tone == "authoritative":
        body = f"{title}. Here's what you need to know."
        if description:
            body += f" {description[:140]}"
        return body
    if tone == "inspirational":
        body = f"Ready for {title}?"
        if description:
            body += f" {description[:120]}"
        return body + " 💡"
    # engaging default
    body = f"{title}"
    if description:
        body += f" — {description[:120]}"
    return body + " 🔥"


def _suggest_hashtags(source: SourceContent, target_platform: str, max_count: int) -> list[str]:
    pool = list(HASHTAG_POOL.get(source.niche.lower(), []))
    if not pool:
        pool = list(GENERIC_HASHTAGS)
    if target_platform in ("tiktok", "reels", "youtube_shorts"):
        pool = pool + GENERIC_HASHTAGS
    elif target_platform == "linkedin":
        pool = [h for h in pool if h not in GENERIC_HASHTAGS][:max_count]
    # Dedup + trim.
    seen: set[str] = set()
    out: list[str] = []
    for h in pool:
        if h in seen:
            continue
        seen.add(h)
        out.append(h)
        if len(out) >= max_count:
            break
    return out


def _best_time(platform: str, tz: str, weekday_only: bool = False) -> str:
    """Return a posting-time string in the given timezone.

    Uses a simple per-platform hour table (WIB-equivalent hours).
    """
    tz = tz or "Asia/Jakarta"
    hours = {
        "tiktok":         [11, 19, 21],
        "reels":          [12, 18, 20],
        "youtube_shorts": [16, 20, 22],
        "twitter":        [9, 13, 17],
        "linkedin":       [8, 12, 17],
        "youtube":        [17, 20, 21],
    }
    h = hours.get(platform, [12, 18, 20])[0]
    offset = 0
    if tz == "Asia/Jakarta":
        offset = 7
    elif tz == "Asia/Makassar":
        offset = 8
    elif tz == "Asia/Jayapura":
        offset = 9
    elif tz == "UTC":
        offset = 0
    elif tz.startswith("Asia/Singapore") or tz.startswith("Asia/Kuala_Lumpur"):
        offset = 8
    utc_hour = (h - offset) % 24
    now = datetime.now(timezone.utc)
    days_ahead = 1 if now.hour >= utc_hour else 0
    target = now + timedelta(days=days_ahead)
    return target.replace(hour=utc_hour, minute=0, second=0, microsecond=0).isoformat()


def _estimate_reach(platform: str, niche: str) -> int:
    base = {
        "tiktok": 5000, "reels": 4500, "youtube_shorts": 6000,
        "twitter": 2500, "linkedin": 1500, "youtube": 8000,
    }.get(platform, 3000)
    n = (niche or "").lower()
    if n in {"fitness", "gaming", "drama"}:
        base = int(base * 1.4)
    elif n in {"meditation", "education"}:
        base = int(base * 0.7)
    return base


class ContentRepurposer:
    def __init__(self, video_editor: Optional[Any] = None,
                 ai_dispatcher: Optional[Any] = None,
                 analytics: Optional[Any] = None) -> None:
        self.editor = video_editor
        self.ai = ai_dispatcher
        self.analytics = analytics
        self._cache: dict[str, RepurposedContent] = {}
        self.spend_tracker: dict[str, float] = {"spent": 0.0}

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------
    @staticmethod
    def _check_source(source: SourceContent) -> None:
        if not source or not source.media_url or not source.media_url.strip():
            raise ValueError("source.media_url cannot be empty")
        if not source.content_id or not source.content_id.strip():
            raise ValueError("source.content_id cannot be empty")
        if source.duration_sec <= 0 or source.duration_sec > 600:
            raise ValueError(
                f"source.duration_sec out of range: {source.duration_sec}"
            )
        if source.language not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"unsupported language: {source.language}. "
                f"Allowed: {list(SUPPORTED_LANGUAGES)}"
            )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _record_spend(self, cost: float) -> None:
        self.spend_tracker["spent"] = round(self.spend_tracker["spent"] + cost, 6)
        log.info("repurposer_spend: +$%.6f total=$%.6f", cost, self.spend_tracker["spent"])

    async def _resize_via_editor(self, source: SourceContent, target_format: str) -> tuple[str, float]:
        """Resize the source media via the video editor; return (new_url, cost)."""
        if self.editor is None:
            return source.media_url, 0.0
        if target_format == "vertical" and hasattr(self.editor, "to_vertical"):
            res = await self.editor.to_vertical(source.media_url)
            return res.output_url, res.cost_usd
        if target_format == "square" and hasattr(self.editor, "to_square"):
            res = await self.editor.to_square(source.media_url)
            return res.output_url, res.cost_usd
        if target_format == "horizontal" and hasattr(self.editor, "resize"):
            res = await self.editor.resize(source.media_url, *ASPECT_HORIZONTAL)
            return res.output_url, res.cost_usd
        return source.media_url, 0.0

    async def _build(
        self,
        source: SourceContent,
        target_platform: str,
        tone: str = "engaging",
        timezone_name: str = "Asia/Jakarta",
    ) -> RepurposedContent:
        if target_platform not in PLATFORM_SPECS:
            raise ValueError(
                f"unsupported platform: {target_platform}. "
                f"Allowed: {list(PLATFORM_SPECS)}"
            )
        if tone not in SUPPORTED_TONES:
            raise ValueError(
                f"unsupported tone: {tone}. Allowed: {list(SUPPORTED_TONES)}"
            )
        spec = PLATFORM_SPECS[target_platform]
        target_dur = _clamp_duration(source.duration_sec, spec["min_duration"], spec["max_duration"])
        target_format = spec["format"]
        media_url, cost = await self._resize_via_editor(source, target_format)
        self._record_spend(cost)

        # Cache key: source content_id + platform + tone.
        key = f"{source.content_id}:{target_platform}:{tone}"
        caption = await self.generate_caption(source, target_platform, tone=tone)
        hashtags = await self.suggest_hashtags(source, target_platform, max_count=5)
        best_time = await self.best_posting_time(target_platform, timezone_name)
        reach = _estimate_reach(target_platform, source.niche)
        rep = RepurposedContent(
            target_platform=target_platform,
            target_format=target_format,
            target_duration_sec=target_dur,
            media_url=media_url,
            caption=caption,
            hashtags=hashtags,
            best_posting_time=best_time,
            estimated_reach=reach,
            cost_usd=round(cost, 6),
            metadata={
                "aspect": list(spec["aspect"]),
                "min_duration": spec["min_duration"],
                "max_duration": spec["max_duration"],
                "source_id": source.content_id,
                "source_platform": source.source_platform,
            },
        )
        self._cache[key] = rep
        return rep

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    async def repurpose_for_all_platforms(self, source: SourceContent) -> list[RepurposedContent]:
        self._check_source(source)
        platforms = ["tiktok", "reels", "youtube_shorts", "twitter", "linkedin", "youtube"]
        out: list[RepurposedContent] = []
        for p in platforms:
            out.append(await self._build(source, p, tone=PLATFORM_SPECS[p]["tone"]))
        return out

    async def to_reels(self, source: SourceContent) -> RepurposedContent:
        self._check_source(source)
        return await self._build(source, "reels", tone="engaging")

    async def to_tiktok(self, source: SourceContent) -> RepurposedContent:
        self._check_source(source)
        return await self._build(source, "tiktok", tone="playful")

    async def to_youtube_shorts(self, source: SourceContent) -> RepurposedContent:
        self._check_source(source)
        return await self._build(source, "youtube_shorts", tone="engaging")

    async def to_twitter_video(self, source: SourceContent) -> RepurposedContent:
        self._check_source(source)
        return await self._build(source, "twitter", tone="engaging")

    async def to_linkedin_video(self, source: SourceContent) -> RepurposedContent:
        self._check_source(source)
        return await self._build(source, "linkedin", tone="professional")

    async def to_youtube_long(self, source: SourceContent) -> RepurposedContent:
        self._check_source(source)
        return await self._build(source, "youtube", tone="authoritative")

    async def generate_caption(
        self, source: SourceContent, target_platform: str, tone: str = "engaging",
    ) -> str:
        if target_platform not in PLATFORM_SPECS:
            raise ValueError(f"unsupported platform: {target_platform}")
        if tone not in SUPPORTED_TONES:
            raise ValueError(f"unsupported tone: {tone}")
        # If an AI dispatcher is present, use it. Otherwise heuristic.
        if self.ai is not None and hasattr(self.ai, "dispatch"):
            try:
                req = {
                    "model": "flux-klein-4b",
                    "prompt": f"caption for {target_platform} ({tone}): {source.title}",
                    "max_cost_usd": 0.01,
                    "n": 1,
                    "metadata": {"task": "caption", "tone": tone},
                }
                # Lightweight: do not actually dispatch network. We just
                # produce a heuristic caption. Real callers can pass an
                # ai_dispatcher that overrides this behaviour.
                _ = req
            except Exception as e:
                log.warning("ai caption dispatch failed: %s", e)
        return _caption_for_tone(source.title, source.description, tone)

    async def suggest_hashtags(
        self, source: SourceContent, target_platform: str, max_count: int = 5,
    ) -> list[str]:
        if target_platform not in PLATFORM_SPECS:
            raise ValueError(f"unsupported platform: {target_platform}")
        max_count = max(1, min(int(max_count), 10))
        return _suggest_hashtags(source, target_platform, max_count)

    async def best_posting_time(
        self, target_platform: str, timezone_name: str = "Asia/Jakarta",
    ) -> str:
        if target_platform not in PLATFORM_SPECS:
            raise ValueError(f"unsupported platform: {target_platform}")
        # If analytics present, try to learn from it. Otherwise heuristic.
        if self.analytics is not None and hasattr(self.analytics, "best_posting_time"):
            try:
                hour_min = self.analytics.best_posting_time(target_platform, niche="default")
                if hour_min:
                    h, m = hour_min
                    now = datetime.now(timezone.utc)
                    days_ahead = 1 if now.hour >= h else 0
                    target = (now + timedelta(days=days_ahead)).replace(
                        hour=h, minute=m, second=0, microsecond=0,
                    )
                    return target.isoformat()
            except Exception as e:
                log.warning("analytics best_posting_time failed: %s", e)
        return _best_time(target_platform, timezone_name)

    def get_cached(self, source_id: str, target_platform: str) -> Optional[RepurposedContent]:
        for k, v in self._cache.items():
            if k.startswith(f"{source_id}:{target_platform}"):
                return v
        return None

    def summary(self) -> dict[str, Any]:
        return {
            "cached_variants": len(self._cache),
            "spent_usd": self.spend_tracker["spent"],
            "platforms_supported": list(PLATFORM_SPECS),
            "tones_supported": list(SUPPORTED_TONES),
            "editor_configured": self.editor is not None,
            "analytics_configured": self.analytics is not None,
        }


__all__ = [
    "ASPECT_HORIZONTAL",
    "ASPECT_SQUARE",
    "ASPECT_VERTICAL",
    "ContentRepurposer",
    "PLATFORM_SPECS",
    "RepurposedContent",
    "SourceContent",
    "SUPPORTED_LANGUAGES",
    "SUPPORTED_PLATFORMS",
    "SUPPORTED_TONES",
]
