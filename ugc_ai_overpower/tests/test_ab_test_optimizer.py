"""Tests for integrations/ab_test_optimizer.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.ab_test_optimizer import (
    ABTestInput,
    ABTestOptimizer,
    ABTestResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def optimizer():
    return ABTestOptimizer()


@pytest.fixture
def two_variants():
    return [
        "Check out this new product! Buy now! 🔥 #shop",
        "A very long and detailed caption with multiple emoji 🔥🔥🔥 and a clear call to action — click the link below to get yours today! #shop #deal",
    ]


@pytest.fixture
def three_variants():
    return [
        "Buy now! 🔥",
        "Check out our latest collection — link in bio to shop the look! ✨",
        "Discover the perfect outfit for every occasion. From casual to formal, we have you covered. Tap the link to explore more and find your new favorite piece today! 👗🔥✨ #fashion #style",
    ]


# ---------------------------------------------------------------------------
# ABTestInput validation
# ---------------------------------------------------------------------------

def test_ab_input_valid():
    inp = ABTestInput(variants=["A", "B"], metric="ctr")
    assert inp.metric == "ctr"
    assert inp.sample_size == 1000


def test_ab_input_invalid_metric():
    with pytest.raises(ValueError, match="metric must be one of"):
        ABTestInput(variants=["A", "B"], metric="invalid")


def test_ab_input_too_few_variants():
    with pytest.raises(ValueError, match="Need at least 2 variants"):
        ABTestInput(variants=["A"], metric="ctr")


def test_ab_input_too_many_variants():
    with pytest.raises(ValueError, match="Max 5 variants"):
        ABTestInput(variants=["A", "B", "C", "D", "E", "F"], metric="ctr")


def test_ab_input_sample_size_too_small():
    with pytest.raises(ValueError, match="sample_size must be >= 100"):
        ABTestInput(variants=["A", "B"], metric="ctr", sample_size=50)


# ---------------------------------------------------------------------------
# ABTestResult
# ---------------------------------------------------------------------------

def test_ab_result_fields():
    r = ABTestResult(
        winner="A", winner_index=0, lift_percent=12.5,
        confidence=0.95, sample_distribution={"A": 600, "B": 400},
    )
    assert r.winner == "A"
    assert r.lift_percent == 12.5
    assert r.confidence == 0.95


def test_ab_result_to_dict():
    r = ABTestResult(
        winner="A", winner_index=0, lift_percent=5.0,
        confidence=0.9, sample_distribution={"A": 500, "B": 500},
    )
    d = r.to_dict()
    assert d["winner"] == "A"
    assert d["confidence"] == 0.9


# ---------------------------------------------------------------------------
# ABTestOptimizer.run_test — deterministic
# ---------------------------------------------------------------------------

def test_run_test_returns_ab_test_result(optimizer, two_variants):
    inp = ABTestInput(variants=two_variants, metric="engagement")
    result = optimizer.run_test(inp)
    assert isinstance(result, ABTestResult)


def test_run_test_winner_is_one_of_variants(optimizer, two_variants):
    inp = ABTestInput(variants=two_variants, metric="ctr")
    result = optimizer.run_test(inp)
    assert result.winner in two_variants
    assert 0 <= result.winner_index < len(two_variants)


def test_run_test_longer_variant_wins(optimizer, two_variants):
    """Longer variant with more emoji + CTA should win."""
    inp = ABTestInput(variants=two_variants, metric="engagement")
    result = optimizer.run_test(inp)
    # Second variant is longer, has more emoji, has CTA
    assert result.winner == two_variants[1]


def test_run_test_three_variants_picks_longest(optimizer, three_variants):
    inp = ABTestInput(variants=three_variants, metric="conversion")
    result = optimizer.run_test(inp)
    # Third variant is longest with most emoji
    assert result.winner == three_variants[2]


def test_run_test_lift_percent_positive(optimizer, two_variants):
    inp = ABTestInput(variants=two_variants, metric="engagement")
    result = optimizer.run_test(inp)
    assert result.lift_percent >= 0


def test_run_test_confidence_in_range(optimizer, two_variants):
    inp = ABTestInput(variants=two_variants, metric="ctr")
    result = optimizer.run_test(inp)
    assert 0.5 <= result.confidence <= 0.99


def test_run_test_sample_distribution_sum(optimizer, two_variants):
    inp = ABTestInput(variants=two_variants, metric="engagement", sample_size=2000)
    result = optimizer.run_test(inp)
    total = sum(result.sample_distribution.values())
    assert abs(total - 2000) <= 1  # rounding


def test_run_test_different_metrics_give_different_scores(optimizer):
    variants = ["Short", "A much longer variant with a CTA — buy now! 🔥"]
    r1 = optimizer.run_test(ABTestInput(variants=variants, metric="ctr"))
    r2 = optimizer.run_test(ABTestInput(variants=variants, metric="retention"))
    # Both should pick the longer variant
    assert r1.winner == variants[1]
    assert r2.winner == variants[1]


def test_run_test_all_metrics_accepted(optimizer):
    variants = ["A", "B"]
    for metric in ("ctr", "conversion", "engagement", "retention"):
        inp = ABTestInput(variants=variants, metric=metric)
        result = optimizer.run_test(inp)
        assert result.winner in variants


def test_run_test_large_sample_increases_confidence(optimizer, two_variants):
    r_small = optimizer.run_test(ABTestInput(variants=two_variants, metric="ctr", sample_size=100))
    r_large = optimizer.run_test(ABTestInput(variants=two_variants, metric="ctr", sample_size=10000))
    assert r_large.confidence >= r_small.confidence


# ---------------------------------------------------------------------------
# ABTestOptimizer.suggest_next_test
# ---------------------------------------------------------------------------

def test_suggest_next_test_returns_string(optimizer):
    suggestion = optimizer.suggest_next_test("Buy now!", "fashion")
    assert isinstance(suggestion, str)
    assert len(suggestion) > 10


def test_suggest_next_test_contains_winner(optimizer):
    suggestion = optimizer.suggest_next_test("Click here!", "tech")
    assert "Click here" in suggestion


def test_suggest_next_test_all_niches(optimizer):
    for niche in ("fashion", "tech", "beauty", "food", "fitness", "travel", "finance", "lifestyle"):
        s = optimizer.suggest_next_test("Shop now", niche)
        assert isinstance(s, str) and len(s) > 10


def test_suggest_next_test_fallback_niche(optimizer):
    s = optimizer.suggest_next_test("Buy", "unknown_niche")
    assert "comment" in s.lower()
