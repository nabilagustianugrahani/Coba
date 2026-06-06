"""Rate limiters for API call throttling.

Three strategies:
  * TokenBucketLimiter  — capacity tokens, refill at refill_per_sec. Lazy refill on access.
  * SlidingWindowLimiter — track request timestamps in a deque; max_requests per window_sec.
  * MultiKeyLimiter — route per-key to a registered inner limiter (e.g., 60/min OpenAI,
    100/sec Twitter). Unknown keys are passed through with a warning.

All limiters are async-safe: per-instance ``asyncio.Lock`` guards the check-and-deduct
critical section, so concurrent acquires never double-spend tokens.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Any

log = logging.getLogger(__name__)

__all__ = [
    "RateLimiter",
    "TokenBucketLimiter",
    "SlidingWindowLimiter",
    "MultiKeyLimiter",
]

_DEFAULT_KEY = "default"
_POLL_INTERVAL_SEC = 0.05


class RateLimiter(ABC):
    """Abstract rate limiter.

    Subclasses must implement :meth:`acquire`, :meth:`get_remaining`, and :meth:`reset`.
    :meth:`wait_and_acquire` has a generic default that polls with ``asyncio.sleep``.
    """

    @abstractmethod
    async def acquire(self, key: str = _DEFAULT_KEY, tokens: int = 1) -> bool:
        """Try to consume ``tokens`` for ``key``. Returns True if granted, False otherwise."""

    async def wait_and_acquire(
        self,
        key: str,
        tokens: int = 1,
        max_wait_sec: float = 60.0,
    ) -> bool:
        """Block (asyncio.sleep in a polling loop) until tokens are available or the
        deadline elapses. Returns True on acquisition, False on timeout.
        """
        if tokens <= 0:
            return True
        deadline = time.monotonic() + max_wait_sec
        while True:
            if await self.acquire(key, tokens):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            await asyncio.sleep(min(_POLL_INTERVAL_SEC, remaining))

    @abstractmethod
    def get_remaining(self, key: str = _DEFAULT_KEY) -> int:
        """Tokens/requests still available for ``key`` right now."""

    @abstractmethod
    def reset(self, key: str = _DEFAULT_KEY) -> None:
        """Clear all state for ``key`` (no-op if unknown)."""


class TokenBucketLimiter(RateLimiter):
    """Token bucket: capacity tokens, refill at ``refill_per_sec``.

    On every access the bucket is lazily refilled based on elapsed monotonic time.
    ``min(capacity, current + elapsed * rate)`` ensures the bucket never overflows.
    """

    def __init__(self, capacity: int, refill_per_sec: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        if refill_per_sec <= 0:
            raise ValueError("refill_per_sec must be > 0")
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self._state: dict[str, dict[str, float]] = {}
        # threading.RLock so sync reads (get_remaining/reset) and async
        # acquires share the same critical section. Operations under the lock
        # never await, so a sync lock is safe in async contexts.
        self._lock = threading.RLock()

    def _refill(self, key: str, now: float) -> float:
        state = self._state.setdefault(
            key, {"tokens": float(self.capacity), "last_refill": now}
        )
        elapsed = now - state["last_refill"]
        if elapsed > 0:
            state["tokens"] = min(
                self.capacity, state["tokens"] + elapsed * self.refill_per_sec
            )
            state["last_refill"] = now
        return state["tokens"]

    async def acquire(self, key: str = _DEFAULT_KEY, tokens: int = 1) -> bool:
        """Atomically refill, check, and deduct. Returns False if not enough tokens."""
        if tokens <= 0:
            return True
        with self._lock:
            now = time.monotonic()
            current = self._refill(key, now)
            if current >= tokens:
                self._state[key]["tokens"] = current - tokens
                return True
            return False

    def get_remaining(self, key: str = _DEFAULT_KEY) -> int:
        """Snapshot remaining tokens under the lock so concurrent refill+deduct
        cannot tear the value.
        """
        if key not in self._state:
            return self.capacity
        with self._lock:
            now = time.monotonic()
            return int(self._refill(key, now))

    def reset(self, key: str = _DEFAULT_KEY) -> None:
        """Clear all state for ``key`` (no-op if unknown)."""
        with self._lock:
            self._state.pop(key, None)

    def __repr__(self) -> str:
        return f"TokenBucketLimiter(capacity={self.capacity}, refill_per_sec={self.refill_per_sec})"


class SlidingWindowLimiter(RateLimiter):
    """Sliding window: at most ``max_requests`` per ``window_sec`` per key.

    Stores monotonic timestamps in a deque; old ones are evicted lazily on access.
    """

    def __init__(self, max_requests: int, window_sec: float) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be > 0")
        if window_sec <= 0:
            raise ValueError("window_sec must be > 0")
        self.max_requests = max_requests
        self.window_sec = window_sec
        self._state: dict[str, deque[float]] = {}
        self._lock = threading.RLock()

    def _trim(self, key: str, now: float) -> deque[float]:
        dq = self._state.setdefault(key, deque())
        cutoff = now - self.window_sec
        while dq and dq[0] < cutoff:
            dq.popleft()
        return dq

    async def acquire(self, key: str = _DEFAULT_KEY, tokens: int = 1) -> bool:
        """Atomically trim, check, and record. Returns False if window is full."""
        if tokens <= 0:
            return True
        with self._lock:
            now = time.monotonic()
            dq = self._trim(key, now)
            if len(dq) + tokens <= self.max_requests:
                for _ in range(tokens):
                    dq.append(now)
                return True
            return False

    def get_remaining(self, key: str = _DEFAULT_KEY) -> int:
        """Snapshot remaining request slots under the lock so concurrent
        acquire+trim cannot tear the value.
        """
        if key not in self._state:
            return self.max_requests
        with self._lock:
            now = time.monotonic()
            dq = self._trim(key, now)
            return max(0, self.max_requests - len(dq))

    def reset(self, key: str = _DEFAULT_KEY) -> None:
        """Clear all state for ``key`` (no-op if unknown)."""
        with self._lock:
            self._state.pop(key, None)

    def __repr__(self) -> str:
        return f"SlidingWindowLimiter(max_requests={self.max_requests}, window_sec={self.window_sec})"


class MultiKeyLimiter(RateLimiter):
    """Routes per-key to a registered inner limiter.

    Example::

        limits = MultiKeyLimiter({
            "openai":  TokenBucketLimiter(capacity=60,  refill_per_sec=1.0),
            "twitter": TokenBucketLimiter(capacity=100, refill_per_sec=100.0),
        })
        if await limits.acquire("openai"):
            await call_openai()

    Unknown keys are allowed through with a warning log (configurable behavior — easy
    to flip to raise if you'd rather fail closed).
    """

    def __init__(self, limiters: dict[str, RateLimiter], *, allow_unknown: bool = True) -> None:
        self.limiters: dict[str, RateLimiter] = dict(limiters)
        self.allow_unknown = allow_unknown

    def register(self, key: str, limiter: RateLimiter) -> None:
        """Add or replace a per-key limiter at runtime."""
        self.limiters[key] = limiter

    def keys(self) -> list[str]:
        return list(self.limiters.keys())

    async def acquire(self, key: str = _DEFAULT_KEY, tokens: int = 1) -> bool:
        limiter = self.limiters.get(key)
        if limiter is None:
            if self.allow_unknown:
                log.warning(
                    "MultiKeyLimiter: no limiter registered for key %r — allowing", key
                )
                return True
            raise KeyError(f"MultiKeyLimiter: no limiter registered for key {key!r}")
        return await limiter.acquire(key=key, tokens=tokens)

    def get_remaining(self, key: str = _DEFAULT_KEY) -> int:
        limiter = self.limiters.get(key)
        if limiter is None:
            return -1
        return limiter.get_remaining(key)

    def reset(self, key: str = _DEFAULT_KEY) -> None:
        limiter = self.limiters.get(key)
        if limiter is None:
            return
        limiter.reset(key)

    def stats(self) -> dict[str, dict[str, Any]]:
        """Snapshot of per-key remaining capacity (useful for /metrics endpoints)."""
        return {key: {"remaining": lim.get_remaining(key)} for key, lim in self.limiters.items()}

    def __repr__(self) -> str:
        return f"MultiKeyLimiter(limiters={self.limiters!r})"
