"""Prometheus metrics for UGC AI Overpower.

Defines counters, histograms, and gauges for production monitoring.
Exposes a /metrics endpoint returning text in Prometheus exposition format.
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request
from fastapi.responses import Response

# ── HTTP metrics ───────────────────────────────────────────────────────────────

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float("inf")),
)

# ── Cache metrics ──────────────────────────────────────────────────────────────

cache_size = Gauge("cache_size", "Current cache size (number of entries)")
cache_hits_total = Counter("cache_hits_total", "Total cache hits")
cache_misses_total = Counter("cache_misses_total", "Total cache misses")

# ── Circuit breaker ────────────────────────────────────────────────────────────

active_circuits_open = Gauge("active_circuits_open", "Number of open circuit breakers")

# ── Rate limiter ───────────────────────────────────────────────────────────────

rate_limit_acquires = Counter("rate_limit_acquires", "Rate limiter acquire total")

# ── AI dispatch ────────────────────────────────────────────────────────────────

ai_dispatch_total = Counter(
    "ai_dispatch_total", "Total AI dispatch calls",
    ["provider", "status", "fallback_used"],
)

# ── Notion sync ────────────────────────────────────────────────────────────────

notion_sync_total = Counter(
    "notion_sync_total", "Total Notion sync operations",
    ["action", "status"],
)

# ── Scheduler ──────────────────────────────────────────────────────────────────

scheduler_active_jobs = Gauge("scheduler_active_jobs", "Number of active scheduler jobs")
scheduler_pending_jobs = Gauge("scheduler_pending_jobs", "Number of pending scheduler jobs")

# ── Webhooks ───────────────────────────────────────────────────────────────────

webhook_received_total = Counter(
    "webhook_received_total", "Total webhooks received",
    ["source"],
)


def register_metrics_route(app):
    """Register the /metrics endpoint on a FastAPI application."""
    from fastapi import Request
    from fastapi.responses import Response

    @app.get("/metrics")
    async def _metrics(request: Request):
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
