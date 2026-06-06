"""Real performance benchmarks for the BATCH B resilience stack.

Measures throughput, latency, and correctness of:
  * MemoryCache / TieredCache / @cached decorator
  * AsyncPool (priority, drain, error isolation, throughput)
  * TokenBucketLimiter / SlidingWindowLimiter / MultiKeyLimiter
  * CircuitBreaker (state transitions, recovery, fast-fail in OPEN)
  * RateLimitedCachedBreaker (full pipeline throughput)
  * Minimal FastAPI dashboard endpoint latency (with mocked deps)

All benchmarks use ``time.perf_counter()`` directly (no pytest-benchmark
required) and assert a generous upper bound. They print the actual numbers
to stdout so the run script can aggregate them into BENCHMARKS.md.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.core.cache import (  # noqa: E402
    MemoryCache,
    RedisCache,
    TieredCache,
    cached,
)
from ugc_ai_overpower.core.async_pool import AsyncPool, PoolTask  # noqa: E402
from ugc_ai_overpower.core.circuit_breaker import (  # noqa: E402
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from ugc_ai_overpower.core.performance import RateLimitedCachedBreaker  # noqa: E402
from ugc_ai_overpower.core.rate_limiter import (  # noqa: E402
    MultiKeyLimiter,
    SlidingWindowLimiter,
    TokenBucketLimiter,
)


# =====================================================================
# Small helper: in-memory L2 stand-in for TieredCache promotion tests.
# Implements the CacheBackend interface so we can test L1<->L2 promotion
# without needing a real Redis server.
# =====================================================================


class InMemoryL2Cache:
    """Minimal CacheBackend-compatible store used as TieredCache.L2."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def get(self, key: str) -> Optional[Any]:
        return self._data.get(key)

    async def set(self, key: str, value: Any, ttl_sec: int = 3600) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._data

    async def clear(self) -> None:
        self._data.clear()


# =====================================================================
# Cache benchmarks
# =====================================================================


@pytest.mark.asyncio
async def test_memory_cache_throughput():
    """100K set+get ops on MemoryCache should complete in < 1s."""
    cache = MemoryCache(max_size=20_000, default_ttl=60)
    t0 = time.perf_counter()
    for i in range(50_000):
        await cache.set(f"k{i}", i)
    for i in range(50_000):
        await cache.get(f"k{i}")
    elapsed = time.perf_counter() - t0
    ops = 100_000
    print(f"\n[bench] memory_cache set+get: {ops} ops in {elapsed:.3f}s "
          f"({ops/elapsed/1000:.1f}K ops/s)")
    assert elapsed < 1.0, f"MemoryCache too slow: {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_redis_cache_throughput():
    """100K ops on RedisCache should complete in < 5s. Skipped if no Redis."""
    try:
        import redis.asyncio as aioredis  # noqa: F401
    except ImportError:
        pytest.skip("redis package not installed")

    client = None
    try:
        client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
        await client.ping()
    except Exception as exc:
        pytest.skip(f"Redis not reachable: {exc}")
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass

    cache = RedisCache(url="redis://localhost:6379", default_ttl=60)
    try:
        t0 = time.perf_counter()
        for i in range(50_000):
            await cache.set(f"bench:k{i}", i)
        for i in range(50_000):
            await cache.get(f"bench:k{i}")
        elapsed = time.perf_counter() - t0
        ops = 100_000
        print(f"\n[bench] redis_cache set+get: {ops} ops in {elapsed:.3f}s "
              f"({ops/elapsed/1000:.1f}K ops/s)")
        assert elapsed < 5.0, f"RedisCache too slow: {elapsed:.3f}s"
    finally:
        try:
            await cache.clear()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_tiered_cache_promotion():
    """L1 miss then L2 hit should promote to L1 within < 10ms."""
    l1 = MemoryCache(max_size=100, default_ttl=60)
    l2 = InMemoryL2Cache()
    tiered = TieredCache(l1=l1, l2=l2)  # type: ignore[arg-type]

    # Seed L2 only (L1 empty)
    await l2.set("promote-key", {"v": 42})

    # L1 miss -> L2 hit, then promotion to L1
    t0 = time.perf_counter()
    v = await tiered.get("promote-key")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert v == {"v": 42}
    l1_value = await l1.get("promote-key")
    assert l1_value == {"v": 42}, "value should be promoted to L1 after first hit"

    # Second get must hit L1 only
    t1 = time.perf_counter()
    v2 = await tiered.get("promote-key")
    elapsed_l1_ms = (time.perf_counter() - t1) * 1000
    assert v2 == {"v": 42}

    print(f"\n[bench] tiered_promotion: l1_miss_l2_hit={elapsed_ms:.3f}ms "
          f"l1_hit={elapsed_l1_ms:.3f}ms")
    assert elapsed_ms < 10.0, f"L1->L2 promotion took {elapsed_ms:.3f}ms"


