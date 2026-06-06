"""Async worker pool with priority queue, per-task callbacks, and graceful shutdown.

Provides a small async task pool (``AsyncPool``) that runs callables on a fixed
worker pool with priority-based scheduling, per-task timeouts, success/error
callbacks, cancellation, and statistics. Backs the swarm's batch processing of
async jobs (Notion sync, AI router calls, gallery indexing, etc.).
"""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

__all__ = ["PoolTask", "AsyncPool"]


@dataclass
class PoolTask:
    fn: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: int = 5  # 0=highest, 9=lowest
    timeout_sec: float = 60.0
    on_success: Optional[Callable] = None
    on_error: Optional[Callable] = None


class AsyncPool:
    def __init__(self, max_workers: int = 10, max_queue: int = 1000):
        self.max_workers = max_workers
        self.max_queue = max_queue
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue)
        self._tasks: dict[str, dict] = {}
        self._workers: list[asyncio.Task] = []
        self._workers_started = False
        self._seq = 0
        self._seq_lock = asyncio.Lock()
        # threading.RLock protects _tasks, _inflight, _drain_event, and the
        # cancel/stats/shutdown transitions from both sync and async callers
        # (workers, gather, drain, submit, cancel, stats). The critical
        # sections never await, so a sync lock is safe in async contexts.
        self._state_lock = threading.RLock()
        self._inflight = 0
        self._drain_event = asyncio.Event()
        self._drain_event.set()
        self._closed = False

    def _ensure_workers(self):
        if not self._workers_started and self.max_workers > 0:
            self._workers_started = True
            for i in range(self.max_workers):
                w = asyncio.create_task(self._worker(i))
                self._workers.append(w)

    async def _worker(self, idx: int):
        while True:
            try:
                priority, seq, tid, task = await self._queue.get()
            except asyncio.CancelledError:
                return
            with self._state_lock:
                self._inflight += 1
                self._drain_event.clear()
            state = self._tasks.get(tid)
            try:
                if state is None or state.get("cancelled"):
                    continue
                state["status"] = "running"
                try:
                    if asyncio.iscoroutinefunction(task.fn):
                        coro = task.fn(*task.args, **task.kwargs)
                        result = await asyncio.wait_for(coro, timeout=task.timeout_sec)
                    else:
                        result = task.fn(*task.args, **task.kwargs)
                        if asyncio.iscoroutine(result):
                            result = await asyncio.wait_for(result, timeout=task.timeout_sec)
                    state["result"] = result
                    state["status"] = "completed"
                    if task.on_success:
                        try:
                            task.on_success(result)
                        except Exception as cb_err:
                            log.warning("on_success callback error: %s", cb_err)
                except asyncio.TimeoutError as e:
                    state["error"] = e
                    state["status"] = "failed"
                    if task.on_error:
                        try:
                            task.on_error(e)
                        except Exception as cb_err:
                            log.warning("on_error callback error: %s", cb_err)
                except Exception as e:
                    state["error"] = e
                    state["status"] = "failed"
                    if task.on_error:
                        try:
                            task.on_error(e)
                        except Exception as cb_err:
                            log.warning("on_error callback error: %s", cb_err)
            finally:
                with self._state_lock:
                    self._inflight -= 1
                    self._queue.task_done()
                    if self._inflight == 0 and self._queue.empty():
                        self._drain_event.set()

    async def submit(self, task: PoolTask) -> str:
        self._ensure_workers()
        tid = uuid.uuid4().hex
        async with self._seq_lock:
            self._seq += 1
            seq = self._seq
        with self._state_lock:
            self._tasks[tid] = {
                "status": "pending",
                "result": None,
                "error": None,
                "task": task,
                "cancelled": False,
            }
            self._drain_event.clear()
        try:
            self._queue.put_nowait((task.priority, seq, tid, task))
        except asyncio.QueueFull:
            with self._state_lock:
                del self._tasks[tid]
            raise
        return tid

    async def map(self, fn: Callable, items: list, concurrency: int = 5) -> list[Any]:
        sem = asyncio.Semaphore(concurrency)
        results: list[Any] = [None] * len(items)

        async def run_one(i, item):
            async with sem:
                if asyncio.iscoroutinefunction(fn):
                    r = await fn(item)
                else:
                    r = fn(item)
                    if asyncio.iscoroutine(r):
                        r = await r
                results[i] = r

        await asyncio.gather(*[run_one(i, item) for i, item in enumerate(items)])
        return results

    async def gather_with_errors(self, tasks: list[PoolTask]) -> tuple[list[Any], list[Exception]]:
        tids = []
        for t in tasks:
            tid = await self.submit(t)
            tids.append(tid)
        await self.drain()
        results = []
        errors = []
        with self._state_lock:
            for tid in tids:
                state = self._tasks.get(tid, {"status": "missing", "result": None, "error": None})
                if state["status"] == "completed":
                    results.append(state["result"])
                elif state["status"] == "failed" and state["error"] is not None:
                    errors.append(state["error"])
                else:
                    errors.append(RuntimeError(f"task {tid} ended in status {state['status']}"))
        return results, errors

    def cancel(self, task_id: str) -> bool:
        """Mark a pending task as cancelled. Returns True if a pending task was found."""
        with self._state_lock:
            state = self._tasks.get(task_id)
            if state is None:
                return False
            if state["status"] != "pending":
                return False
            state["cancelled"] = True
            state["status"] = "cancelled"
            return True

    def stats(self) -> dict:
        """Snapshot counters under the lock so concurrent state writes don't tear."""
        pending = running = completed = failed = 0
        with self._state_lock:
            for s in self._tasks.values():
                st = s["status"]
                if st == "pending":
                    pending += 1
                elif st == "running":
                    running += 1
                elif st == "completed":
                    completed += 1
                elif st == "failed":
                    failed += 1
            total = len(self._tasks)
        return {
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "total": total,
        }

    async def drain(self, timeout_sec: float = 30.0) -> None:
        try:
            await asyncio.wait_for(self._drain_event.wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            pass

    async def shutdown(self) -> None:
        with self._state_lock:
            for state in self._tasks.values():
                if state["status"] == "pending":
                    state["cancelled"] = True
                    state["status"] = "cancelled"
        try:
            await asyncio.wait_for(self._drain_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._closed = True
