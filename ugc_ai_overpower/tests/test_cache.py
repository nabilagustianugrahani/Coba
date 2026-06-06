"""Tests for core/cache.py — CacheBackend, MemoryCache, RedisCache, TieredCache, @cached."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.core.cache import (  # noqa: E402
    CacheBackend,
    MemoryCache,
    TieredCache,
    cached,
)

try:
    import redis.asyncio  # noqa: F401
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

requires_redis = pytest.mark.skipif(not HAS_REDIS, reason="redis package not installed")


# ─── MemoryCache tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_get_set_roundtrip():
    cache = MemoryCache()
    await cache.set("k1", {"v": 1})
    result = await cache.get("k1")
    assert result == {"v": 1}


@pytest.mark.asyncio
async def test_memory_get_missing_returns_none():
    cache = MemoryCache()
    assert await cache.get("nope") is None


@pytest.mark.asyncio
async def test_memory_delete():
    cache = MemoryCache()
    await cache.set("k1", "v1")
    await cache.delete("k1")
    assert await cache.get("k1") is None
    assert await cache.exists("k1") is False


@pytest.mark.asyncio
async def test_memory_exists():
    cache = MemoryCache()
    assert await cache.exists("k1") is False
    await cache.set("k1", "v1")
    assert await cache.exists("k1") is True


@pytest.mark.asyncio
async def test_memory_clear():
    cache = MemoryCache()
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.clear()
    assert await cache.get("a") is None
    assert await cache.get("b") is None
    assert await cache.exists("a") is False


@pytest.mark.asyncio
async def test_memory_ttl_expiry():
    cache = MemoryCache(default_ttl=3600)
    await cache.set("ephemeral", "x", ttl_sec=0.1)
    assert await cache.get("ephemeral") == "x"
    await asyncio.sleep(0.2)
    assert await cache.get("ephemeral") is None
    assert await cache.exists("ephemeral") is False


@pytest.mark.asyncio
async def test_memory_lru_eviction():
    cache = MemoryCache(max_size=3, default_ttl=3600)
    await cache.set("k1", 1)
    await cache.set("k2", 2)
    await cache.set("k3", 3)
    await cache.set("k4", 4)  # evicts k1 (oldest)
    await cache.set("k5", 5)  # evicts k2
    assert await cache.get("k1") is None
    assert await cache.get("k2") is None
    assert await cache.get("k3") == 3
    assert await cache.get("k4") == 4
    assert await cache.get("k5") == 5


@pytest.mark.asyncio
async def test_memory_default_ttl_applied():
    cache = MemoryCache(default_ttl=3600)
    # Setting without explicit ttl_sec should use default (and not expire instantly)
    await cache.set("p", "v")
    assert await cache.get("p") == "v"


@pytest.mark.asyncio
async def test_memory_thread_safety_under_gather():
    cache = MemoryCache(max_size=1000, default_ttl=3600)
    async def writer(i: int):
        await cache.set(f"k{i}", i)
    await asyncio.gather(*[writer(i) for i in range(50)])
    for i in range(50):
        assert await cache.get(f"k{i}") == i


@pytest.mark.asyncio
async def test_memory_none_values_cached_explicitly():
    """Documented behaviour: None is stored and returned as a real value
    (distinguishable from a miss). This keeps `await get` symmetric with
    `await set` and avoids the ambiguity where None could mean 'miss'."""
    cache = MemoryCache()
    assert await cache.get("absent") is None  # miss → None
    await cache.set("explicit_none", None)
    assert await cache.exists("explicit_none") is True
    assert await cache.get("explicit_none") is None  # hit → None (value stored)


# ─── RedisCache tests (skip if redis not installed) ──────────────────


@requires_redis
@pytest.mark.asyncio
async def test_redis_connection_failure_graceful():
    from ugc_ai_overpower.core.cache import RedisCache
    # bad URL → connection should fail gracefully
    rc = RedisCache(url="redis://127.0.0.1:1", default_ttl=60)
    # get on a never-connected cache should return None without raising
    result = await rc.get("missing")
    assert result is None
    # exists on a never-connected cache should return False
    assert await rc.exists("missing") is False


@requires_redis
@pytest.mark.asyncio
async def test_redis_get_missing_returns_none():
    from ugc_ai_overpower.core.cache import RedisCache
    rc = RedisCache(url="redis://127.0.0.1:6379", default_ttl=60)
    # First call to a non-running redis should fail → None
    result = await rc.get("definitely_not_there")
    assert result is None


@requires_redis
@pytest.mark.asyncio
async def test_redis_set_failure_noop():
    from ugc_ai_overpower.core.cache import RedisCache
    rc = RedisCache(url="redis://127.0.0.1:1", default_ttl=60)
    # Should not raise even though connection fails
    await rc.set("k", "v")
    # And after that, get should still return None
    assert await rc.get("k") is None


# ─── TieredCache tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tiered_l1_hit_skips_l2():
    l1 = MemoryCache()
    l2 = MemoryCache()
    await l1.set("k", "from_l1")
    l2.get = AsyncMock(wraps=l2.get)  # track calls
    tiered = TieredCache(l1=l1, l2=l2)
    result = await tiered.get("k")
    assert result == "from_l1"
    l2.get.assert_not_called()


@pytest.mark.asyncio
async def test_tiered_l1_miss_populates_l1():
    l1 = MemoryCache()
    l2 = MemoryCache()
    await l2.set("k", "from_l2")
    tiered = TieredCache(l1=l1, l2=l2)
    result = await tiered.get("k")
    assert result == "from_l2"
    # L1 should now be populated
    assert await l1.get("k") == "from_l2"


@pytest.mark.asyncio
async def test_tiered_set_writes_both():
    l1 = MemoryCache()
    l2 = MemoryCache()
    l1.set = AsyncMock(wraps=l1.set)
    l2.set = AsyncMock(wraps=l2.set)
    tiered = TieredCache(l1=l1, l2=l2)
    await tiered.set("k", "v")
    l1.set.assert_called_once()
    l2.set.assert_called_once()
    assert await l1.get("k") == "v"
    assert await l2.get("k") == "v"


@pytest.mark.asyncio
async def test_tiered_clear_clears_both():
    l1 = MemoryCache()
    l2 = MemoryCache()
    await l1.set("a", 1)
    await l2.set("b", 2)
    tiered = TieredCache(l1=l1, l2=l2)
    await tiered.clear()
    assert await l1.get("a") is None
    assert await l2.get("b") is None


# ─── @cached decorator tests ───────────────────────────────────────


@pytest.mark.asyncio
async def test_decorator_caches_result():
    backend = MemoryCache()
    calls = {"n": 0}

    @cached(backend=backend, ttl_sec=60)
    async def slow(x: int) -> int:
        calls["n"] += 1
        return x * 2

    assert await slow(5) == 10
    assert await slow(5) == 10
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_decorator_different_args_different_keys():
    backend = MemoryCache()
    calls = {"n": 0}

    @cached(backend=backend, ttl_sec=60)
    async def fn(x: int) -> int:
        calls["n"] += 1
        return x + 1

    assert await fn(1) == 2
    assert await fn(2) == 3
    assert await fn(1) == 2
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_decorator_invalidation_on_delete():
    backend = MemoryCache()
    calls = {"n": 0}

    @cached(backend=backend, ttl_sec=60)
    async def fn(x: int) -> int:
        calls["n"] += 1
        return x

    assert await fn(1) == 1
    assert await fn(1) == 1
    assert calls["n"] == 1
    # delete the underlying key by reconstructing it
    import hashlib
    payload = json.dumps([[1], []], sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    key = f"fn:{digest}"
    await backend.delete(key)
    assert await fn(1) == 1
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_decorator_default_backend():
    # Set module-level default backend
    backend = MemoryCache()
    cached.default_backend = backend
    calls = {"n": 0}

    @cached(ttl_sec=60)
    async def fn(x: int) -> int:
        calls["n"] += 1
        return x * 3

    assert await fn(7) == 21
    assert await fn(7) == 21
    assert calls["n"] == 1
    # cleanup
    cached.default_backend = None


@pytest.mark.asyncio
async def test_decorator_concurrent_calls_call_fn_once():
    backend = MemoryCache()
    calls = {"n": 0}

    @cached(backend=backend, ttl_sec=60)
    async def fn(x: int) -> int:
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return x

    results = await asyncio.gather(*[fn(42) for _ in range(10)])
    assert all(r == 42 for r in results)
    assert calls["n"] == 1


# ─── Edge case tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edge_empty_key():
    cache = MemoryCache()
    await cache.set("", "empty_value")
    assert await cache.get("") == "empty_value"
    assert await cache.exists("") is True


@pytest.mark.asyncio
async def test_edge_unicode_key():
    cache = MemoryCache()
    key = "ключ:🦀"
    await cache.set(key, {"emoji": "✨"})
    assert await cache.get(key) == {"emoji": "✨"}
    assert await cache.exists(key) is True


@pytest.mark.asyncio
async def test_edge_large_value():
    cache = MemoryCache(max_size=10, default_ttl=3600)
    big = {f"k{i}": "x" * 1000 for i in range(100)}  # ~100KB-ish
    await cache.set("big", big)
    result = await cache.get("big")
    assert result == big
    assert len(result) == 100
