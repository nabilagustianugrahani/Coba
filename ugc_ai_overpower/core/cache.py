"""Cache backends for UGC AI Overpower.

Provides an abstract `CacheBackend` interface with three concrete
implementations: `MemoryCache` (LRU + TTL, in-process), `RedisCache`
(durable, lazy-connect, fail-soft), and `TieredCache` (L1 memory +
L2 redis). Includes a `@cached` decorator that memoises async
function results via any `CacheBackend`.
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Optional

log = logging.getLogger(__name__)

__all__ = [
    "CacheBackend",
    "MemoryCache",
    "RedisCache",
    "TieredCache",
    "cached",
]


class CacheBackend(ABC):
    """Abstract async cache interface."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]: ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_sec: int = 3600) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def clear(self) -> None: ...


class MemoryCache(CacheBackend):
    """LRU + TTL cache, in-process, safe under asyncio gather."""

    def __init__(self, max_size: int = 10000, default_ttl: int = 3600) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._data: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()
        self._lock = asyncio.Lock()

    @staticmethod
    def _now() -> float:
        return asyncio.get_running_loop().time()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if self._now() >= expiry:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    async def set(self, key: str, value: Any, ttl_sec: int = 3600) -> None:
        if ttl_sec is None or ttl_sec <= 0:
            ttl_sec = self.default_ttl
        async with self._lock:
            self._data[key] = (value, self._now() + ttl_sec)
            self._data.move_to_end(key)
            while len(self._data) > self.max_size:
                self._data.popitem(last=False)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return False
            value, expiry = entry
            if self._now() >= expiry:
                del self._data[key]
                return False
            self._data.move_to_end(key)
            return True

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()


class RedisCache(CacheBackend):
    """Redis-backed cache using redis.asyncio. Lazy-connect, fail-soft."""

    def __init__(self, url: str = "redis://localhost:6379", default_ttl: int = 3600) -> None:
        self.url = url
        self.default_ttl = default_ttl
        self._client: Any = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is None:
                try:
                    import redis.asyncio as aioredis
                    self._client = aioredis.from_url(self.url, decode_responses=True)
                except Exception as exc:
                    log.warning("RedisCache connect failed (%s): %s", self.url, exc)
                    return None
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        try:
            client = await self._get_client()
            if client is None:
                return None
            raw = await client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            log.warning("RedisCache get failed for key=%s: %s", key, exc)
            return None

    async def set(self, key: str, value: Any, ttl_sec: int = 3600) -> None:
        try:
            client = await self._get_client()
            if client is None:
                return
            ttl = ttl_sec if (ttl_sec and ttl_sec > 0) else self.default_ttl
            await client.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception as exc:
            log.warning("RedisCache set failed for key=%s: %s", key, exc)

    async def delete(self, key: str) -> None:
        try:
            client = await self._get_client()
            if client is None:
                return
            await client.delete(key)
        except Exception as exc:
            log.warning("RedisCache delete failed for key=%s: %s", key, exc)

    async def exists(self, key: str) -> bool:
        try:
            client = await self._get_client()
            if client is None:
                return False
            return bool(await client.exists(key))
        except Exception as exc:
            log.warning("RedisCache exists failed for key=%s: %s", key, exc)
            return False

    async def clear(self) -> None:
        try:
            client = await self._get_client()
            if client is None:
                return
            await client.flushdb()
        except Exception as exc:
            log.warning("RedisCache clear failed: %s", exc)


class TieredCache(CacheBackend):
    """Two-tier cache: L1 (MemoryCache) in front of L2 (RedisCache).

    Reads consult L1 first, fall through to L2 and repopulate L1 on hit.
    Writes fan out to both tiers. Deletes and clear hit both tiers.
    """

    def __init__(self, l1: MemoryCache, l2: RedisCache) -> None:
        self.l1 = l1
        self.l2 = l2

    async def get(self, key: str) -> Optional[Any]:
        v = await self.l1.get(key)
        if v is not None:
            return v
        v = await self.l2.get(key)
        if v is not None:
            await self.l1.set(key, v)
        return v

    async def set(self, key: str, value: Any, ttl_sec: int = 3600) -> None:
        await self.l1.set(key, value, ttl_sec=ttl_sec)
        await self.l2.set(key, value, ttl_sec=ttl_sec)

    async def delete(self, key: str) -> None:
        await self.l1.delete(key)
        await self.l2.delete(key)

    async def exists(self, key: str) -> bool:
        if await self.l1.exists(key):
            return True
        return await self.l2.exists(key)

    async def clear(self) -> None:
        await self.l1.clear()
        await self.l2.clear()


def _make_key(fn_name: str, args: tuple, kwargs: dict, prefix: str) -> str:
    payload = json.dumps(
        [list(args), sorted(kwargs.items())],
        default=str,
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"{prefix}{fn_name}:{digest}"


# Module-level lock serialises cache misses so a thundering herd of
# concurrent identical calls collapses to a single underlying call.
_miss_lock = asyncio.Lock()


def cached(
    ttl_sec: int = 3600,
    key_prefix: str = "",
    backend: Optional[CacheBackend] = None,
):
    """Decorator that memoises async function results in a CacheBackend.

    Key = ``key_prefix + fn_name + sha256(json(args, kwargs, sorted))[:16]``.

    If ``backend`` is None, falls back to ``cached.default_backend``.
    If that's also None, the wrapped function runs uncached.
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            be = backend or cached.default_backend
            if be is None:
                return await fn(*args, **kwargs)
            key = _make_key(fn.__name__, args, kwargs, key_prefix)
            hit = await be.get(key)
            if hit is not None:
                return hit
            # serialise concurrent misses for the same key
            async with _miss_lock:
                hit = await be.get(key)
                if hit is not None:
                    return hit
                result = await fn(*args, **kwargs)
                await be.set(key, result, ttl_sec=ttl_sec)
                return result

        return wrapper

    return decorator


cached.default_backend: Optional[CacheBackend] = None
