"""Tests for core.rate_limiter.

Covers TokenBucketLimiter, SlidingWindowLimiter, MultiKeyLimiter, the
``wait_and_acquire`` polling helper, and async concurrency safety.
"""
import asyncio
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.core.rate_limiter import (  # noqa: E402
    MultiKeyLimiter,
    RateLimiter,
    SlidingWindowLimiter,
    TokenBucketLimiter,
)


# ---------------------------------------------------------------------------
# TokenBucketLimiter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_bucket_capacity_then_exhaust():
    """1. capacity=5: first 5 acquires True, 6th False."""
    tb = TokenBucketLimiter(capacity=5, refill_per_sec=1.0)
    results = [await tb.acquire() for _ in range(6)]
    assert results[:5] == [True, True, True, True, True]
    assert results[5] is False


@pytest.mark.asyncio
async def test_token_bucket_refill_after_wait():
    """2. After waiting longer than 1/refill_per_sec, a token is available again."""
    tb = TokenBucketLimiter(capacity=2, refill_per_sec=10.0)
    assert await tb.acquire() is True
    assert await tb.acquire() is True
    assert await tb.acquire() is False
    await asyncio.sleep(0.15)  # ~1.5 tokens refilled
    assert await tb.acquire() is True


@pytest.mark.asyncio
async def test_token_bucket_remaining_decreases_to_zero():
    """3. get_remaining decreases as tokens are spent, then stabilizes at 0."""
    tb = TokenBucketLimiter(capacity=3, refill_per_sec=0.0001)  # effectively no refill
    assert tb.get_remaining() == 3
    await tb.acquire()
    assert tb.get_remaining() == 2
    await tb.acquire()
    assert tb.get_remaining() == 1
    await tb.acquire()
    assert tb.get_remaining() == 0
    assert tb.get_remaining() == 0  # stays at 0


@pytest.mark.asyncio
async def test_token_bucket_reset_restores_capacity():
    """4. reset() restores the bucket to full capacity."""
    tb = TokenBucketLimiter(capacity=5, refill_per_sec=0.0001)
    for _ in range(5):
        assert await tb.acquire() is True
    assert await tb.acquire() is False
    tb.reset("default")
    assert tb.get_remaining() == 5
    assert await tb.acquire() is True


@pytest.mark.asyncio
async def test_token_bucket_independent_keys():
    """5. Different keys do not share a bucket."""
    tb = TokenBucketLimiter(capacity=2, refill_per_sec=0.0001)
    assert await tb.acquire("a") is True
    assert await tb.acquire("a") is True
    assert await tb.acquire("a") is False
    # 'b' untouched
    assert await tb.acquire("b") is True
    assert await tb.acquire("b") is True
    assert await tb.acquire("b") is False


@pytest.mark.asyncio
async def test_token_bucket_tokens_two_request():
    """6. A request of tokens=2 consumes 2 from the bucket."""
    tb = TokenBucketLimiter(capacity=5, refill_per_sec=0.0001)
    assert await tb.acquire(tokens=2) is True
    assert tb.get_remaining() == 3
    assert await tb.acquire(tokens=3) is True
    assert tb.get_remaining() == 0
    assert await tb.acquire(tokens=1) is False


@pytest.mark.asyncio
async def test_token_bucket_never_exceeds_capacity():
    """7. Refill is capped at capacity even after very long idle periods."""
    tb = TokenBucketLimiter(capacity=3, refill_per_sec=100.0)
    await asyncio.sleep(0.5)  # would accrue 50 tokens uncapped
    assert tb.get_remaining() == 3


# ---------------------------------------------------------------------------
# SlidingWindowLimiter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sliding_window_max_then_block():
    """8. max=3, window=1s: 3 quick acquires True, 4th False."""
    sw = SlidingWindowLimiter(max_requests=3, window_sec=1.0)
    assert await sw.acquire() is True
    assert await sw.acquire() is True
    assert await sw.acquire() is True
    assert await sw.acquire() is False


