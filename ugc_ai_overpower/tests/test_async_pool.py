"""Tests for core/async_pool.py."""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.core.async_pool import PoolTask, AsyncPool  # noqa: E402

pytestmark = pytest.mark.asyncio


# ─── 1. submit returns string id ───────────────────────────────────


async def test_submit_returns_string_id():
    pool = AsyncPool(max_workers=1)
    try:
        tid = await pool.submit(PoolTask(fn=lambda: 42))
        assert isinstance(tid, str)
        assert len(tid) > 0
    finally:
        await pool.shutdown()


# ─── 2. submit + drain captures result ─────────────────────────────


async def test_submit_then_drain_captures_result():
    pool = AsyncPool(max_workers=2)
    try:
        tid = await pool.submit(PoolTask(fn=lambda: 42))
        await pool.drain(timeout_sec=2.0)
        state = pool._tasks[tid]
        assert state["status"] == "completed"
        assert state["result"] == 42
    finally:
        await pool.shutdown()


# ─── 3. priority order (single worker) ─────────────────────────────


async def test_priority_order():
    order: list[str] = []

    def make_fn(label: str):
        def _fn():
            order.append(label)
            return label
        return _fn

    pool = AsyncPool(max_workers=1)
    try:
        await pool.submit(PoolTask(fn=make_fn("p9"), priority=9))
        await pool.submit(PoolTask(fn=make_fn("p0"), priority=0))
        await pool.submit(PoolTask(fn=make_fn("p5"), priority=5))
        await pool.drain(timeout_sec=2.0)
        assert order == ["p0", "p5", "p9"]
    finally:
        await pool.shutdown()


# ─── 4. map preserves order ────────────────────────────────────────


async def test_map_preserves_order():
    pool = AsyncPool()
    try:
        items = list(range(10))
        results = await pool.map(lambda x: x * 2, items, concurrency=4)
        assert results == [x * 2 for x in items]
    finally:
        await pool.shutdown()


# ─── 5. map concurrency bound ──────────────────────────────────────


async def test_map_concurrency_bound():
    pool = AsyncPool()

    async def slow(_):
        await asyncio.sleep(0.1)
        return 1

    try:
        start = time.monotonic()
        results = await pool.map(slow, list(range(10)), concurrency=3)
        elapsed = time.monotonic() - start
        assert sum(results) == 10
        # 10 items / 3 concurrency * 0.1s ≈ 0.4s; allow 0.25 < t < 0.7
        assert elapsed > 0.25, f"too fast: {elapsed}"
        assert elapsed < 0.7, f"too slow: {elapsed}"
    finally:
        await pool.shutdown()


# ─── 6. gather_with_errors mixed ──────────────────────────────────


async def test_gather_with_errors_mixed():
    pool = AsyncPool(max_workers=2)
    try:
        tasks = [
            PoolTask(fn=lambda: 42),
            PoolTask(fn=lambda: (_ for _ in ()).throw(RuntimeError("boom"))),
            PoolTask(fn=lambda: 42),
        ]
        results, errors = await pool.gather_with_errors(tasks)
        assert results == [42, 42]
        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)
    finally:
        await pool.shutdown()


# ─── 7. gather_with_errors never raises ────────────────────────────


async def test_gather_with_errors_never_raises():
    pool = AsyncPool(max_workers=1)
    try:
        tasks = [PoolTask(fn=lambda: (_ for _ in ()).throw(ValueError("x")))]
        results, errors = await pool.gather_with_errors(tasks)
        assert results == []
        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)
    finally:
        await pool.shutdown()


# ─── 8. on_success callback ────────────────────────────────────────


async def test_on_success_callback():
    pool = AsyncPool(max_workers=1)
    captured: list = []
    try:
        await pool.submit(PoolTask(fn=lambda: 7, on_success=captured.append))
        await pool.drain(timeout_sec=2.0)
        assert captured == [7]
    finally:
        await pool.shutdown()


# ─── 9. on_error callback ──────────────────────────────────────────


async def test_on_error_callback():
    pool = AsyncPool(max_workers=1)
    captured: list = []
    try:
        def bad():
            raise ValueError("nope")

        await pool.submit(PoolTask(fn=bad, on_error=captured.append))
        await pool.drain(timeout_sec=2.0)
        assert len(captured) == 1
        assert isinstance(captured[0], ValueError)
    finally:
        await pool.shutdown()


# ─── 10. cancel pending ────────────────────────────────────────────


async def test_cancel_pending():
    pool = AsyncPool(max_workers=0)
    try:
        tid = await pool.submit(PoolTask(fn=lambda: 1))
        ok = pool.cancel(tid)
        assert ok is True
        assert pool._tasks[tid]["status"] == "cancelled"
    finally:
        await pool.shutdown()


# ─── 11. cancel running returns False ──────────────────────────────


async def test_cancel_running():
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocker():
        started.set()
        await release.wait()
        return 1

    pool = AsyncPool(max_workers=1)
    try:
        tid = await pool.submit(PoolTask(fn=blocker))
        await started.wait()
        ok = pool.cancel(tid)
        assert ok is False
        release.set()
        await pool.drain(timeout_sec=2.0)
    finally:
        await pool.shutdown()


# ─── 12. cancel unknown returns False ──────────────────────────────


async def test_cancel_unknown():
    pool = AsyncPool()
    try:
        assert pool.cancel("nonexistent-id") is False
    finally:
        await pool.shutdown()


# ─── 13. stats counts ──────────────────────────────────────────────


async def test_stats():
    pool = AsyncPool(max_workers=0)
    try:
        for _ in range(3):
            await pool.submit(PoolTask(fn=lambda: 1))
        s = pool.stats()
        assert s["pending"] == 3
        assert s["running"] == 0
        assert s["completed"] == 0
        assert s["failed"] == 0
        assert s["total"] == 3
    finally:
        await pool.shutdown()


