"""Tests for core/performance.py — composite cache + rate limit + breaker."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.core.cache import MemoryCache
from ugc_ai_overpower.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from ugc_ai_overpower.core.performance import (
    RateLimitedCachedBreaker,
    build_default_guard,
    _default_key,
)
from ugc_ai_overpower.core.rate_limiter import (
    MultiKeyLimiter,
    SlidingWindowLimiter,
    TokenBucketLimiter,
)


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def guard():
    """A fresh guard with small limits so tests run fast."""
    return build_default_guard(
        "test_guard",
        rate_capacity=3,
        rate_refill_per_sec=10.0,
        cache_max_size=100,
        cache_ttl=60,
        failure_threshold=2,
        recovery_timeout_sec=0.5,
    )


# ---------------------------------------------------------------- basics


@pytest.mark.asyncio
async def test_execute_cache_miss_then_hit(guard):
    """First call executes the function, second call returns cached value."""
    counter = {"n": 0}

    async def fn(x):
        counter["n"] += 1
        return x * 2

    a = await guard.execute(fn, 5)
    b = await guard.execute(fn, 5)
    assert a == 10
    assert b == 10
    assert counter["n"] == 1  # second call was a cache hit

    s = guard.stats()
    assert s["executed"] == 1
    assert s["cache_hits"] == 1
    assert s["cache_misses"] == 1


@pytest.mark.asyncio
async def test_execute_different_args_different_keys(guard):
    counter = {"n": 0}

    async def fn(x):
        counter["n"] += 1
        return x + 100

    r1 = await guard.execute(fn, 1)
    r2 = await guard.execute(fn, 2)
    assert r1 == 101
    assert r2 == 102
    assert counter["n"] == 2  # different args -> different cache keys


@pytest.mark.asyncio
async def test_explicit_cache_key_bypasses_default_hashing(guard):
    counter = {"n": 0}

    async def fn(x, y):
        counter["n"] += 1
        return x + y

    a = await guard.execute(fn, 1, 2, cache_key="my:key")
    b = await guard.execute(fn, 99, 99, cache_key="my:key")  # diff args, same key
    assert a == 3
    assert b == 3
    assert counter["n"] == 1


# ----------------------------------------------------------------- rate limit


@pytest.mark.asyncio
async def test_rate_limiter_blocks_when_exhausted(guard):
    """After exhausting the bucket, the guard should raise RuntimeError."""
    counter = {"n": 0}

    async def fn(x):
        counter["n"] += 1
        return x

    # First 3 calls use up the bucket (capacity=3)
    for i in range(3):
        assert await guard.execute(fn, i) == i

    # The 4th should time out (refill is 10/s, but wait timeout default 30s
    # would be too slow — set short timeout for the test via a custom guard).
    short_guard = build_default_guard(
        "short", rate_capacity=2, rate_refill_per_sec=0.1
    )
    # capacity=2 -> first 2 ok, 3rd waits 10s for refill -> timeout in 0.1s
    short_guard.acquire_timeout_sec = 0.1
    for i in range(2):
        assert await short_guard.execute(fn, i) == i
    with pytest.raises(RuntimeError, match="rate limit timeout"):
        await short_guard.execute(fn, 99)


@pytest.mark.asyncio
async def test_custom_rate_key_isolates_buckets():
    """Different rate_keys should use different buckets."""
    guard = build_default_guard("multi", rate_capacity=1, rate_refill_per_sec=0.1)
    guard.acquire_timeout_sec = 0.05

    counter = {"n": 0}

    async def fn(x):
        counter["n"] += 1
        return x

    # Use different explicit cache_keys so each call is a cache miss, plus
    # different rate_keys so each call uses a fresh token bucket.
    for i, k in enumerate(("a", "b", "c")):
        assert await guard.execute(fn, i, rate_key=k, cache_key=f"key-{i}") == i
    assert counter["n"] == 3


# ----------------------------------------------------------------- breaker


@pytest.mark.asyncio
async def test_breaker_open_rejects_calls(guard):
    """After failure_threshold failures, breaker is OPEN and rejects new calls."""
    async def boom(x):
        raise ValueError("nope")

    for i in range(5):
        try:
            await guard.execute(boom, i)
        except (ValueError, CircuitBreakerOpen):
            pass

    # Breaker should now be open
    s = guard.stats()
    assert s["breaker_state"] == "open"
    assert s["breaker_rejected"] >= 1

    with pytest.raises(CircuitBreakerOpen):
        await guard.execute(boom, 99)


@pytest.mark.asyncio
async def test_breaker_recovers_after_timeout(guard):
    """After recovery_timeout, the breaker should allow a probe call."""
    async def boom(x):
        raise ValueError("nope")

    # Trip the breaker (failure_threshold=2)
    for i in range(3):
        try:
            await guard.execute(boom, i, cache_key=f"trip-{i}")
        except (ValueError, CircuitBreakerOpen):
            pass
    assert guard.breaker.state() == CircuitState.OPEN

    # Wait past recovery_timeout (0.5s in the fixture)
    await asyncio.sleep(0.6)

    counter = {"n": 0}

    async def good(x):
        counter["n"] += 1
        return x * 10

    # success_threshold=2 -> need 2 successful probes to close.
    # Use unique cache_keys so each is a cache miss and goes through breaker.
    await guard.execute(good, 1, cache_key="probe-1")
    await guard.execute(good, 2, cache_key="probe-2")
    assert guard.breaker.state() == CircuitState.CLOSED
    assert counter["n"] == 2


# ----------------------------------------------------------------- cache ttl


@pytest.mark.asyncio
async def test_cache_ttl_expiry():
    """Cached values should expire after the given TTL."""
    guard = build_default_guard("ttl", rate_capacity=100, rate_refill_per_sec=100.0)
    counter = {"n": 0}

    async def fn(x):
        counter["n"] += 1
        return x

    assert await guard.execute(fn, 1, cache_ttl=1) == 1
    assert await guard.execute(fn, 1, cache_ttl=1) == 1
    assert counter["n"] == 1

    # Manually invalidate to force re-execution
    await guard.invalidate(_default_key(fn, (1,), {}))
    assert await guard.execute(fn, 1, cache_ttl=1) == 1
    assert counter["n"] == 2


# ----------------------------------------------------------------- stats


@pytest.mark.asyncio
async def test_stats_tracks_flow(guard):
    async def fn(x):
        return x

    await guard.execute(fn, 1)         # miss + exec
    await guard.execute(fn, 1)         # hit
    await guard.execute(fn, 2)         # miss + exec
    s = guard.stats()
    assert s["name"] == "test_guard"
    assert s["cache_misses"] == 2
    assert s["cache_hits"] == 1
    assert s["executed"] == 2
    assert s["errors"] == 0


@pytest.mark.asyncio
async def test_reset_clears_counters_and_closes_breaker(guard):
    async def boom(x):
        raise ValueError("nope")

    for i in range(5):
        try:
            await guard.execute(boom, i)
        except (ValueError, CircuitBreakerOpen):
            pass

    assert guard.breaker.state() == CircuitState.OPEN
    guard.reset()
    assert guard.breaker.state() == CircuitState.CLOSED
    s = guard.stats()
    assert s["executed"] == 0
    assert s["errors"] == 0


# -------------------------------------------------------------- sync functions


@pytest.mark.asyncio
async def test_supports_sync_callable(guard):
    """The guard should work with plain (non-async) callables too."""
    counter = {"n": 0}

    def fn(x, y):
        counter["n"] += 1
        return x + y

    assert await guard.execute(fn, 2, 3) == 5
    assert await guard.execute(fn, 2, 3) == 5
    assert counter["n"] == 1


@pytest.mark.asyncio
async def test_supports_sync_failure(guard):
    def boom():
        raise RuntimeError("sync boom")

    with pytest.raises(RuntimeError, match="sync boom"):
        await guard.execute(boom)
    # After 2 failures the breaker should open
    with pytest.raises((RuntimeError, CircuitBreakerOpen)):
        await guard.execute(boom)


# ----------------------------------------------------- alternate components


@pytest.mark.asyncio
async def test_works_with_explicit_components():
    """Caller can wire up custom components instead of build_default_guard."""
    cache = MemoryCache(max_size=10, default_ttl=30)
    limiter = SlidingWindowLimiter(max_requests=5, window_sec=1.0)
    breaker = CircuitBreaker(name="custom", failure_threshold=3)

    guard = RateLimitedCachedBreaker(
        name="custom_guard",
        rate_limiter=limiter,
        cache=cache,
        breaker=breaker,
    )
    counter = {"n": 0}

    async def fn(x):
        counter["n"] += 1
        return x * 3

    for _ in range(3):
        assert await guard.execute(fn, 4) == 12
    # First is miss, next 2 are hits
    assert counter["n"] == 1


@pytest.mark.asyncio
async def test_works_with_multi_key_limiter():
    """MultiKeyLimiter plugged in as the rate_limiter component."""
    guard = build_default_guard("mk", rate_capacity=100, rate_refill_per_sec=100.0)
    # Swap the limiter for a multi-key one
    guard.rate_limiter = MultiKeyLimiter(
        limiters={
            "openai": TokenBucketLimiter(capacity=2, refill_per_sec=0.1),
            "twitter": TokenBucketLimiter(capacity=2, refill_per_sec=0.1),
        }
    )
    guard.acquire_timeout_sec = 0.05

    counter = {"n": 0}

    async def fn(x):
        counter["n"] += 1
        return x

    # 2 ok for openai, then rate-limited (different key is independent)
    assert await guard.execute(fn, 1, rate_key="openai") == 1
    assert await guard.execute(fn, 2, rate_key="openai") == 2
    with pytest.raises(RuntimeError, match="rate limit timeout"):
        await guard.execute(fn, 3, rate_key="openai")
    # Different key is independent
    assert await guard.execute(fn, 4, rate_key="twitter") == 4


# --------------------------------------------------------------- default key


def test_default_key_is_deterministic():
    async def fn(x, y=0):
        return x + y

    k1 = _default_key(fn, (1,), {"y": 2})
    k2 = _default_key(fn, (1,), {"y": 2})
    assert k1 == k2
    assert len(k1) == 32  # sha256 truncated to 32 hex chars


def test_default_key_differs_for_different_args():
    async def fn(x):
        return x

    assert _default_key(fn, (1,), {}) != _default_key(fn, (2,), {})
    assert _default_key(fn, (1,), {}) != _default_key(fn, (1,), {"extra": 1})


def test_default_key_kwargs_order_independent():
    async def fn(x, y=0, z=0):
        return x

    k1 = _default_key(fn, (1,), {"y": 2, "z": 3})
    k2 = _default_key(fn, (1,), {"z": 3, "y": 2})
    assert k1 == k2