@pytest.mark.asyncio
async def test_sliding_window_recovers_after_window():
    """9. After the window elapses, new acquires are allowed again."""
    sw = SlidingWindowLimiter(max_requests=2, window_sec=0.2)
    assert await sw.acquire() is True
    assert await sw.acquire() is True
    assert await sw.acquire() is False
    await asyncio.sleep(0.25)
    assert await sw.acquire() is True


@pytest.mark.asyncio
async def test_sliding_window_sliding_behavior():
    """10. Old timestamps drop off as time passes (true sliding, not fixed buckets)."""
    sw = SlidingWindowLimiter(max_requests=2, window_sec=0.5)
    assert await sw.acquire() is True
    await asyncio.sleep(0.6)  # first request drops out of window
    assert await sw.acquire() is True  # second batch slot 1
    assert await sw.acquire() is True  # second batch slot 2
    assert await sw.acquire() is False  # window full again


@pytest.mark.asyncio
async def test_sliding_window_get_remaining():
    """11. get_remaining accurately reflects the current window's free slots."""
    sw = SlidingWindowLimiter(max_requests=4, window_sec=1.0)
    assert sw.get_remaining() == 4
    await sw.acquire()
    assert sw.get_remaining() == 3
    await sw.acquire()
    assert sw.get_remaining() == 2


@pytest.mark.asyncio
async def test_sliding_window_reset_clears_history():
    """12. reset() wipes the window — full quota is available again."""
    sw = SlidingWindowLimiter(max_requests=2, window_sec=10.0)
    assert await sw.acquire() is True
    assert await sw.acquire() is True
    assert await sw.acquire() is False
    sw.reset("default")
    assert sw.get_remaining() == 2
    assert await sw.acquire() is True


@pytest.mark.asyncio
async def test_sliding_window_independent_keys():
    """13. Per-key state is independent."""
    sw = SlidingWindowLimiter(max_requests=1, window_sec=10.0)
    assert await sw.acquire("x") is True
    assert await sw.acquire("x") is False
    assert await sw.acquire("y") is True
    assert await sw.acquire("y") is False


# ---------------------------------------------------------------------------
# MultiKeyLimiter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_key_different_limits_per_key():
    """14. Each registered key gets its own limiter with its own quota."""
    mk = MultiKeyLimiter({
        "openai": TokenBucketLimiter(capacity=2, refill_per_sec=0.0001),
        "twitter": TokenBucketLimiter(capacity=5, refill_per_sec=0.0001),
    })
    assert await mk.acquire("openai") is True
    assert await mk.acquire("openai") is True
    assert await mk.acquire("openai") is False
    for _ in range(5):
        assert await mk.acquire("twitter") is True
    assert await mk.acquire("twitter") is False


@pytest.mark.asyncio
async def test_multi_key_unknown_key_allowed():
    """15. Unknown keys pass through (with a warning)."""
    mk = MultiKeyLimiter({})
    assert await mk.acquire("nope") is True
    assert await mk.acquire("anything") is True


# ---------------------------------------------------------------------------
# wait_and_acquire
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_and_acquire_succeeds():
    """16. wait_and_acquire returns True once tokens become available."""
    tb = TokenBucketLimiter(capacity=1, refill_per_sec=50.0)
    assert await tb.acquire() is True
    assert await tb.acquire() is False  # bucket empty
    result = await tb.wait_and_acquire("default", tokens=1, max_wait_sec=1.0)
    assert result is True


@pytest.mark.asyncio
async def test_wait_and_acquire_timeout():
    """17. wait_and_acquire returns False when max_wait_sec elapses first."""
    tb = TokenBucketLimiter(capacity=1, refill_per_sec=0.1)  # 10s for 1 token
    assert await tb.acquire() is True
    start = time.monotonic()
    result = await tb.wait_and_acquire("default", tokens=1, max_wait_sec=0.2)
    elapsed = time.monotonic() - start
    assert result is False
    assert 0.15 <= elapsed < 0.5  # ~0.2s, give CI some slack


