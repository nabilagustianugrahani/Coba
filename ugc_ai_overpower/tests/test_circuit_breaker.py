"""Tests for core/circuit_breaker.py — CircuitBreaker, CircuitBreakerRegistry."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.circuit_breaker import (  # noqa: E402
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    CircuitState,
)


async def _ok_async():
    return "ok"


async def _fail_async():
    raise RuntimeError("boom")


def _ok_sync():
    return "sync_ok"


# ─── CircuitBreaker tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_starts_closed():
    cb = CircuitBreaker("svc")
    assert cb.state() == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_successful_call_returns_result():
    cb = CircuitBreaker("svc")
    result = await cb.call(_ok_async)
    assert result == "ok"
    assert cb.state() == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_failure_raises_original_exception():
    cb = CircuitBreaker("svc", failure_threshold=5)
    with pytest.raises(RuntimeError, match="boom"):
        await cb.call(_fail_async)
    assert cb.stats()["failures"] == 1
    assert cb.state() == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_opens_after_failure_threshold():
    cb = CircuitBreaker("svc", failure_threshold=3)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.call(_fail_async)
    assert cb.state() == CircuitState.OPEN


@pytest.mark.asyncio
async def test_open_state_rejects_calls():
    cb = CircuitBreaker("svc", failure_threshold=2)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(_fail_async)
    assert cb.state() == CircuitState.OPEN
    with pytest.raises(CircuitBreakerOpen):
        await cb.call(_ok_async)


@pytest.mark.asyncio
async def test_transitions_to_half_open_after_timeout():
    cb = CircuitBreaker(
        "svc", failure_threshold=2, recovery_timeout_sec=0.05, success_threshold=3
    )
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(_fail_async)
    assert cb.state() == CircuitState.OPEN
    await asyncio.sleep(0.08)
    result = await cb.call(_ok_async)
    assert result == "ok"
    assert cb.state() == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_success_increments_counter():
    cb = CircuitBreaker(
        "svc", failure_threshold=2, recovery_timeout_sec=0.05, success_threshold=3
    )
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(_fail_async)
    await asyncio.sleep(0.08)
    await cb.call(_ok_async)
    assert cb._success_count == 1
    await cb.call(_ok_async)
    assert cb._success_count == 2
    assert cb.state() == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_threshold_closes_circuit():
    cb = CircuitBreaker(
        "svc", failure_threshold=2, recovery_timeout_sec=0.05, success_threshold=2
    )
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(_fail_async)
    await asyncio.sleep(0.08)
    await cb.call(_ok_async)
    await cb.call(_ok_async)
    assert cb.state() == CircuitState.CLOSED
    assert cb.stats()["opened_at"] is None


@pytest.mark.asyncio
async def test_half_open_failure_reopens_circuit():
    cb = CircuitBreaker("svc", failure_threshold=2, recovery_timeout_sec=0.05)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(_fail_async)
    first_opened_at = cb.stats()["opened_at"]
    assert first_opened_at is not None
    await asyncio.sleep(0.08)
    with pytest.raises(RuntimeError):
        await cb.call(_fail_async)
    assert cb.state() == CircuitState.OPEN
    second_opened_at = cb.stats()["opened_at"]
    assert second_opened_at is not None
    assert second_opened_at != first_opened_at


@pytest.mark.asyncio
async def test_stats_has_expected_keys_and_values():
    cb = CircuitBreaker("svc")
    stats = cb.stats()
    assert set(stats.keys()) == {
        "name",
        "state",
        "total_calls",
        "failures",
        "successes",
        "last_failure_at",
        "opened_at",
    }
    assert stats["name"] == "svc"
    assert stats["state"] == "closed"
    assert stats["total_calls"] == 0
    assert stats["failures"] == 0
    assert stats["successes"] == 0
    assert stats["last_failure_at"] is None
    assert stats["opened_at"] is None


@pytest.mark.asyncio
async def test_stats_last_failure_at_is_iso_string():
    cb = CircuitBreaker("svc", failure_threshold=5)
    with pytest.raises(RuntimeError):
        await cb.call(_fail_async)
    last_failure = cb.stats()["last_failure_at"]
    assert isinstance(last_failure, str)
    parsed = datetime.fromisoformat(last_failure)
    assert isinstance(parsed, datetime)


@pytest.mark.asyncio
async def test_reset_forces_closed_and_clears_counters():
    cb = CircuitBreaker("svc", failure_threshold=2)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(_fail_async)
    assert cb.state() == CircuitState.OPEN
    cb.reset()
    assert cb.state() == CircuitState.CLOSED
    assert cb._failure_count == 0
    assert cb._success_count == 0
    assert cb.stats()["opened_at"] is None
    result = await cb.call(_ok_async)
    assert result == "ok"


@pytest.mark.asyncio
async def test_call_with_async_fn():
    cb = CircuitBreaker("svc")
    result = await cb.call(_ok_async)
    assert result == "ok"


@pytest.mark.asyncio
async def test_call_with_sync_fn_runs_in_thread():
    cb = CircuitBreaker("svc")
    result = await cb.call(_ok_sync)
    assert result == "sync_ok"


@pytest.mark.asyncio
async def test_call_with_args_and_kwargs():
    cb = CircuitBreaker("svc")

    async def afn(a, b, c=0, d=0):
        return a + b + c + d

    result = await cb.call(afn, 1, 2, c=3, d=4)
    assert result == 10


@pytest.mark.asyncio
async def test_call_preserves_return_value():
    cb = CircuitBreaker("svc")

    async def afn():
        return {"key": "value", "items": [1, 2, 3]}

    result = await cb.call(afn)
    assert result == {"key": "value", "items": [1, 2, 3]}


# ─── CircuitBreakerRegistry tests ──────────────────────────────────


def test_registry_get_creates_new_breaker():
    reg = CircuitBreakerRegistry()
    cb = reg.get("svc1", failure_threshold=7)
    assert isinstance(cb, CircuitBreaker)
    assert cb.name == "svc1"
    assert cb._failure_threshold == 7


def test_registry_get_returns_same_instance():
    reg = CircuitBreakerRegistry()
    cb1 = reg.get("svc1", failure_threshold=10)
    cb2 = reg.get("svc1")
    assert cb1 is cb2


@pytest.mark.asyncio
async def test_registry_list_open_returns_open_names():
    reg = CircuitBreakerRegistry()
    cb1 = reg.get("svc1", failure_threshold=2)
    reg.get("svc2", failure_threshold=2)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb1.call(_fail_async)
    open_list = reg.list_open()
    assert "svc1" in open_list
    assert "svc2" not in open_list


@pytest.mark.asyncio
async def test_registry_force_close_returns_true_and_resets():
    reg = CircuitBreakerRegistry()
    cb = reg.get("svc1", failure_threshold=2)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(_fail_async)
    assert cb.state() == CircuitState.OPEN
    result = reg.force_close("svc1")
    assert result is True
    assert cb.state() == CircuitState.CLOSED


def test_registry_force_close_unknown_returns_false():
    reg = CircuitBreakerRegistry()
    assert reg.force_close("nonexistent") is False


def test_registry_all_stats_returns_dict_for_all_breakers():
    reg = CircuitBreakerRegistry()
    reg.get("svc1")
    reg.get("svc2")
    all_stats = reg.all_stats()
    assert set(all_stats.keys()) == {"svc1", "svc2"}
    assert all_stats["svc1"]["name"] == "svc1"
    assert all_stats["svc2"]["name"] == "svc2"
    assert all_stats["svc1"]["state"] == "closed"