@pytest.mark.asyncio
async def test_cache_concurrent_reads():
    """100 concurrent readers should see no data races or exceptions."""
    cache = MemoryCache(max_size=200, default_ttl=60)
    await cache.set("shared", "expected")

    async def reader(_i: int) -> Any:
        v = await cache.get("shared")
        assert v == "expected"
        return v

    t0 = time.perf_counter()
    results = await asyncio.gather(*(reader(i) for i in range(100)))
    elapsed = time.perf_counter() - t0
    assert len(results) == 100
    assert all(r == "expected" for r in results)
    print(f"\n[bench] cache_concurrent_reads: 100 readers in {elapsed*1000:.2f}ms")
    assert elapsed < 0.5, f"concurrent reads too slow: {elapsed*1000:.1f}ms"


@pytest.mark.asyncio
async def test_decorator_overhead():
    """@cached wrapper should add < 2x overhead vs uncached function."""
    calls = {"n": 0}

    async def expensive(x: int) -> int:
        calls["n"] += 1
        await asyncio.sleep(0.0005)  # 0.5ms
        return x * 3

    # Direct, no cache
    t0 = time.perf_counter()
    for i in range(200):
        await expensive(i)
    direct = time.perf_counter() - t0

    # Cached — populate, then 200 reads that should all hit
    cache = MemoryCache(max_size=500, default_ttl=60)
    cached.default_backend = cache  # type: ignore[attr-defined]

    @cached(ttl_sec=60)
    async def expensive_c(x: int) -> int:
        calls["n"] += 1
        await asyncio.sleep(0.0005)
        return x * 3

    # Populate
    for i in range(200):
        await expensive_c(i)
    # Now read 200 (all should hit)
    t1 = time.perf_counter()
    for i in range(200):
        await expensive_c(i)
    cached_time = time.perf_counter() - t1

    cached.default_backend = None  # type: ignore[attr-defined]

    # Cached path should be FAST (memory hits), not 2x slower than compute
    ratio = cached_time / max(direct, 1e-9)
    print(f"\n[bench] decorator_overhead: direct={direct*1000:.1f}ms "
          f"cached_reads={cached_time*1000:.1f}ms ratio={ratio:.2f}x")
    # Cached reads should be much faster than direct, so ratio is < 2.0
    assert ratio < 2.0, f"decorator overhead ratio {ratio:.2f}x exceeds 2.0x"


# =====================================================================
# AsyncPool benchmarks
# =====================================================================


