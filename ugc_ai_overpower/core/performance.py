"""Unified performance wrapper — cache + rate limit + circuit breaker.

Combines the three resilience layers into a single decorator-friendly object.
`RateLimitedCachedBreaker.execute` checks the three guards in order:

    1. Circuit breaker — fail fast if the dependency is unhealthy.
    2. Rate limiter    — wait briefly if the per-key quota is exhausted.
    3. Cache           — return the stored value if the request is a replay.

On a successful call, the result is written back to the cache so subsequent
calls hit the L1/L2 store instead of the upstream API.

Typical usage:

    from ugc_ai_overpower.core.cache import MemoryCache
    from ugc_ai_overpower.core.rate_limiter import TokenBucketLimiter
    from ugc_ai_overpower.core.circuit_breaker import CircuitBreaker
    from ugc_ai_overpower.core.performance import RateLimitedCachedBreaker

    guard = RateLimitedCachedBreaker(
        name="openai_chat",
        rate_limiter=TokenBucketLimiter(capacity=60, refill_per_sec=1.0),
        cache=MemoryCache(max_size=10_000, default_ttl=300),
        breaker=CircuitBreaker(name="openai", failure_threshold=5, recovery_timeout_sec=30.0),
    )

    result = await guard.execute(call_openai, prompt="hello", cache_key="hello")

If `cache_key` is omitted, the wrapper falls back to ``fn.__name__`` plus a
deterministic hash of ``(args, kwargs)`` — handy when callers don't want to
think about keying.
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import inspect
import json
import logging
from typing import Any, Callable, Optional

from ugc_ai_overpower.core.cache import CacheBackend
from ugc_ai_overpower.core.circuit_breaker import CircuitBreaker
from ugc_ai_overpower.core.rate_limiter import RateLimiter

log = logging.getLogger(__name__)

__all__ = ["RateLimitedCachedBreaker", "build_default_guard"]


def _default_key(fn: Callable, args: tuple, kwargs: dict) -> str:
    """Produce a stable cache key from function identity + call signature.

    The hash covers ``fn.__qualname__`` and a JSON-serialised snapshot of
    ``args``/``kwargs`` (with sorted keys) so equivalent calls collide
    regardless of dict ordering.
    """
    h = hashlib.sha256()
    h.update((fn.__qualname__ or fn.__name__ or "fn").encode("utf-8"))
    try:
        payload = json.dumps(
            {"args": list(args), "kwargs": kwargs},
            sort_keys=True,
            default=str,
            ensure_ascii=False,
        )
    except (TypeError, ValueError):
        payload = repr((args, sorted(kwargs.items())))
    h.update(b"|")
    h.update(payload.encode("utf-8"))
    return h.hexdigest()[:32]


class RateLimitedCachedBreaker:
    """Composite guard: breaker → rate limit → cache → execute → cache write.

    Each check is cheap and ordered for the common case:
      * an unhealthy breaker is rejected immediately (no I/O).
      * an empty bucket short-circuits before any cache lookup.
      * a cache hit short-circuits before any upstream call.

    Parameters
    ----------
    name:
        Human-readable identifier used in logs and breaker stats.
    rate_limiter:
        Any object implementing the ``RateLimiter`` interface.
    cache:
        Any object implementing the ``CacheBackend`` interface.
    breaker:
        A ``CircuitBreaker`` instance (state, counters, transitions).
    acquire_timeout_sec:
        Maximum time to wait for a rate-limit token before giving up.
    """

    def __init__(
        self,
        name: str,
        rate_limiter: RateLimiter,
        cache: CacheBackend,
        breaker: CircuitBreaker,
        acquire_timeout_sec: float = 30.0,
    ) -> None:
        self.name = name
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.breaker = breaker
        self.acquire_timeout_sec = float(acquire_timeout_sec)
        # Local counters — useful for monitoring dashboards.
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "rate_limited": 0,
            "breaker_rejected": 0,
            "executed": 0,
            "errors": 0,
        }

    # ------------------------------------------------------------------ public

    async def execute(
        self,
        fn: Callable,
        *args: Any,
        cache_key: Optional[str] = None,
        cache_ttl: int = 3600,
        rate_key: str = "default",
        rate_tokens: int = 1,
        **kwargs: Any,
    ) -> Any:
        """Run ``fn`` with all three guards in place.

        Returns the cached value when one exists, otherwise awaits a fresh
        call through the breaker and writes the result back to the cache.

        Raises
        ------
        CircuitBreakerOpen
            If the breaker is open. Propagated unchanged so callers can
            surface a 503-style response.
        Exception
            Any exception raised by ``fn`` is re-raised after the breaker
            has recorded the failure.
        """
        key = cache_key or _default_key(fn, args, kwargs)

        # 1. Rate limit — wait briefly for a token, then proceed.
        # Done before the cache lookup so a stampeding herd of cache misses
        # can't burst past the upstream's per-second quota.
        if not await self.rate_limiter.wait_and_acquire(
            rate_key, tokens=rate_tokens, max_wait_sec=self.acquire_timeout_sec
        ):
            self._stats["rate_limited"] += 1
            log.warning("perf[%s]: rate limit timeout for key=%s", self.name, rate_key)
            raise RuntimeError(
                f"rate limit timeout for {self.name} key={rate_key} "
                f"after {self.acquire_timeout_sec}s"
            )

        # 2. Cache lookup — short-circuit on hit (no breaker round-trip).
        cached_value = await self.cache.get(key)
        if cached_value is not None:
            self._stats["cache_hits"] += 1
            log.debug("perf[%s]: cache hit key=%s", self.name, key)
            return cached_value

        # 3. Execute via breaker, then write through to cache.
        # breaker.call() handles the full state machine (CLOSED -> OPEN ->
        # HALF_OPEN -> CLOSED) including the recovery timeout probe.
        self._stats["cache_misses"] += 1
        try:
            result = await self.breaker.call(self._invoke, fn, *args, **kwargs)
        except Exception as exc:
            from ugc_ai_overpower.core.circuit_breaker import CircuitBreakerOpen
            if isinstance(exc, CircuitBreakerOpen):
                self._stats["breaker_rejected"] += 1
                log.warning("perf[%s]: breaker open, rejecting call", self.name)
            else:
                self._stats["errors"] += 1
            raise

        self._stats["executed"] += 1
        try:
            await self.cache.set(key, result, ttl_sec=cache_ttl)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("perf[%s]: cache write failed: %s", self.name, exc)

        log.debug(
            "perf[%s]: executed fn=%s key=%s",
            self.name, getattr(fn, "__name__", "?"), key,
        )
        return result

    async def invalidate(self, key_or_pattern: str) -> None:
        """Invalidate a single cache entry.

        The current ``CacheBackend`` interface only exposes single-key
        ``delete``; pattern-based invalidation is left to concrete
        implementations (e.g. a Redis-backed cache can extend it).
        """
        await self.cache.delete(key_or_pattern)

    def stats(self) -> dict:
        """Return a snapshot of wrapper-level counters.

        These complement the per-component stats (breaker, limiter, cache)
        by tracking the *flow* of calls through the composite guard.
        """
        return {
            "name": self.name,
            **self._stats,
            "breaker_state": self.breaker.state().value,
        }

    def reset(self) -> None:
        """Reset wrapper counters and force the breaker back to CLOSED."""
        self._stats = {k: 0 for k in self._stats}
        self.breaker.reset()


    # ----------------------------------------------------------------- helpers

    async def _invoke(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Call ``fn`` regardless of sync/async, then return its result.

        Kept as a thin helper so the breaker can wrap a single callable
        without us having to special-case coroutines inside ``breaker.call``.
        """
        if inspect.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        result = fn(*args, **kwargs)
        if inspect.iscoroutine(result):
            return await result
        return result