@pytest.mark.asyncio
async def test_wait_and_acquire_tokens_zero():
    """18. tokens=0 is a no-op acquire — returns True immediately."""
    tb = TokenBucketLimiter(capacity=1, refill_per_sec=0.0001)
    result = await tb.wait_and_acquire("default", tokens=0, max_wait_sec=0.1)
    assert result is True


# ---------------------------------------------------------------------------
# Concurrency & edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_acquires_no_double_spend():
    """19. 10 concurrent acquires against capacity=5: exactly 5 succeed, 5 fail."""
    tb = TokenBucketLimiter(capacity=5, refill_per_sec=0.0001)
    results = await asyncio.gather(*[tb.acquire() for _ in range(10)])
    assert sum(1 for r in results if r) == 5
    assert sum(1 for r in results if not r) == 5


@pytest.mark.asyncio
async def test_token_bucket_partial_refill_timing():
    """20. After draining, a short wait produces a partial (not full) refill."""
    tb = TokenBucketLimiter(capacity=10, refill_per_sec=2.0)
    for _ in range(10):
        await tb.acquire()
    assert tb.get_remaining() == 0
    await asyncio.sleep(0.6)  # ~1.2 tokens expected
    rem = tb.get_remaining()
    assert 1 <= rem <= 2, f"expected partial refill in [1, 2], got {rem}"


@pytest.mark.asyncio
async def test_sliding_window_exactly_max_allowed_in_window():
    """21. Out of 10 attempts, exactly max_requests succeed before the window expires."""
    sw = SlidingWindowLimiter(max_requests=5, window_sec=10.0)
    successes = 0
    for _ in range(10):
        if await sw.acquire():
            successes += 1
    assert successes == 5


@pytest.mark.asyncio
async def test_token_bucket_default_key_is_default():
    """22. When no key is passed, the limiter uses the 'default' key."""
    tb = TokenBucketLimiter(capacity=1, refill_per_sec=0.0001)
    assert tb.get_remaining() == 1
    assert await tb.acquire() is True
    assert tb.get_remaining() == 0
    # Explicit "default" sees the same state
    assert await tb.acquire("default") is False


@pytest.mark.asyncio
async def test_multi_key_stats_per_inner_limiter():
    """23. get_remaining on MultiKeyLimiter reflects each inner limiter's state."""
    openai = TokenBucketLimiter(capacity=2, refill_per_sec=0.0001)
    twitter = TokenBucketLimiter(capacity=5, refill_per_sec=0.0001)
    mk = MultiKeyLimiter({"openai": openai, "twitter": twitter})
    await mk.acquire("openai")
    await mk.acquire("openai")
    assert mk.get_remaining("openai") == 0
    assert mk.get_remaining("twitter") == 5
    # stats() snapshot
    snap = mk.stats()
    assert snap["openai"]["remaining"] == 0
    assert snap["twitter"]["remaining"] == 5


@pytest.mark.asyncio
async def test_acquire_returns_bool_not_none():
    """24. acquire() must return a real bool, never None or a truthy non-bool."""
    tb = TokenBucketLimiter(capacity=1, refill_per_sec=0.0001)
    r_ok = await tb.acquire()
    assert r_ok is True
    assert isinstance(r_ok, bool)
    r_no = await tb.acquire()
    assert r_no is False
    assert isinstance(r_no, bool)


def test_reset_on_unknown_key_is_noop():
    """25. reset() on an unseen key must be a silent no-op (no exceptions)."""
    tb = TokenBucketLimiter(capacity=5, refill_per_sec=1.0)
    tb.reset("does_not_exist")
    assert tb.get_remaining("does_not_exist") == 5

    sw = SlidingWindowLimiter(max_requests=5, window_sec=1.0)
    sw.reset("does_not_exist")
    assert sw.get_remaining("does_not_exist") == 5

    mk = MultiKeyLimiter({})
    mk.reset("does_not_exist")  # must not raise