# ─── 14. drain blocks until done ───────────────────────────────────


async def test_drain_blocks_until_done():
    pool = AsyncPool(max_workers=3)

    async def slow(_):
        await asyncio.sleep(0.1)
        return _

    try:
        start = time.monotonic()
        tasks = [PoolTask(fn=slow, args=(i,)) for i in range(5)]
        for t in tasks:
            await pool.submit(t)
        await pool.drain(timeout_sec=5.0)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.1
    finally:
        await pool.shutdown()


# ─── 15. shutdown cancels pending ──────────────────────────────────


async def test_shutdown_cancels_pending():
    pool = AsyncPool(max_workers=0)
    try:
        for _ in range(3):
            await pool.submit(PoolTask(fn=lambda: 1))
        await pool.shutdown()
        cancelled = sum(1 for s in pool._tasks.values() if s["status"] == "cancelled")
        assert cancelled == 3
    finally:
        pass


# ─── 16. timeout raises TimeoutError ───────────────────────────────


async def test_timeout():
    pool = AsyncPool(max_workers=1)
    try:
        tid = await pool.submit(
            PoolTask(fn=lambda: asyncio.sleep(5.0), timeout_sec=0.1)
        )
        await pool.drain(timeout_sec=2.0)
        state = pool._tasks[tid]
        assert state["status"] == "failed"
        assert isinstance(state["error"], asyncio.TimeoutError)
    finally:
        await pool.shutdown()


# ─── 17. queue full ────────────────────────────────────────────────


async def test_queue_full():
    pool = AsyncPool(max_workers=0, max_queue=1000)
    try:
        for _ in range(1000):
            await pool.submit(PoolTask(fn=lambda: 1))
        with pytest.raises(asyncio.QueueFull):
            await pool.submit(PoolTask(fn=lambda: 1))
    finally:
        await pool.shutdown()


# ─── 18. concurrent workers ────────────────────────────────────────


async def test_concurrent_workers():
    pool = AsyncPool(max_workers=5)

    async def work(_):
        await asyncio.sleep(0.01)
        return _

    try:
        tids = []
        for i in range(20):
            tids.append(await pool.submit(PoolTask(fn=work, args=(i,))))
        await pool.drain(timeout_sec=5.0)
        for tid in tids:
            assert pool._tasks[tid]["status"] == "completed"
    finally:
        await pool.shutdown()


# ─── 19. empty pool drain returns instantly ─────────────────────────


async def test_empty_pool_drain():
    pool = AsyncPool()
    try:
        start = time.monotonic()
        await pool.drain(timeout_sec=1.0)
        elapsed = time.monotonic() - start
        assert elapsed < 0.2
    finally:
        await pool.shutdown()


# ─── 20. async fn support ──────────────────────────────────────────


async def test_async_fn_support():
    pool = AsyncPool(max_workers=1)
    try:

        async def afn():
            await asyncio.sleep(0.01)
            return "async_ok"

        tid = await pool.submit(PoolTask(fn=afn))
        await pool.drain(timeout_sec=2.0)
        assert pool._tasks[tid]["result"] == "async_ok"
    finally:
        await pool.shutdown()


# ─── 21. kwargs passthrough ────────────────────────────────────────


async def test_kwargs_passthrough():
    pool = AsyncPool(max_workers=1)
    try:

        def fn(a, b=0, c=0):
            return a + b + c

        tid = await pool.submit(PoolTask(fn=fn, args=(1,), kwargs={"b": 2, "c": 3}))
        await pool.drain(timeout_sec=2.0)
        assert pool._tasks[tid]["result"] == 6
    finally:
        await pool.shutdown()


# ─── 22. on_error preserves traceback ──────────────────────────────


async def test_on_error_preserves_traceback():
    pool = AsyncPool(max_workers=1)
    try:

        def bad():
            raise ValueError("trace me")

        tid = await pool.submit(PoolTask(fn=bad))
        await pool.drain(timeout_sec=2.0)
        err = pool._tasks[tid]["error"]
        assert isinstance(err, ValueError)
        assert err.__traceback__ is not None
    finally:
        await pool.shutdown()


# ─── 23. map with async fn ─────────────────────────────────────────


async def test_map_with_async_fn():
    pool = AsyncPool()

    async def doubler(x):
        await asyncio.sleep(0.001)
        return x * 2

    try:
        items = [1, 2, 3, 4, 5]
        results = await pool.map(doubler, items, concurrency=3)
        assert results == [2, 4, 6, 8, 10]
    finally:
        await pool.shutdown()


# ─── 24. drain with timeout returns promptly ───────────────────────


async def test_drain_with_timeout():
    started = asyncio.Event()
    release = asyncio.Event()
    pool = AsyncPool(max_workers=1)

    async def blocker():
        started.set()
        await release.wait()
        return 1

    try:
        await pool.submit(PoolTask(fn=blocker))
        await started.wait()
        start = time.monotonic()
        await pool.drain(timeout_sec=0.1)
        elapsed = time.monotonic() - start
        assert elapsed < 0.3
        release.set()
    finally:
        await pool.shutdown()


# ─── 25. stats total counter ───────────────────────────────────────


async def test_stats_total_counter():
    pool = AsyncPool(max_workers=2)
    try:
        for i in range(7):
            await pool.submit(PoolTask(fn=lambda: 1))
        await pool.drain(timeout_sec=2.0)
        s = pool.stats()
        assert s["total"] == 7
        assert s["total"] == len(pool._tasks)
    finally:
        await pool.shutdown()
