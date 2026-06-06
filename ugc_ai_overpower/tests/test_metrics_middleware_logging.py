"""
Batch N — Production Hardening: Prometheus metrics, request tracing, structured logging.
15 tests: 5 metrics, 5 middleware, 5 logging config.
"""
from __future__ import annotations

import io
import json
import logging
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ═══════════════════════════════════════════════════════════════════════════════
#  5 METRICS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetricsEndpoint:
    """Verify Prometheus /metrics endpoint behaves correctly."""

    @pytest.fixture
    def metrics_app(self):
        """Minimal FastAPI app with /metrics registered and no auth."""
        from fastapi import FastAPI
        from ugc_ai_overpower.web.metrics import register_metrics_route

        app = FastAPI()
        register_metrics_route(app)
        return app

    def test_metrics_returns_200(self, metrics_app):
        """The /metrics endpoint must return HTTP 200."""
        from starlette.testclient import TestClient
        with TestClient(metrics_app) as client:
            r = client.get("/metrics")
        assert r.status_code == 200

    def test_metrics_content_type(self, metrics_app):
        """Content-Type must be the standard Prometheus text format."""
        from starlette.testclient import TestClient
        with TestClient(metrics_app) as client:
            r = client.get("/metrics")
        ct = r.headers.get("content-type", "")
        assert "text/plain" in ct

    def test_metrics_reflects_counter_increment(self, metrics_app):
        """Incrementing http_requests_total must show in /metrics output."""
        from starlette.testclient import TestClient
        from ugc_ai_overpower.web.metrics import http_requests_total

        http_requests_total.labels(method="GET", path="/test", status="200").inc()
        http_requests_total.labels(method="GET", path="/test", status="200").inc()

        with TestClient(metrics_app) as client:
            body = client.get("/metrics").text

        assert 'http_requests_total{method="GET",path="/test",status="200"} 2.0' in body

    def test_metrics_gauge_updates(self, metrics_app):
        """Setting a gauge value must be reflected in /metrics output."""
        from starlette.testclient import TestClient
        from ugc_ai_overpower.web.metrics import cache_size, active_circuits_open

        cache_size.set(42)
        active_circuits_open.set(3)

        with TestClient(metrics_app) as client:
            body = client.get("/metrics").text

        assert "cache_size 42.0" in body
        assert "active_circuits_open 3.0" in body

    def test_metrics_histogram_observation(self, metrics_app):
        """Observing a histogram must update count/sum in /metrics output."""
        from starlette.testclient import TestClient
        from ugc_ai_overpower.web.metrics import http_request_duration_seconds

        http_request_duration_seconds.labels(method="POST", path="/submit").observe(0.25)

        with TestClient(metrics_app) as client:
            body = client.get("/metrics").text

        # Histogram output includes _count and _sum
        assert 'http_request_duration_seconds_count{method="POST",path="/submit"}' in body
        assert 'http_request_duration_seconds_sum{method="POST",path="/submit"}' in body