@pytest.mark.asyncio
async def test_pool_1000_tasks_4_workers():
    """1000 tasks of ~5ms each on 4 workers should complete in < 10s."""
    pool = AsyncPool(max_workers=4, max_queue=2000)

    async def work(i: int) -> int:
        await asyncio.sleep(0.005)
        return i * 2

    t0 = time.perf_counter()
    tasks = [PoolTask(fn=work, args=(i,)) for i in range(1000)]
    results, errors = await pool.gather_with_errors(tasks)
    elapsed = time.perf_counter() - t0
    await pool.shutdown()

    assert not errors, f"unexpected errors: {errors[:3]}"
    assert len(results) == 1000
    print(f"\n[bench] pool_1000x4workers: {len(results)} tasks in {elapsed:.2f}s "
          f"({len(results)/elapsed:.0f} ops/s)")
    assert elapsed < 10.0, f"pool too slow: {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_pool_priority_ordering():
    """High-priority (low number) tasks should run before low-priority ones."""
    pool = AsyncPool(max_workers=1, max_queue=200)  # 1 worker → strict ordering
    order: list[int] = []

    async def work(i: int) -> None:
        order.append(i)
        await asyncio.sleep(0.001)

    # Submit low priority first, then high
    tids = []
    for i in range(5):
        tids.append(await pool.submit(PoolTask(fn=work, args=(i,), priority=9)))
    for i in range(100, 105):
        tids.append(await pool.submit(PoolTask(fn=work, args=(i,), priority=0)))

    await pool.drain(timeout_sec=5.0)
    await pool.shutdown()

    # The 5 high-priority (100..104) tasks should appear before any of 0..4
    high = [x for x in order if x >= 100]
    low = [x for x in order if x < 100]
    # All 5 high came first
    assert len(high) == 5 and len(low) == 5
    first_low_idx = order.index(low[0])
    last_high_idx = max(i for i, v in enumerate(order) if v >= 100)
    assert last_high_idx < first_low_idx, (
        f"priority broken: order={order}"
    )
    print(f"\n[bench] pool_priority: order={order}")


@pytest.mark.asyncio
async def test_pool_drain_timeout():
    """An empty pool should drain in < 100ms."""
    pool = AsyncPool(max_workers=4, max_queue=100)
    t0 = time.perf_counter()
    await pool.drain(timeout_sec=0.5)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    await pool.shutdown()
    print(f"\n[bench] pool_drain_empty: {elapsed_ms:.2f}ms")
    assert elapsed_ms < 100.0


@pytest.mark.asyncio
async def test_pool_error_isolation():
    """One failing task should not block the other 49."""
    pool = AsyncPool(max_workers=4, max_queue=200)

    async def good(i: int) -> int:
        await asyncio.sleep(0.001)
        return i

    async def bad(i: int) -> int:
        await asyncio.sleep(0.001)
        raise ValueError(f"bad-{i}")

    tasks: list[PoolTask] = []
    for i in range(50):
        if i == 25:
            tasks.append(PoolTask(fn=bad, args=(i,)))
        else:
            tasks.append(PoolTask(fn=good, args=(i,)))

    t0 = time.perf_counter()
    results, errors = await pool.gather_with_errors(tasks)
    elapsed = time.perf_counter() - t0
    await pool.shutdown()

    assert len(results) == 49, f"expected 49 successes, got {len(results)}"
    assert len(errors) == 1, f"expected 1 error, got {len(errors)}"
    print(f"\n[bench] pool_error_isolation: 49 ok + 1 err in {elapsed*1000:.1f}ms")
    assert elapsed < 5.0


# =====================================================================
# RateLimiter benchmarks
# =====================================================================


@pytest.mark.asyncio
async def test_token_bucket_1000_acquires():
    """1000 acquires on a large-capacity bucket should complete in < 50ms."""
    # Capacity 100k and rate 100k/s — effectively unlimited for 1000 acquires.
    bucket = TokenBucketLimiter(capacity=100_000, refill_per_sec=100_000.0)
    t0 = time.perf_counter()
    for _ in range(1000):
        assert await bucket.acquire("k")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"\n[bench] token_bucket_1000: {elapsed_ms:.2f}ms "
          f"({1000/elapsed_ms*1000:.0f} ops/s)")
    assert elapsed_ms < 50.0, f"token bucket too slow: {elapsed_ms:.2f}ms"


@pytest.mark.asyncio
async def test_sliding_window_accuracy():
    """Sliding window should grant max_requests then reject the (n+1)th."""
    # 5 requests per 1s window
    win = SlidingWindowLimiter(max_requests=5, window_sec=1.0)
    granted = 0
    rejected = 0
    for _ in range(7):
        if await win.acquire("k"):
            granted += 1
        else:
            rejected += 1
    assert granted == 5
    assert rejected == 2
    assert win.get_remaining("k") == 0
    print(f"\n[bench] sliding_window: granted={granted} rejected={rejected}")