def build_default_guard(
    name: str,
    *,
    rate_capacity: int = 60,
    rate_refill_per_sec: float = 1.0,
    cache_max_size: int = 10_000,
    cache_ttl: int = 300,
    failure_threshold: int = 5,
    recovery_timeout_sec: float = 30.0,
) -> RateLimitedCachedBreaker:
    """Convenience builder for the common case.

    Wires up an in-memory cache, a token-bucket rate limiter, and a circuit
    breaker with sensible defaults. Useful for tests and for callers that
    don't need to tune each component individually.
    """
    # Imports kept local to avoid pulling cache/breaker at module import
    # time (helps test isolation and keeps the dependency graph shallow).
    from ugc_ai_overpower.core.cache import MemoryCache
    from ugc_ai_overpower.core.circuit_breaker import CircuitBreaker
    from ugc_ai_overpower.core.rate_limiter import TokenBucketLimiter

    cache = MemoryCache(max_size=cache_max_size, default_ttl=cache_ttl)
    limiter = TokenBucketLimiter(capacity=rate_capacity, refill_per_sec=rate_refill_per_sec)
    breaker = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout_sec=recovery_timeout_sec,
    )
    return RateLimitedCachedBreaker(
        name=name,
        rate_limiter=limiter,
        cache=cache,
        breaker=breaker,
    )
