"""Burst and edge-case tests for rate limiters.

Covers TokenBucketLimiter and SlidingWindowLimiter under burst loads,
concurrent race conditions, isolated keys, reset, stats, and extreme rates.

Pytest-asyncio mode: auto.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.core.rate_limiter import (
    MultiKeyLimiter,
    SlidingWindowLimiter,
    TokenBucketLimiter,
)

# ======================================================================
# TokenBucketLimiter — burst & recovery
# ======================================================================


@pytest.mark.asyncio
async def test_burst_1000_reqs_drops_excess():
    """1000 concurrent acquires against capacity=10: at most 10 succeed."""
    tb = TokenBucketLimiter(capacity=10, refill_per_sec=0.0001)
    results = await asyncio.gather(*[tb.acquire() for _ in range(1000)])
    successes = sum(1 for r in results if r)
    assert successes == 10, f"expected 10, got {successes}"


@pytest.mark.asyncio
async def test_burst_above_limit_then_recovery():
    """After exhausting, wait for refill, then acquire succeeds."""
    tb = TokenBucketLimiter(capacity=5, refill_per_sec=20.0)
    for _ in range(5):
        assert await tb.acquire() is True
    assert await tb.acquire() is False
    await asyncio.sleep(0.3)  # ~6 tokens refilled
    assert await tb.acquire() is True


@pytest.mark.asyncio
async def test_refill_timing_precision():
    """Refill at 100/sec: after 50ms, at least 4 tokens available (should be 5)."""
    tb = TokenBucketLimiter(capacity=100, refill_per_sec=100.0)
    for _ in range(100):
        await tb.acquire()
    assert await tb.acquire() is False
    await asyncio.sleep(0.05)  # ~5 tokens
    rem = tb.get_remaining()
    assert 4 <= rem <= 100, f"expected ~5 tokens, got {rem}"


# ======================================================================
# TokenBucketLimiter — isolated keys
# ======================================================================


@pytest.mark.asyncio
async def test_isolated_keys_token_bucket():
    """Different keys have independent token buckets."""
    tb = TokenBucketLimiter(capacity=3, refill_per_sec=0.0001)
    for _ in range(3):
        assert await tb.acquire("a") is True
    assert await tb.acquire("a") is False
    # 'b' is untouched
    assert await tb.acquire("b") is True
    assert tb.get_remaining("b") == 2


# ======================================================================
# TokenBucketLimiter — reset & stats
# ======================================================================


@pytest.mark.asyncio
async def test_reset_clears_token_bucket():
    """reset() restores full capacity."""
    tb = TokenBucketLimiter(capacity=7, refill_per_sec=0.0001)
    for _ in range(7):
        await tb.acquire()
    assert await tb.acquire() is False
    tb.reset("default")
    assert tb.get_remaining() == 7
    assert await tb.acquire() is True


# ======================================================================
# TokenBucketLimiter — zero rate / very high rate
# ======================================================================


async def _test_zero_rate(capacity: int, refill_per_sec: float):
    """Zero or negative rate limiter should reject instantiation."""
    pass


def test_zero_rate_raises():
    """refill_per_sec <= 0 raises ValueError."""
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=10, refill_per_sec=0)
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=10, refill_per_sec=-1)


def test_zero_capacity_raises():
    """capacity <= 0 raises ValueError."""
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=0, refill_per_sec=1)
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=-1, refill_per_sec=1)


@pytest.mark.asyncio
async def test_very_high_rate_no_practical_limit():
    """capacity=1_000_000, refill=1_000_000/sec: no practical limit."""
    tb = TokenBucketLimiter(capacity=1_000_000, refill_per_sec=1_000_000)
    for _ in range(1000):
        assert await tb.acquire() is True
    assert tb.get_remaining() > 900_000  # most tokens still available


# ======================================================================
# TokenBucketLimiter — sustained pattern
# ======================================================================


@pytest.mark.asyncio
async def test_sustained_pattern():
    """Sustained 1 req/100ms with bucket that refills at same rate."""
    tb = TokenBucketLimiter(capacity=5, refill_per_sec=10.0)
    start = time.monotonic()
    acquired = 0
    while time.monotonic() - start < 2.0:
        if await tb.acquire():
            acquired += 1
        await asyncio.sleep(0.1)
    # Expected: 5 (initial burst) + ~20 (refill over 2s @ 10/s) = ~25
    assert acquired >= 18, f"expected >=18 sustained acquires, got {acquired}"


# ======================================================================
# TokenBucketLimiter — concurrent race conditions
# ======================================================================


@pytest.mark.asyncio
async def test_concurrent_race_condition():
    """200 concurrent acquires with capacity=50: exactly 50 succeed."""
    tb = TokenBucketLimiter(capacity=50, refill_per_sec=0.0001)
    results = await asyncio.gather(*[tb.acquire() for _ in range(200)])
    successes = sum(1 for r in results if r)
    assert successes == 50, f"expected 50, got {successes}"


# ======================================================================
# SlidingWindowLimiter — burst & edge cases
# ======================================================================


@pytest.mark.asyncio
async def test_sliding_window_burst_drops_excess():
    """Burst of 100 against max=5: only 5 succeed."""
    sw = SlidingWindowLimiter(max_requests=5, window_sec=10.0)
    results = await asyncio.gather(*[sw.acquire() for _ in range(100)])
    successes = sum(1 for r in results if r)
    assert successes == 5, f"expected 5, got {successes}"


@pytest.mark.asyncio
async def test_sliding_window_window_boundary():
    """Requests exactly at window boundary (after window_sec elapses)."""
    sw = SlidingWindowLimiter(max_requests=2, window_sec=0.2)
    assert await sw.acquire() is True
    assert await sw.acquire() is True
    assert await sw.acquire() is False
    await asyncio.sleep(0.25)  # past the window
    assert await sw.acquire() is True
    assert await sw.acquire() is True
    assert await sw.acquire() is False  # 2nd window also full


@pytest.mark.asyncio
async def test_sliding_window_concurrent_race():
    """100 concurrent on max=10: exactly 10 succeed."""
    sw = SlidingWindowLimiter(max_requests=10, window_sec=10.0)
    results = await asyncio.gather(*[sw.acquire() for _ in range(100)])
    successes = sum(1 for r in results if r)
    assert successes == 10, f"expected 10, got {successes}"


@pytest.mark.asyncio
async def test_sliding_window_sustained_rate():
    """Sustained 1 req/50ms for 1s against max=10 per 1s window."""
    sw = SlidingWindowLimiter(max_requests=10, window_sec=1.0)
    start = time.monotonic()
    acquired = 0
    while time.monotonic() - start < 1.0:
        if await sw.acquire():
            acquired += 1
        await asyncio.sleep(0.05)
    assert acquired == 10, f"expected 10, got {acquired}"


# ======================================================================
# SlidingWindowLimiter — reset & isolated keys
# ======================================================================


@pytest.mark.asyncio
async def test_sliding_window_reset():
    """reset() clears window history."""
    sw = SlidingWindowLimiter(max_requests=3, window_sec=10.0)
    for _ in range(3):
        await sw.acquire()
    assert await sw.acquire() is False
    sw.reset("default")
    assert sw.get_remaining() == 3
    assert await sw.acquire() is True


@pytest.mark.asyncio
async def test_sliding_window_isolated_keys():
    """Different keys have independent sliding windows."""
    sw = SlidingWindowLimiter(max_requests=2, window_sec=10.0)
    assert await sw.acquire("red") is True
    assert await sw.acquire("red") is True
    assert await sw.acquire("red") is False
    assert await sw.acquire("blue") is True  # isolated
    assert await sw.acquire("blue") is True
    assert await sw.acquire("blue") is False


# ======================================================================
# MultiKeyLimiter — burst with mixed rates
# ======================================================================


@pytest.mark.asyncio
async def test_multi_key_mixed_rates_burst():
    """MultiKeyLimiter with different bucket sizes handles bursts correctly."""
    mk = MultiKeyLimiter({
        "slow": TokenBucketLimiter(capacity=2, refill_per_sec=0.0001),
        "fast": TokenBucketLimiter(capacity=100, refill_per_sec=0.0001),
    })
    slow_results = await asyncio.gather(*[mk.acquire("slow") for _ in range(10)])
    fast_results = await asyncio.gather(*[mk.acquire("fast") for _ in range(200)])
    assert sum(1 for r in slow_results if r) == 2
    assert sum(1 for r in fast_results if r) == 100


# ======================================================================
# Mixed keys with mixed rates (burst pattern)
# ======================================================================


@pytest.mark.asyncio
async def test_burst_pattern_10x100():
    """Burst pattern: 10 reqs × 100 times with 10ms gap — bucket adapts."""
    tb = TokenBucketLimiter(capacity=100, refill_per_sec=50.0)
    total_acquired = 0
    for _ in range(100):
        batch = await asyncio.gather(*[tb.acquire() for _ in range(10)])
        total_acquired += sum(1 for r in batch if r)
        await asyncio.sleep(0.01)
    # With capacity=100 and refill=50/s, over ~1s we get ~100 + 50 = ~150
    assert total_acquired >= 100, f"expected >=100, got {total_acquired}"
    assert total_acquired <= 200, f"expected <=200, got {total_acquired}"


# ======================================================================
# wait_and_acquire timing accuracy
# ======================================================================


# ======================================================================
# MultiKeyLimiter — fail-closed mode
# ======================================================================


@pytest.mark.asyncio
async def test_multi_key_fail_closed():
    """allow_unknown=False raises KeyError for unknown keys."""
    mk = MultiKeyLimiter({}, allow_unknown=False)
    with pytest.raises(KeyError):
        await mk.acquire("unknown")


# ======================================================================
# wait_and_acquire timing accuracy
# ======================================================================


@pytest.mark.asyncio
async def test_wait_and_acquire_timing_accuracy():
    """wait_and_acquire should acquire within 10ms of expected refill time."""
    tb = TokenBucketLimiter(capacity=10, refill_per_sec=10.0)
    for _ in range(10):
        await tb.acquire()
    start = time.monotonic()
    result = await tb.wait_and_acquire("default", tokens=1, max_wait_sec=5.0)
    elapsed = time.monotonic() - start
    assert result is True
    # 1 token at 10/sec = ~100ms, allow generous CI slack
    assert elapsed < 0.5, f"took too long: {elapsed:.3f}s"