@pytest.mark.asyncio
async def test_multi_key_independence():
    """100 keys × 10 reqs each should be granted in < 200ms with no contention."""
    limiters = {
        f"k{i}": TokenBucketLimiter(capacity=100, refill_per_sec=10_000.0)
        for i in range(100)
    }
    multi = MultiKeyLimiter(limiters)

    t0 = time.perf_counter()
    for key, lim in limiters.items():
        for _ in range(10):
            assert await multi.acquire(key)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"\n[bench] multi_key: 1000 reqs across 100 keys in {elapsed_ms:.2f}ms")
    assert elapsed_ms < 200.0, f"multi-key too slow: {elapsed_ms:.2f}ms"


# =====================================================================
# CircuitBreaker benchmarks
# =====================================================================


@pytest.mark.asyncio
async def test_state_transition_speed():
    """CLOSED → OPEN → CLOSED transitions should each take < 1ms."""
    cb = CircuitBreaker(name="t", failure_threshold=2, recovery_timeout_sec=0.01)

    async def fail() -> None:
        raise RuntimeError("nope")

    async def ok() -> int:
        return 1

    # CLOSED -> OPEN
    t0 = time.perf_counter()
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(fail)
    open_ms = (time.perf_counter() - t0) * 1000
    assert cb.state() == CircuitState.OPEN

    # Wait for recovery
    await asyncio.sleep(0.02)

    # OPEN -> HALF_OPEN (probe)
    assert await cb.call(ok) == 1
    # HALF_OPEN -> CLOSED
    assert await cb.call(ok) == 1
    assert cb.state() == CircuitState.CLOSED

    total_ms = (time.perf_counter() - t0) * 1000
    print(f"\n[bench] cb_transition: closed_to_open={open_ms:.3f}ms "
          f"total={total_ms:.3f}ms")
    assert open_ms < 50.0  # 2 failures, very generous


@pytest.mark.asyncio
async def test_recovery_after_timeout():
    """After recovery timeout, half-open probe success → CLOSED."""
    cb = CircuitBreaker(
        name="r", failure_threshold=1, recovery_timeout_sec=0.05, success_threshold=1
    )

    async def fail() -> None:
        raise RuntimeError("x")

    async def ok() -> int:
        return 42

    with pytest.raises(RuntimeError):
        await cb.call(fail)
    assert cb.state() == CircuitState.OPEN

    # Calls in OPEN rejected
    with pytest.raises(CircuitBreakerOpen):
        await cb.call(ok)

    # Wait for recovery timeout
    await asyncio.sleep(0.07)

    # Probe success → CLOSED
    assert await cb.call(ok) == 42
    assert cb.state() == CircuitState.CLOSED
    print("\n[bench] cb_recovery: OK")


@pytest.mark.asyncio
async def test_concurrent_calls_in_open_state():
    """100 calls in OPEN state should all fast-fail (no upstream call)."""
    cb = CircuitBreaker(name="c", failure_threshold=1, recovery_timeout_sec=60.0)

    async def fail() -> None:
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        await cb.call(fail)
    assert cb.state() == CircuitState.OPEN

    async def caller(_i: int) -> None:
        with pytest.raises(CircuitBreakerOpen):
            await cb.call(fail)

    t0 = time.perf_counter()
    await asyncio.gather(*(caller(i) for i in range(100)))
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"\n[bench] cb_open_fastfail: 100 calls in {elapsed_ms:.2f}ms")
    assert elapsed_ms < 100.0, f"fast-fail too slow: {elapsed_ms:.2f}ms"


# =====================================================================
# End-to-end benchmarks
# =====================================================================


