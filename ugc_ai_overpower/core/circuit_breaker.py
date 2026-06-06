"""Circuit breaker pattern for resilient async/sync calls.

Provides automatic failure detection and recovery for external service calls.
State machine: CLOSED -> OPEN (on failures) -> HALF_OPEN (after timeout)
                                            -> CLOSED (after probe successes)
                                            -> OPEN (on probe failure)
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable

log = logging.getLogger(__name__)

__all__ = [
    "CircuitState",
    "CircuitBreakerOpen",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
]


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when circuit is open and call is rejected."""


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 30.0,
        success_threshold: int = 2,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout_sec
        self._success_threshold = success_threshold

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0

        self._opened_at_mono: float | None = None
        self._opened_at_wall: float | None = None
        self._last_failure_at_wall: float | None = None

        self._probe_in_flight = False
        # Per-instance lock guards every state read/write. A `threading.RLock`
        # is reentrant, works from both sync and async contexts, and is cheap
        # for the short critical sections here (no awaits held under the lock).
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return self._name

    def state(self) -> CircuitState:
        """Return the current state, snapshotting under the lock."""
        with self._lock:
            return self._state

    async def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute fn with circuit breaker protection."""
        with self._lock:
            self._total_calls += 1

            if self._state == CircuitState.OPEN:
                if (
                    self._opened_at_mono is not None
                    and (time.monotonic() - self._opened_at_mono) >= self._recovery_timeout
                ):
                    log.info("Circuit '%s' OPEN -> HALF_OPEN", self._name)
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    self._probe_in_flight = False
                else:
                    raise CircuitBreakerOpen(f"Circuit '{self._name}' is OPEN")

            if self._state == CircuitState.HALF_OPEN:
                if self._probe_in_flight:
                    raise CircuitBreakerOpen(
                        f"Circuit '{self._name}' HALF_OPEN probe in flight"
                    )
                self._probe_in_flight = True

        try:
            if inspect.iscoroutinefunction(fn):
                result = await fn(*args, **kwargs)
            else:
                result = await asyncio.to_thread(fn, *args, **kwargs)
        except Exception:
            with self._lock:
                self._record_failure()
            raise
        else:
            with self._lock:
                self._record_success()
            return result

    def _record_failure(self) -> None:
        self._total_failures += 1
        self._last_failure_at_wall = time.time()

        if self._state == CircuitState.HALF_OPEN:
            log.warning("Circuit '%s' HALF_OPEN probe failed -> OPEN", self._name)
            self._state = CircuitState.OPEN
            self._opened_at_mono = time.monotonic()
            self._opened_at_wall = time.time()
            self._failure_count = 0
            self._success_count = 0
            self._probe_in_flight = False
        elif self._state == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                log.warning(
                    "Circuit '%s' failure threshold %d reached -> OPEN",
                    self._name,
                    self._failure_threshold,
                )
                self._state = CircuitState.OPEN
                self._opened_at_mono = time.monotonic()
                self._opened_at_wall = time.time()

    def _record_success(self) -> None:
        self._total_successes += 1

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            self._probe_in_flight = False
            if self._success_count >= self._success_threshold:
                log.info("Circuit '%s' HALF_OPEN -> CLOSED", self._name)
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                self._opened_at_mono = None
                self._opened_at_wall = None
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def stats(self) -> dict:
        """Snapshot stats under the lock so concurrent writes don't tear."""
        with self._lock:
            return self._stats_unlocked()

    def stats_sync(self) -> dict:
        """Backward-compatible alias for :meth:`stats`."""
        return self.stats()

    def _stats_unlocked(self) -> dict:
        return {
            "name": self._name,
            "state": self._state.value,
            "total_calls": self._total_calls,
            "failures": self._total_failures,
            "successes": self._total_successes,
            "last_failure_at": (
                datetime.fromtimestamp(self._last_failure_at_wall).isoformat()
                if self._last_failure_at_wall is not None
                else None
            ),
            "opened_at": (
                datetime.fromtimestamp(self._opened_at_wall).isoformat()
                if self._opened_at_wall is not None
                else None
            ),
        }

    def reset(self) -> None:
        """Force back to CLOSED, clear all counters."""
        with self._lock:
            log.info("Circuit '%s' reset -> CLOSED", self._name)
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._opened_at_mono = None
            self._opened_at_wall = None
            self._last_failure_at_wall = None
            self._probe_in_flight = False


class CircuitBreakerRegistry:
    """Manage multiple breakers by name."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, name: str, **kwargs: Any) -> CircuitBreaker:
        """Get or create a breaker. kwargs passed to CircuitBreaker on first creation."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name=name, **kwargs)
        return self._breakers[name]

    def list_open(self) -> list[str]:
        """Return names of breakers currently in OPEN state."""
        return [n for n, b in self._breakers.items() if b.state() == CircuitState.OPEN]

    def force_close(self, name: str) -> bool:
        """Force a breaker to CLOSED state. Returns True if found."""
        if name not in self._breakers:
            return False
        self._breakers[name].reset()
        return True

    def all_stats(self) -> dict[str, dict]:
        """Return stats dict for every registered breaker."""
        return {n: b.stats_sync() for n, b in self._breakers.items()}
