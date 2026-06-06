#!/usr/bin/env python3
"""Load test for the BATCH B resilience stack.

Spawns N concurrent "campaign" workers via AsyncPool. Each worker:
  1. Tries a cache get on a hot key.
  2. Calls a fake API through a rate-limited circuit-breaker.
  3. Reports its latency to the central collector.

Measures total wall time, aggregate throughput, p50/p95/p99 latency, and
error rate. Exits 0 on success.

Usage:
    python scripts/load_test.py --workers 100 --duration 60
    python scripts/load_test.py --workers 50 --duration 10 --no-fail
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.core.async_pool import AsyncPool, PoolTask
from ugc_ai_overpower.core.cache import MemoryCache
from ugc_ai_overpower.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from ugc_ai_overpower.core.performance import RateLimitedCachedBreaker
from ugc_ai_overpower.core.rate_limiter import TokenBucketLimiter


# ============================================================== worker


class LoadTest:
    def __init__(self, workers: int, duration: int, fail_inject: float,
                 cache_hit_ratio: float, rate_capacity: int) -> None:
        self.workers = workers
        self.duration = float(duration)
        self.fail_inject = fail_inject
        self.cache_hit_ratio = cache_hit_ratio
        self.rate_capacity = rate_capacity
        self._stop = asyncio.Event()
        self._latencies: list[float] = []
        self._lat_lock = asyncio.Lock()
        self._ok = 0
        self._err = 0
        self._rate_limited = 0
        self._breaker_open = 0
        self._cache_hits = 0
        self._cache_misses = 0

        # Shared infra — same instance across all workers, like a real
        # production deployment behind a single FastAPI process.
        self.cache = MemoryCache(max_size=10_000, default_ttl=300)
        self.rate_limiter = TokenBucketLimiter(
            capacity=rate_capacity, refill_per_sec=rate_capacity
        )
        self.breaker = CircuitBreaker(
            name="load_test", failure_threshold=50, recovery_timeout_sec=5.0
        )
        self.guard = RateLimitedCachedBreaker(
            name="load_test",
            rate_limiter=self.rate_limiter,
            cache=self.cache,
            breaker=self.breaker,
            acquire_timeout_sec=2.0,
        )

    async def campaign(self, worker_id: int) -> None:
        """One iteration of a campaign worker."""
        # Half the calls hit a small hot set → real cache hits.
        if random.random() < self.cache_hit_ratio:
            key = f"hot:{random.randint(0, 19)}"
        else:
            key = f"cold:{worker_id}:{random.randint(0, 1_000_000)}"

        async def fake_api(k: str) -> dict:
            # Tiny work + a chance of injected failure
            await asyncio.sleep(0.001)
            if random.random() < self.fail_inject:
                raise RuntimeError("injected failure")
            return {"key": k, "ts": time.time()}

        t0 = time.perf_counter()
        try:
            res = await self.guard.execute(fake_api, key, cache_key=key)
            elapsed = (time.perf_counter() - t0) * 1000
            async with self._lat_lock:
                self._latencies.append(elapsed)
                self._ok += 1
            assert res["key"] == key
        except CircuitBreakerOpen:
            self._breaker_open += 1
        except Exception as exc:
            err_name = type(exc).__name__
            if "rate" in err_name.lower():
                self._rate_limited += 1
            else:
                self._err += 1

    async def worker_loop(self, wid: int) -> None:
        """One worker: keep calling campaign() until duration elapses."""
        end = time.perf_counter() + self.duration
        # Stagger start slightly to avoid synchronous bursts
        await asyncio.sleep(random.uniform(0, 0.05))
        while time.perf_counter() < end and not self._stop.is_set():
            await self.campaign(wid)
            # Small yield
            await asyncio.sleep(0)

    async def run(self) -> dict:
        """Spawn N workers for the configured duration and return stats."""
        print(f"Load test: workers={self.workers} duration={self.duration}s "
              f"fail_inject={self.fail_inject} cache_hit_ratio={self.cache_hit_ratio} "
              f"rate_capacity={self.rate_capacity}")
        t0 = time.perf_counter()
        workers = [asyncio.create_task(self.worker_loop(i))
                   for i in range(self.workers)]
        # Periodic progress line
        try:
            while time.perf_counter() - t0 < self.duration:
                await asyncio.sleep(1.0)
                elapsed = time.perf_counter() - t0
                print(f"  ... {elapsed:.1f}s elapsed, "
                      f"ok={self._ok} err={self._err} "
                      f"rate_limited={self._rate_limited} "
                      f"breaker_open={self._breaker_open}")
        finally:
            self._stop.set()
            await asyncio.gather(*workers, return_exceptions=True)
        total = time.perf_counter() - t0

        return await self._summarise(total)

    def _percentile(self, sorted_vals: list[float], pct: float) -> float:
        if not sorted_vals:
            return 0.0
        k = int(round((pct / 100.0) * (len(sorted_vals) - 1)))
        return sorted_vals[max(0, min(k, len(sorted_vals) - 1))]

    async def _summarise(self, total_sec: float) -> dict:
        async with self._lat_lock:
            sorted_lat = sorted(self._latencies)
        ok = self._ok
        err = self._err
        rl = self._rate_limited
        bo = self._breaker_open
        attempts = ok + err + rl + bo
        return {
            "total_sec": total_sec,
            "attempts": attempts,
            "ok": ok,
            "err": err,
            "rate_limited": rl,
            "breaker_open": bo,
            "error_rate": (err + rl + bo) / max(attempts, 1),
            "throughput_rps": attempts / total_sec if total_sec > 0 else 0,
            "p50_ms": self._percentile(sorted_lat, 50),
            "p95_ms": self._percentile(sorted_lat, 95),
            "p99_ms": self._percentile(sorted_lat, 99),
            "max_ms": sorted_lat[-1] if sorted_lat else 0,
            "guard_stats": self.guard.stats(),
        }


# ============================================================== cli


def render_report(stats: dict) -> str:
    lines: list[str] = []
    lines.append("\n========== LOAD TEST REPORT ==========")
    lines.append(f"Total wall time       : {stats['total_sec']:.2f}s")
    lines.append(f"Total attempts        : {stats['attempts']:,}")
    lines.append(f"  Successful (ok)     : {stats['ok']:,}")
    lines.append(f"  Errors              : {stats['err']:,}")
    lines.append(f"  Rate-limited        : {stats['rate_limited']:,}")
    lines.append(f"  Breaker-rejected    : {stats['breaker_open']:,}")
    lines.append(f"Error rate            : {stats['error_rate']*100:.2f}%")
    lines.append(f"Throughput            : {stats['throughput_rps']:.0f} req/s")
    lines.append(f"Latency p50           : {stats['p50_ms']:.2f}ms")
    lines.append(f"Latency p95           : {stats['p95_ms']:.2f}ms")
    lines.append(f"Latency p99           : {stats['p99_ms']:.2f}ms")
    lines.append(f"Latency max           : {stats['max_ms']:.2f}ms")
    gs = stats.get("guard_stats", {})
    if gs:
        lines.append("--- RateLimitedCachedBreaker counters ---")
        lines.append(f"  cache_hits          : {gs.get('cache_hits', 0):,}")
        lines.append(f"  cache_misses        : {gs.get('cache_misses', 0):,}")
        lines.append(f"  executed            : {gs.get('executed', 0):,}")
        lines.append(f"  rate_limited        : {gs.get('rate_limited', 0):,}")
        lines.append(f"  breaker_rejected    : {gs.get('breaker_rejected', 0):,}")
        lines.append(f"  breaker_state       : {gs.get('breaker_state', '?')}")
    lines.append("======================================\n")
    return "\n".join(lines)


async def amain() -> int:
    parser = argparse.ArgumentParser(description="Load test the BATCH B resilience stack")
    parser.add_argument("--workers", type=int, default=100,
                        help="Number of concurrent workers (default 100)")
    parser.add_argument("--duration", type=int, default=60,
                        help="Duration in seconds (default 60)")
    parser.add_argument("--fail-inject", type=float, default=0.0,
                        help="Fraction of calls that fail (0.0–1.0, default 0)")
    parser.add_argument("--cache-hit-ratio", type=float, default=0.7,
                        help="Fraction of calls that hit a hot key (0.0–1.0)")
    parser.add_argument("--rate-capacity", type=int, default=10_000,
                        help="Token-bucket capacity (also refill rate)")
    parser.add_argument("--no-fail", action="store_true",
                        help="Don't fail the script on high error rate")
    args = parser.parse_args()

    if args.fail_inject < 0 or args.fail_inject > 1:
        print("error: --fail-inject must be between 0 and 1", file=sys.stderr)
        return 2
    if args.workers < 1 or args.duration < 1:
        print("error: --workers and --duration must be positive", file=sys.stderr)
        return 2

    test = LoadTest(
        workers=args.workers,
        duration=args.duration,
        fail_inject=args.fail_inject,
        cache_hit_ratio=args.cache_hit_ratio,
        rate_capacity=args.rate_capacity,
    )
    stats = await test.run()
    print(render_report(stats))

    if not args.no_fail and stats["error_rate"] > 0.05:
        print(f"FAIL: error rate {stats['error_rate']*100:.1f}% > 5%")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(amain()))
