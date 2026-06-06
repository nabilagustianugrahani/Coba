"""Optimize captions for engagement based on platform + niche.

Scoring:
  score = 0.4 * length_match + 0.3 * hashtag_match + 0.2 * emoji_appropriateness + 0.1 * cta_present

Platform limits:
  - TikTok:     2200 chars, optimal < 150
  - Instagram:  2200 chars, optimal < 125
  - Twitter:    280 chars
  - YouTube:    5000 chars (description), optimal < 200
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ugc_ai_overpower.integrations.character_agent import Character

log = logging.getLogger(__name__)

PLATFORM_LIMITS: dict[str, dict[str, int]] = {
    "tiktok":    {"max": 2200, "optimal": 150},
    "instagram": {"max": 2200, "optimal": 125},
    "twitter":   {"max": 280,  "optimal": 100},
    "youtube":   {"max": 5000, "optimal": 200},
}

CTA_PHRASES: list[str] = [
    "follow", "subscribe", "share", "like", "comment", "save",
    "check link", "link in bio", "swipe up", "tag a friend",
    "dm me", "drop a comment", "let me know", "try this",
    "shop now", "click", "sign up", "join",
]


@dataclass
class CaptionInput:
    text: str
    platform: str = "instagram"
    niche: str = "general"


@dataclass
class CaptionResult:
    optimized_text: str
    char_count: int
    optimal_length: bool
    hashtag_count: int
    emoji_count: int
    cta_detected: bool
    engagement_score: float  # 0-100
    suggestions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_EMOJI_RX = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # misc
    "]", flags=re.UNICODE,  # no + — count individual chars
)
_HASHTAG_RX = re.compile(r"#\w+")
_CTA_RX = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in CTA_PHRASES) + r")\b",
    re.IGNORECASE,
)

NICHE_EMOJI_SCORE: dict[str, float] = {
    "fashion": 0.9, "beauty": 0.9, "lifestyle": 0.8, "food": 0.7,
    "travel": 0.8, "fitness": 0.6, "tech": 0.3, "finance": 0.3,
    "general": 0.5,
}


def _count_hashtags(text: str) -> int:
    return len(_HASHTAG_RX.findall(text))


def _count_emojis(text: str) -> int:
    return len(_EMOJI_RX.findall(text))


def _detect_cta(text: str) -> bool:
    return bool(_CTA_RX.search(text))


def _score_length(text: str, platform: str) -> tuple[float, bool, list[str]]:
    limits = PLATFORM_LIMITS.get(platform, PLATFORM_LIMITS["instagram"])
    cc = len(text)
    optimal = limits["optimal"]
    max_c = limits["max"]
    if cc == 0:
        return 0.0, False, ["Content is empty"]
    if cc > max_c:
        return 10.0, False, [f"Exceeds {platform} limit ({cc} > {max_c})"]
    # score: 100 at optimal, linear decay to 0 at max
    if cc <= optimal:
        raw = 100.0 * (1.0 - (optimal - cc) / optimal * 0.5)  # 50-100
    else:
        raw = 100.0 * max(0.0, 1.0 - (cc - optimal) / (max_c - optimal))
    ok = cc <= max_c
    sug: list[str] = []
    if cc > optimal:
        sug.append(f"Shorten caption to ~{optimal} chars for better engagement")
    return round(min(100.0, raw), 1), ok, sug


def _score_hashtags(hashtag_count: int, platform: str, niche: str) -> tuple[float, list[str]]:
    """Score hashtag usage. Ideal: 3-5 for most platforms."""
    if platform == "youtube":
        ideal_max = 15
    elif platform in ("twitter",):
        ideal_max = 3
    else:
        ideal_max = 10
    if hashtag_count == 0:
        return 30.0, ["Add a few hashtags to increase reach"]
    if hashtag_count > ideal_max:
        return max(0.0, 100.0 - (hashtag_count - ideal_max) * 8), ["Too many hashtags"]
    # 80-100 for 1 to ideal_max
    raw = 80.0 + (hashtag_count / max(1, ideal_max)) * 20.0
    return round(min(100.0, raw), 1), []


def _score_emoji_appropriateness(emoji_count: int, niche: str) -> tuple[float, list[str]]:
    niche_score = NICHE_EMOJI_SCORE.get(niche, NICHE_EMOJI_SCORE["general"])
    if emoji_count == 0:
        return 40.0 * niche_score, []
    # 0-3 emojis is ideal for most niches
    ideal_raw = min(100.0, emoji_count * 25.0)  # 1=25, 2=50, 3=75, 4=100
    ideal_raw = min(ideal_raw, 100.0 - max(0, emoji_count - 4) * 20.0)  # penalty for >4
    raw = ideal_raw * niche_score
    sug: list[str] = []
    if emoji_count > 5:
        sug.append("Too many emojis — reduce to 1-3 for better readability")
    return round(min(100.0, raw), 1), sug


def _score_cta(has_cta: bool) -> tuple[float, list[str]]:
    if has_cta:
        return 100.0, []
    return 0.0, ["Add a call to action (e.g., 'Follow for more')"]


def _optimize_text(text: str, platform: str) -> str:
    """Truncate if over platform limit, preserving content structure."""
    limits = PLATFORM_LIMITS.get(platform, PLATFORM_LIMITS["instagram"])
    max_c = limits["max"]
    if len(text) <= max_c:
        return text
    # Try to truncate at sentence boundary
    truncated = text[:max_c]
    last_period = truncated.rfind(".")
    if last_period > max_c * 0.8:
        return text[: last_period + 1]
    last_space = truncated.rfind(" ")
    if last_space > max_c * 0.5:
        return text[:last_space]
    return truncated


# ---------------------------------------------------------------------------
# main class
# ---------------------------------------------------------------------------

class CaptionOptimizer:
    def __init__(self, character: Optional[Character] = None) -> None:
        self.character = character

    def optimize(self, caption: CaptionInput) -> CaptionResult:
        text = caption.text
        platform = caption.platform.lower()
        niche = caption.niche.lower()

        if platform not in PLATFORM_LIMITS:
            raise ValueError(f"Unsupported platform: {platform}. Supported: {list(PLATFORM_LIMITS)}")

        optimized = _optimize_text(text, platform)
        cc = len(optimized)
        hashtag_count = _count_hashtags(optimized)
        emoji_count = _count_emojis(optimized)
        cta_detected = _detect_cta(optimized)

        len_score, optimal_length, len_sug = _score_length(optimized, platform)
        htag_score, htag_sug = _score_hashtags(hashtag_count, platform, niche)
        emoji_score, emoji_sug = _score_emoji_appropriateness(emoji_count, niche)
        cta_score, cta_sug = _score_cta(cta_detected)

        raw = (0.4 * len_score + 0.3 * htag_score + 0.2 * emoji_score + 0.1 * cta_score)
        engagement_score = round(raw, 1)

        suggestions = len_sug + htag_sug + emoji_sug + cta_sug

        return CaptionResult(
            optimized_text=optimized,
            char_count=cc,
            optimal_length=optimal_length,
            hashtag_count=hashtag_count,
            emoji_count=emoji_count,
            cta_detected=cta_detected,
            engagement_score=engagement_score,
            suggestions=suggestions,
        )

    def suggest_hashtags(self, niche: str, count: int = 5) -> list[str]:
        """Return deterministic niche-relevant hashtags."""
        pool: dict[str, list[str]] = {
            "fashion":   ["#OOTD", "#fashion", "#style", "#trendy", "#outfitinspo", "#viralstyle"],
            "beauty":    ["#skincare", "#makeup", "#glowup", "#beauty", "#tutorial"],
            "tech":      ["#tech", "#gadget", "#review", "#unboxing", "#techtips"],
            "food":      ["#food", "#recipe", "#homemade", "#yummy", "#foodie"],
            "fitness":   ["#fitness", "#workout", "#gym", "#fitlife", "#health"],
            "travel":    ["#travel", "#wanderlust", "#explore", "#adventure", "#trip"],
            "finance":   ["#finance", "#investing", "#money", "#wealth", "#budget"],
            "lifestyle": ["#lifestyle", "#daily", "#life", "#vlog", "#inspo"],
            "general":   ["#viral", "#fyp", "#trending", "#content", "#creator"],
        }
        tags = pool.get(niche.lower(), pool["general"])
        count = max(1, min(count, len(tags)))
        return tags[:count]

    def platform_limits(self) -> dict[str, dict[str, int]]:
        return {k: dict(v) for k, v in PLATFORM_LIMITS.items()}


__all__ = [
    "CaptionInput",
    "CaptionOptimizer",
    "CaptionResult",
    "PLATFORM_LIMITS",
]