# ═══════════════════════════════════════════════════════════════════════════════
#  5 MIDDLEWARE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTracingMiddleware:
    """Verify TracingMiddleware adds headers and logs correctly."""

    @pytest.fixture
    def trace_app(self):
        """Minimal FastAPI app with TracingMiddleware and a test route."""
        from fastapi import FastAPI
        from ugc_ai_overpower.web.middleware import TracingMiddleware
        import asyncio

        app = FastAPI()
        app.add_middleware(TracingMiddleware)

        @app.get("/hello")
        async def hello():
            return {"message": "ok"}

        @app.get("/slow")
        async def slow():
            import asyncio
            await asyncio.sleep(1.2)
            return {"message": "slow"}

        @app.get("/error")
        async def error():
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="server error")

        return app

    def test_request_id_added(self, trace_app):
        """Every response must have an X-Request-ID header."""
        from starlette.testclient import TestClient
        with TestClient(trace_app) as client:
            r = client.get("/hello")
        assert "X-Request-ID" in r.headers
        assert len(r.headers["X-Request-ID"]) > 0

    def test_response_time_header(self, trace_app):
        """Every response must have an X-Response-Time header (ms)."""
        from starlette.testclient import TestClient
        with TestClient(trace_app) as client:
            r = client.get("/hello")
        assert "X-Response-Time" in r.headers
        val = float(r.headers["X-Response-Time"])
        assert val > 0

    def test_slow_request_logged(self, trace_app):
        """Requests taking >1 s must log a warning."""
        from starlette.testclient import TestClient
        logger = logging.getLogger("ugc_ai_overpower.web.middleware")
        logger.setLevel(logging.WARNING)

        with patch.object(logger, "warning") as mock_warning:
            with TestClient(trace_app) as client:
                r = client.get("/slow")
            assert r.status_code == 200
            # Should have logged at least one warning (slow request)
            slow_calls = [c for c in mock_warning.call_args_list if "Slow request" in str(c)]
            assert len(slow_calls) >= 1

    def test_error_5xx_logged(self, trace_app):
        """A 5xx response must log an error."""
        from starlette.testclient import TestClient
        logger = logging.getLogger("ugc_ai_overpower.web.middleware")
        logger.setLevel(logging.ERROR)

        with patch.object(logger, "error") as mock_error:
            with TestClient(trace_app) as client:
                r = client.get("/error")
            assert r.status_code == 500
            error_calls = [c for c in mock_error.call_args_list if "Request failed" in str(c)]
            assert len(error_calls) >= 1

    def test_request_id_preserved(self, trace_app):
        """If client sends X-Request-ID, the same ID must be returned."""
        from starlette.testclient import TestClient
        custom_id = "my-custom-trace-id-789"
        with TestClient(trace_app) as client:
            r = client.get("/hello", headers={"X-Request-ID": custom_id})
        assert r.headers.get("X-Request-ID") == custom_id


# ═══════════════════════════════════════════════════════════════════════════════
#  5 LOGGING CONFIG TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoggingConfig:
    """Verify structured logging configuration."""

    def test_json_formatter_output(self):
        """JSON formatter must produce valid JSON with expected fields."""
        from ugc_ai_overpower.core.logging_config import JSONFormatter, request_id_var

        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger", level=logging.INFO,
            pathname=__file__, lineno=42, msg="hello world",
            args=(), exc_info=None,
        )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert "timestamp" in parsed
        assert "request_id" in parsed

    def test_log_level_from_env(self, monkeypatch):
        """LOG_LEVEL_<MODULE> env var must set logger level."""
        from ugc_ai_overpower.core.logging_config import apply_env_log_levels

        monkeypatch.setenv("LOG_LEVEL_TEST_MODULE", "ERROR")
        apply_env_log_levels()
        # Env LOG_LEVEL_TEST_MODULE → "test_module" → "test.module"
        test_logger = logging.getLogger("test.module")
        assert test_logger.level == logging.ERROR

    def test_file_rotation_configured(self, tmp_path):
        """setup_logging must create a RotatingFileHandler."""
        from ugc_ai_overpower.core.logging_config import setup_logging

        log_dir = tmp_path / "logs"
        logger = setup_logging(
            name="test_rotate", level=logging.DEBUG,
            log_dir=str(log_dir),
            max_bytes=1024, backup_count=5,
        )

        file_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(file_handlers) == 1
        h = file_handlers[0]
        assert h.maxBytes == 1024
        assert h.backupCount == 5

        # Clean up handlers so other tests don't see duplicates
        for h in list(logger.handlers):
            logger.removeHandler(h)

    def test_request_id_in_context(self):
        """request_id_var must carry value across coroutines."""
        from ugc_ai_overpower.core.logging_config import request_id_var
        import asyncio

        async def inner():
            return request_id_var.get()

        async def outer():
            request_id_var.set("test-rid-456")
            val = await inner()
            assert val == "test-rid-456"
            return val

        result = asyncio.run(outer())
        assert result == "test-rid-456"

    def test_async_safety(self, monkeypatch):
        """Multiple concurrent contexts must not share request IDs."""
        from ugc_ai_overpower.core.logging_config import request_id_var
        import asyncio

        async def worker(rid: str) -> str:
            request_id_var.set(rid)
            await asyncio.sleep(0.02)
            return request_id_var.get()

        async def main():
            results = await asyncio.gather(
                worker("rid-A"),
                worker("rid-B"),
                worker("rid-C"),
            )
            return results

        results = asyncio.run(main())
        assert results == ["rid-A", "rid-B", "rid-C"]
