"""A/B testing framework for content variants.

Provides deterministic variant assignment, impression/engagement/conversion
tracking, and statistical significance analysis using a two-proportion z-test.

Design:
  - Variants are content pieces (post + image + caption + hashtags)
  - Users are deterministically bucketed via md5(test_id:user_id)
  - Winner picked by conversion_rate; significance via pooled z-test
  - All dataclasses serializable via to_dict() for Notion sync
"""
from __future__ import annotations

import hashlib
import logging
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)


@dataclass
class Variant:
    id: str
    content: str
    image_url: str = ""
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    impressions: int = 0
    engagements: int = 0
    conversions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def engagement_rate(self) -> float:
        if self.impressions == 0:
            return 0.0
        return self.engagements / self.impressions

    def conversion_rate(self) -> float:
        if self.impressions == 0:
            return 0.0
        return self.conversions / self.impressions


@dataclass
class ABTestResult:
    winner_id: str
    winner_rate: float
    loser_id: str
    loser_rate: float
    uplift_percent: float
    confidence: float
    sample_size: int
    is_significant: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ABTest:
    id: str
    name: str
    variants: list[Variant] = field(default_factory=list)
    traffic_split: list[float] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ABTesting:
    """In-memory A/B test manager.

    Stores tests and per-user variant assignments. Assignment is deterministic
    so the same user always lands on the same variant for a given test.
    """

    def __init__(self) -> None:
        self._tests: dict[str, ABTest] = {}
        self._assignments: dict[str, dict[str, str]] = {}

    def create_test(
        self,
        name: str,
        variants: list[Variant],
        traffic_split: Optional[list[float]] = None,
    ) -> str:
        if not variants:
            raise ValueError("variants must not be empty")
        if traffic_split is None:
            traffic_split = [1.0 / len(variants)] * len(variants)
        if len(traffic_split) != len(variants):
            raise ValueError("traffic_split length must match variants")
        if not math.isclose(sum(traffic_split), 1.0, abs_tol=1e-6):
            raise ValueError("traffic_split must sum to 1.0")
        test_id = f"test_{uuid.uuid4().hex[:8]}"
        test = ABTest(
            id=test_id,
            name=name,
            variants=list(variants),
            traffic_split=list(traffic_split),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._tests[test_id] = test
        self._assignments[test_id] = {}
        log.info("Created A/B test %s (%s) with %d variants", test_id, name, len(variants))
        return test_id

    def assign_variant(self, test_id: str, user_id: str) -> Variant:
        if test_id not in self._tests:
            raise KeyError(f"Test {test_id} not found")
        test = self._tests[test_id]
        if user_id in self._assignments[test_id]:
            vid = self._assignments[test_id][user_id]
            for v in test.variants:
                if v.id == vid:
                    return v
        h = int(hashlib.md5(f"{test_id}:{user_id}".encode()).hexdigest()[:8], 16)
        target = (h % 10000) / 10000.0
        cum = 0.0
        idx = len(test.variants) - 1
        for i, w in enumerate(test.traffic_split):
            cum += w
            if target < cum:
                idx = i
                break
        variant = test.variants[idx]
        self._assignments[test_id][user_id] = variant.id
        return variant

    def record_impression(self, test_id: str, variant_id: str) -> None:
        self._get_variant(test_id, variant_id).impressions += 1

    def record_engagement(self, test_id: str, variant_id: str) -> None:
        self._get_variant(test_id, variant_id).engagements += 1

    def record_conversion(self, test_id: str, variant_id: str) -> None:
        self._get_variant(test_id, variant_id).conversions += 1

    def _get_variant(self, test_id: str, variant_id: str) -> Variant:
        if test_id not in self._tests:
            raise KeyError(f"Test {test_id} not found")
        for v in self._tests[test_id].variants:
            if v.id == variant_id:
                return v
        raise KeyError(f"Variant {variant_id} not found")

    @staticmethod
    def _z_test_proportions(p1: float, n1: int, p2: float, n2: int) -> float:
        if n1 == 0 or n2 == 0:
            return 1.0
        p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
        if p_pool == 0 or p_pool == 1:
            return 1.0
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
        if se == 0:
            return 1.0
        z = (p1 - p2) / se
        p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
        return max(0.0, min(1.0, p))

    def analyze(self, test_id: str, min_samples: int = 100) -> ABTestResult:
        if test_id not in self._tests:
            raise KeyError(f"Test {test_id} not found")
        test = self._tests[test_id]
        if len(test.variants) < 2:
            raise ValueError("Need at least 2 variants")
        sorted_v = sorted(test.variants, key=lambda v: v.conversion_rate(), reverse=True)
        winner = sorted_v[0]
        loser = sorted_v[1]
        total_n = sum(v.impressions for v in test.variants)
        p = self._z_test_proportions(
            winner.conversion_rate(), winner.impressions,
            loser.conversion_rate(), loser.impressions,
        )
        confidence = 1.0 - p
        if loser.conversion_rate() > 0:
            uplift = ((winner.conversion_rate() - loser.conversion_rate()) /
                      loser.conversion_rate() * 100.0)
        else:
            uplift = 0.0
        significant = (p < 0.05) and (total_n >= min_samples)
        return ABTestResult(
            winner_id=winner.id,
            winner_rate=winner.conversion_rate(),
            loser_id=loser.id,
            loser_rate=loser.conversion_rate(),
            uplift_percent=uplift,
            confidence=confidence,
            sample_size=total_n,
            is_significant=significant,
        )

    def multi_variate_score(self, test_id: str) -> dict[str, float]:
        if test_id not in self._tests:
            raise KeyError(f"Test {test_id} not found")
        result: dict[str, float] = {}
        for v in self._tests[test_id].variants:
            er = v.engagement_rate()
            cr = v.conversion_rate()
            result[v.id] = max(0.0, min(1.0, er * 0.5 + cr * 0.5))
        return result

    def get_test(self, test_id: str) -> ABTest:
        if test_id not in self._tests:
            raise KeyError(f"Test {test_id} not found")
        return self._tests[test_id]

    def list_tests(self) -> list[ABTest]:
        return list(self._tests.values())
