"""A/B test optimizer — pick winning variant based on simulated engagement.

Uses a simple heuristic: longer variants with more emoji + CTA win more often.
In production this would be replaced with a real Bayesian/nonparametric test.
"""
from __future__ import annotations

import logging
import math
import random
import re
from dataclasses import dataclass, field
from typing import Optional

from ugc_ai_overpower.integrations.character_agent import Character

log = logging.getLogger(__name__)

_EMOJI_RX = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]", flags=re.UNICODE,
)

_CTA_KEYWORDS = [
    "follow", "subscribe", "share", "like", "comment", "save",
    "check link", "link in bio", "swipe up", "tag a friend",
    "dm me", "drop a comment", "let me know", "try this",
    "shop now", "click", "sign up", "join", "buy", "order",
]


@dataclass
class ABTestInput:
    variants: list[str]  # 2-5 caption/body variants
    metric: str  # ctr, conversion, engagement, retention
    sample_size: int = 1000

    def __post_init__(self) -> None:
        valid_metrics = ("ctr", "conversion", "engagement", "retention")
        if self.metric not in valid_metrics:
            raise ValueError(f"metric must be one of {valid_metrics}, got {self.metric}")
        if len(self.variants) < 2:
            raise ValueError(f"Need at least 2 variants, got {len(self.variants)}")
        if len(self.variants) > 5:
            raise ValueError(f"Max 5 variants, got {len(self.variants)}")
        if self.sample_size < 100:
            raise ValueError(f"sample_size must be >= 100, got {self.sample_size}")


@dataclass
class ABTestResult:
    winner: str
    winner_index: int
    lift_percent: float
    confidence: float  # 0-1
    sample_distribution: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "winner": self.winner,
            "winner_index": self.winner_index,
            "lift_percent": self.lift_percent,
            "confidence": self.confidence,
            "sample_distribution": self.sample_distribution,
        }


def _count_emojis(text: str) -> int:
    return len(_EMOJI_RX.findall(text))


def _has_cta(text: str) -> bool:
    pattern = r"\b(" + "|".join(re.escape(k) for k in _CTA_KEYWORDS) + r")\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


def _heuristic_score(variant: str, metric: str, rng: random.Random) -> float:
    """Score a variant from 0-100. Higher = more engaging.

    Heuristic:
      - Length: 0-40 pts (longer up to 300 chars)
      - Emoji:  0-30 pts (capped at 3 emoji)
      - CTA:    0-30 pts (1 if present)
      - Metric boost: +5 for engagement/retention, +10 for ctr/conversion
      - Small jitter: +/-5 for realism
    """
    score = 0.0

    # Length score (0-40)
    normalized_len = min(len(variant) / 300.0, 1.0)
    score += normalized_len * 40.0

    # Emoji score (0-30)
    emoji_count = min(_count_emojis(variant), 3)
    score += (emoji_count / 3.0) * 30.0

    # CTA score (0-30)
    if _has_cta(variant):
        score += 30.0

    # Metric boost
    boost_map = {"ctr": 10, "conversion": 10, "engagement": 5, "retention": 5}
    score += boost_map.get(metric, 5)

    # Jitter
    score += rng.uniform(-5.0, 5.0)

    return max(0.0, min(100.0, score))


class ABTestOptimizer:
    """Simulate an A/B test and pick the winning variant.

    Uses a simple heuristic scoring function. In a real system this would
    call a Bayesian model or frequentist significance test.
    """

    def __init__(self, character: Optional[Character] = None) -> None:
        self.character = character
        self._rng = random.Random(42)

    def run_test(self, ab_input: ABTestInput) -> ABTestResult:
        """Run a simulated A/B test on the given variants.

        Returns the winner with estimated lift and confidence.
        """
        n = len(ab_input.variants)
        sample_per_variant = max(100, ab_input.sample_size // n)

        # Score each variant
        scores = [_heuristic_score(v, ab_input.metric, self._rng) for v in ab_input.variants]

        # Simulate sampling: distribute samples proportional to score
        total_score = sum(scores) or 1.0
        proportions = [s / total_score for s in scores]

        sample_distribution: dict[str, int] = {}
        for i, variant in enumerate(ab_input.variants):
            sample_distribution[variant] = int(proportions[i] * ab_input.sample_size)

        # Find winner
        winner_idx = max(range(n), key=lambda i: scores[i])
        winner = ab_input.variants[winner_idx]

        # Lift over second best
        sorted_scores = sorted(scores, reverse=True)
        if len(sorted_scores) > 1 and sorted_scores[1] > 0:
            lift = ((sorted_scores[0] - sorted_scores[1]) / sorted_scores[1]) * 100.0
        else:
            lift = 0.0

        # Confidence: simulated via a simple heuristic based on sample size + score gap
        gap = sorted_scores[0] - (sorted_scores[1] if len(sorted_scores) > 1 else 0)
        confidence = min(0.99, 0.5 + (gap / 100.0) * 0.4 + (ab_input.sample_size / 10000.0) * 0.09)
        confidence = max(0.5, min(0.99, confidence))

        return ABTestResult(
            winner=winner,
            winner_index=winner_idx,
            lift_percent=round(lift, 2),
            confidence=round(confidence, 4),
            sample_distribution=sample_distribution,
        )

    def suggest_next_test(self, current_winner: str, niche: str) -> str:
        """Suggest a follow-up test variant based on the winner + niche."""
        n_presets = {
            "fashion": "Actually, would YOU wear this? Drop a yes/no! 🔥",
            "tech": "Drop a comment with your thoughts on this spec!",
            "beauty": "Tag a friend who needs to see this glow-up! ✨",
            "food": "Try this recipe and tag me in your version! 😋",
            "fitness": "Save this and try it tomorrow — report back! 💪",
            "travel": "Tag your travel buddy — where should we go next? ✈️",
            "finance": "Save this breakdown for your next portfolio review! 📈",
            "lifestyle": "Share this with someone who needs a reset! 💫",
        }
        base = n_presets.get(niche, "Drop a comment and let me know your thoughts!")
        return f"{current_winner.rstrip('.')} — {base}"


__all__ = [
    "ABTestInput",
    "ABTestResult",
    "ABTestOptimizer",
]