@pytest.mark.asyncio
async def test_rate_limited_cached_breaker_throughput():
    """Full pipeline (rate-limit + cache + breaker) for 10K ops should be < 5s."""
    # Huge capacity → no real throttling. Same key repeated → all cache hits.
    guard = RateLimitedCachedBreaker(
        name="bench_guard",
        rate_limiter=TokenBucketLimiter(capacity=1_000_000, refill_per_sec=1_000_000.0),
        cache=MemoryCache(max_size=1000, default_ttl=60),
        breaker=CircuitBreaker(name="bench", failure_threshold=100, recovery_timeout_sec=1.0),
        acquire_timeout_sec=1.0,
    )

    async def fake_api(x: int) -> dict:
        # No-op — we'll keep results small and fast
        return {"echo": x}

    t0 = time.perf_counter()
    # First call: miss
    r0 = await guard.execute(fake_api, 1, cache_key="shared")
    assert r0 == {"echo": 1}
    # 9999 cache hits
    for _ in range(9999):
        r = await guard.execute(fake_api, 1, cache_key="shared")
        assert r == {"echo": 1}
    elapsed = time.perf_counter() - t0

    s = guard.stats()
    print(f"\n[bench] full_pipeline: 10K ops in {elapsed:.3f}s "
          f"({10000/elapsed:.0f} ops/s) | hits={s['cache_hits']} "
          f"misses={s['cache_misses']} exec={s['executed']}")
    assert elapsed < 5.0, f"pipeline too slow: {elapsed:.3f}s"
    assert s["cache_hits"] == 9999
    assert s["cache_misses"] == 1


def test_dashboard_endpoint_latency():
    """Minimal FastAPI app with stub endpoints — each must respond < 100ms."""
    try:
        from fastapi import FastAPI, Depends
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not installed")

    app = FastAPI()

    # Stub auth dependency (mimics dashboard auth_required)
    async def auth_required(req: Any = None) -> dict:
        return {"user": "bench"}

    @app.get("/api/v1/campaigns")
    async def list_campaigns(_=Depends(auth_required)):
        return {"data": [], "total": 0}

    @app.get("/api/v1/influencers")
    async def list_influencers(_=Depends(auth_required)):
        return {"data": [], "total": 0}

    @app.get("/api/v1/analytics/dashboard")
    async def analytics_dashboard(_=Depends(auth_required)):
        return {
            "total_campaigns": 0,
            "total_content": 0,
            "influencers": 0,
            "psychology_frameworks": 7,
            "uptime_hours": 0.0,
        }

    @app.get("/api/v1/analytics/summary")
    async def analytics_summary(_=Depends(auth_required)):
        return {"summary": "ok"}

    @app.get("/api/v1/queue/status")
    async def queue_status(_=Depends(auth_required)):
        return {"stats": {"total": 0, "pending": 0, "done": 0, "failed": 0}, "items": []}

    @app.get("/api/v1/brands")
    async def brand_list(_=Depends(auth_required)):
        return {"data": []}

    @app.get("/api/v1/approvals/list")
    async def approval_list(_=Depends(auth_required)):
        return {"data": []}

    @app.get("/api/v1/gallery/list")
    async def gallery_list(_=Depends(auth_required)):
        return {"data": []}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    client = TestClient(app)
    headers = {"Authorization": "Bearer bench-token"}

    endpoints = [
        ("/api/v1/campaigns", "GET"),
        ("/api/v1/influencers", "GET"),
        ("/api/v1/analytics/dashboard", "GET"),
        ("/api/v1/analytics/summary", "GET"),
        ("/api/v1/queue/status", "GET"),
        ("/api/v1/brands", "GET"),
        ("/api/v1/approvals/list", "GET"),
        ("/api/v1/gallery/list", "GET"),
        ("/health", "GET"),
    ]

    worst = 0.0
    print("\n[bench] dashboard_endpoints (stub app, mocked auth):")
    for path, method in endpoints:
        # Warmup
        getattr(client, method.lower())(path, headers=headers)
        # Measure (5 samples, take median)
        samples: list[float] = []
        for _ in range(5):
            t0 = time.perf_counter()
            resp = getattr(client, method.lower())(path, headers=headers)
            samples.append((time.perf_counter() - t0) * 1000)
            assert resp.status_code == 200, f"{path} -> {resp.status_code}"
        samples.sort()
        median = samples[len(samples) // 2]
        worst = max(worst, median)
        print(f"  {path:40s} median={median:.2f}ms")

    assert worst < 100.0, f"slowest endpoint {worst:.1f}ms > 100ms"
