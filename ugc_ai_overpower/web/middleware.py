"""Request tracing middleware for FastAPI.

Adds ``X-Request-ID``, ``X-Response-Time`` headers, logs request start/finish
with timing, and flags slow (>1 s) / failed (5xx) requests.
"""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from ugc_ai_overpower.core.logging_config import request_id_var
from ugc_ai_overpower.web.metrics import (
    http_requests_total,
    http_request_duration_seconds,
)

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that adds tracing headers and logs every request.

    * Reads / generates ``X-Request-ID``.
    * Sets ``X-Response-Time`` (ms).
    * Logs request start, finish, slow (>1 s) warnings, and 5xx errors.
    * Updates Prometheus ``http_requests_total`` and
      ``http_request_duration_seconds`` metrics.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # ── Request phase ────────────────────────────────────────────
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(req_id)
        start = time.monotonic()
        method = request.method
        path = request.url.path

        logger.info("Request started", extra={"method": method, "path": path})

        # ── Dispatch ─────────────────────────────────────────────────
        try:
            response = await call_next(request)
        except Exception:
            duration = time.monotonic() - start
            logger.exception("Request failed after %.4fs", duration)
            http_request_duration_seconds.labels(method=method, path=path).observe(duration)
            http_requests_total.labels(method=method, path=path, status="500").inc()
            raise

        # ── Response phase ───────────────────────────────────────────
        duration = time.monotonic() - start
        status = response.status_code

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time"] = f"{duration * 1000:.2f}"

        # Update Prometheus metrics
        http_requests_total.labels(method=method, path=path, status=str(status)).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)

        # Slow request warning
        if duration > 1.0:
            logger.warning(
                "Slow request: %s %s → %s in %.4fs",
                method, path, status, duration,
            )

        # Failed request error
        if status >= 500:
            logger.error(
                "Request failed: %s %s → %s in %.4fs",
                method, path, status, duration,
            )

        logger.info("Request finished: %s %s → %s in %.4fs", method, path, status, duration)

        return response
