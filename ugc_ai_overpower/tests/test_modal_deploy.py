"""Tests for modal_deploy.py, wan_video_gen.py, and flux_klein.py.

40 tests total:
  - 12 tests for ModalDeployer
  - 12 tests for wan_video_gen (mocked)
  - 10 tests for flux_klein (mocked)
  -  6 integration tests
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("modal", reason="modal package not installed")

from ugc_ai_overpower.integrations.modal_deploy import (
    DEFAULT_BUDGET_USD,
    GPU_HOURLY_RATES,
    ModalAuthError,
    ModalDeployConfig,
    ModalDeployer,
)

# ---------------------------------------------------------------------------
# Helpers: import modal app modules with decorators patched so functions
# remain callable (modal.App.function + fastapi_endpoint wrap them otherwise).
# We also patch the image/volume creation so we don't need real modal infra.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _wan_mod():
    """Import wan_video_gen with patched decorators, caching for module scope."""
    _cache = getattr(_wan_mod, "_cache", None)
    if _cache is not None:
        return _cache
    with patch("modal.App") as mock_app, \
         patch("modal.fastapi_endpoint", lambda **kw: lambda f: f), \
         patch("modal.Image.debian_slim"), \
         patch("modal.Volume.from_name"):
        mock_instance = MagicMock()
        mock_instance.function = lambda **kw: lambda f: f
        mock_instance.name = "ugc-wan-video-gen"
        mock_app.return_value = mock_instance
        # Remove cached import if any
        if "ugc_ai_overpower.integrations.modal_apps.wan_video_gen" in sys.modules:
            del sys.modules["ugc_ai_overpower.integrations.modal_apps.wan_video_gen"]
        mod = importlib.import_module(
            "ugc_ai_overpower.integrations.modal_apps.wan_video_gen"
        )
        # Ensure the mock_app is used as the app
        mod.app = mock_instance
        _wan_mod._cache = mod
    return mod


@pytest.fixture(scope="module")
def _flux_mod():
    """Import flux_klein with patched decorators, caching for module scope."""
    _cache = getattr(_flux_mod, "_cache", None)
    if _cache is not None:
        return _cache
    with patch("modal.App") as mock_app, \
         patch("modal.fastapi_endpoint", lambda **kw: lambda f: f), \
         patch("modal.Image.debian_slim"), \
         patch("modal.Volume.from_name"):
        mock_instance = MagicMock()
        mock_instance.function = lambda **kw: lambda f: f
        mock_instance.name = "ugc-flux-klein"
        mock_app.return_value = mock_instance
        if "ugc_ai_overpower.integrations.modal_apps.flux_klein" in sys.modules:
            del sys.modules["ugc_ai_overpower.integrations.modal_apps.flux_klein"]
        mod = importlib.import_module(
            "ugc_ai_overpower.integrations.modal_apps.flux_klein"
        )
        mod.app = mock_instance
        _flux_mod._cache = mod
    return mod


# ---------------------------------------------------------------------------
# ModalDeployConfig tests
# ---------------------------------------------------------------------------

class TestModalDeployConfig:
    def test_valid_config(self):
        cfg = ModalDeployConfig(app_name="test-app")
        assert cfg.validate() == []

    def test_missing_app_name(self):
        cfg = ModalDeployConfig(app_name="")
        errors = cfg.validate()
        assert any("app_name" in e for e in errors)

    def test_whitespace_app_name(self):
        cfg = ModalDeployConfig(app_name="   ")
        errors = cfg.validate()
        assert any("app_name" in e for e in errors)

    def test_invalid_gpu(self):
        cfg = ModalDeployConfig(app_name="test", gpu="INVALID")
        errors = cfg.validate()
        assert any("gpu" in e.lower() for e in errors)

    def test_negative_cpu(self):
        cfg = ModalDeployConfig(app_name="test", cpu=-1)
        errors = cfg.validate()
        assert any("cpu" in e.lower() for e in errors)

    def test_small_memory(self):
        cfg = ModalDeployConfig(app_name="test", memory_mb=64)
        errors = cfg.validate()
        assert any("memory" in e.lower() for e in errors)

    def test_to_app_kwargs(self):
        cfg = ModalDeployConfig(app_name="test", gpu="A10G", timeout_sec=120, memory_mb=4096)
        kwargs = cfg.to_app_kwargs()
        assert kwargs["gpu"] == "A10G"
        assert kwargs["timeout"] == 120
        assert kwargs["memory"] == 4096
        assert "schedule" not in kwargs

    def test_to_app_kwargs_with_schedule(self):
        cfg = ModalDeployConfig(app_name="test", schedule="daily")
        kwargs = cfg.to_app_kwargs()
        assert kwargs["schedule"] == "daily"

    def test_default_values(self):
        cfg = ModalDeployConfig(app_name="my-app")
        assert cfg.python_version == "3.12"
        assert cfg.gpu == "T4"
        assert cfg.cpu == 1.0
        assert cfg.memory_mb == 2048
        assert cfg.timeout_sec == 300
        assert cfg.concurrency_limit == 10
        assert cfg.secrets == []
        assert cfg.schedule is None

    def test_gpu_hourly_rates_known_gpus(self):
        assert "T4" in GPU_HOURLY_RATES
        assert "A10G" in GPU_HOURLY_RATES
        assert "H100" in GPU_HOURLY_RATES
        assert GPU_HOURLY_RATES["T4"] < GPU_HOURLY_RATES["A10G"] < GPU_HOURLY_RATES["H100"]

    def test_default_budget_constant(self):
        assert DEFAULT_BUDGET_USD == 5.0


# ---------------------------------------------------------------------------
# ModalDeployer tests
# ---------------------------------------------------------------------------

class TestModalDeployer:
    def test_not_authenticated_without_creds(self):
        d = ModalDeployer(token_id="", token_secret="")
        assert d.is_authenticated() is False

    def test_not_authenticated_wrong_creds(self):
        d = ModalDeployer(token_id="bad", token_secret="bad")
        assert d.is_authenticated() is False

    def test_estimate_cost_returns_positive(self):
        d = ModalDeployer(token_id="id", token_secret="secret")
        cfg = ModalDeployConfig(app_name="test", gpu="T4", timeout_sec=60)
        cost = d.estimate_cost("/fake/path.py", cfg)
        assert cost > 0

    def test_estimate_cost_scales_with_gpu(self):
        d = ModalDeployer(token_id="id", token_secret="secret")
        cfg_t4 = ModalDeployConfig(app_name="test", gpu="T4", timeout_sec=60)
        cfg_h100 = ModalDeployConfig(app_name="test", gpu="H100", timeout_sec=60)
        cost_t4 = d.estimate_cost("/fake.py", cfg_t4)
        cost_h100 = d.estimate_cost("/fake.py", cfg_h100)
        assert cost_t4 < cost_h100

    def test_estimate_cost_scales_with_timeout(self):
        d = ModalDeployer(token_id="id", token_secret="secret")
        cfg_short = ModalDeployConfig(app_name="test", gpu="A10G", timeout_sec=60)
        cfg_long = ModalDeployConfig(app_name="test", gpu="A10G", timeout_sec=600)
        short = d.estimate_cost("/fake.py", cfg_short)
        long = d.estimate_cost("/fake.py", cfg_long)
        assert short < long

    def test_deploy_missing_file_raises(self):
        d = ModalDeployer(token_id="id", token_secret="secret")
        cfg = ModalDeployConfig(app_name="test")
        with pytest.raises(FileNotFoundError, match="not found"):
            d.deploy("/nonexistent/app.py", cfg)

    def test_deploy_unauthenticated_raises(self):
        d = ModalDeployer(token_id="", token_secret="")
        cfg = ModalDeployConfig(app_name="test")
        with pytest.raises(ModalAuthError, match="not configured"):
            d.deploy("/tmp/fake_app.py", cfg)

    def test_undeploy_unauthenticated_raises(self):
        d = ModalDeployer(token_id="", token_secret="")
        with pytest.raises(ModalAuthError, match="not configured"):
            d.undeploy("test-app")

    def test_list_apps_unauthenticated_raises(self):
        d = ModalDeployer(token_id="", token_secret="")
        with pytest.raises(ModalAuthError, match="not configured"):
            d.list_apps()

    def test_get_app_stats_unauthenticated_raises(self):
        d = ModalDeployer(token_id="", token_secret="")
        with pytest.raises(ModalAuthError, match="not configured"):
            d.get_app_stats("test-app")

    def test_summary_structure(self):
        d = ModalDeployer(token_id="id", token_secret="secret", budget_usd=5.0)
        s = d.summary()
        assert s["budget_usd"] == 5.0
        assert s["spent_usd"] == 0.0
        assert s["remaining_usd"] == 5.0
        assert "gpu_rates" in s
        assert s["authenticated"] is False

    def test_summary_with_budget_tracking(self):
        tracker = {"spent": 2.50}
        d = ModalDeployer(token_id="id", token_secret="secret", budget_usd=10.0, spend_tracker=tracker)
        s = d.summary()
        assert s["budget_usd"] == 10.0
        assert s["spent_usd"] == 2.50
        assert s["remaining_usd"] == 7.50


# ---------------------------------------------------------------------------
# wan_video_gen tests (mocked)
# ---------------------------------------------------------------------------

class TestWanVideoGenApp:
    def test_app_name(self, _wan_mod):
        assert _wan_mod.APP_NAME == "ugc-wan-video-gen"

    def test_default_model(self, _wan_mod):
        assert _wan_mod.DEFAULT_MODEL == "wan-2.1-1.3b"

    def test_default_duration(self, _wan_mod):
        assert _wan_mod.DEFAULT_DURATION == 5.0

    def test_default_resolution(self, _wan_mod):
        assert _wan_mod.DEFAULT_RESOLUTION == "720p"

    def test_default_fps(self, _wan_mod):
        assert _wan_mod.DEFAULT_FPS == 24

    def test_health_endpoint_returns_dict(self, _wan_mod):
        result = _wan_mod.health()
        assert result["app"] == _wan_mod.APP_NAME
        assert result["status"] == "healthy"
        assert "wan-2.1-1.3b" in result["models"]
        assert result["sglang_diffusion"] is True

    def test_generate_returns_error_on_exception(self, _wan_mod):
        with patch.object(_wan_mod, "_generate_wan_video",
                          side_effect=RuntimeError("mock failure")):
            result = _wan_mod.generate(prompt="test video", model="wan-2.1-1.3b", n=1)
        assert "error" in result
        assert "mock failure" in result["error"]

    def test_generate_clamps_n(self, _wan_mod):
        with patch.object(_wan_mod, "_generate_wan_video",
                          return_value=["aaaa", "bbbb"]):
            result = _wan_mod.generate(prompt="test", model="wan-2.1-1.3b", n=10)
        assert result["n"] <= 2

    def test_generate_returns_cost_and_gpu(self, _wan_mod):
        with patch.object(_wan_mod, "_generate_wan_video",
                          return_value=["video_b64_data"]):
            result = _wan_mod.generate(prompt="test", model="wan-2.1-14b", n=1)
        assert result["gpu"] == "H100"
        assert result["cost_usd"] >= 0

    def test_generate_returns_proper_structure(self, _wan_mod):
        with patch.object(_wan_mod, "_generate_wan_video",
                          return_value=["abc"]):
            result = _wan_mod.generate(prompt="a cat playing", model="wan-2.1-1.3b",
                                       duration_sec=3.0, n=1)
        assert "videos_b64" in result
        assert result["model"] == "wan-2.1-1.3b"
        assert result["duration_sec"] == 3.0
        assert result["resolution"] == "720p"
        assert result["fps"] == 24

    def test_app_is_modal_app(self, _wan_mod):
        assert _wan_mod.app is not None
        assert _wan_mod.app.name == "ugc-wan-video-gen"


# ---------------------------------------------------------------------------
# flux_klein tests (mocked)
# ---------------------------------------------------------------------------

class TestFluxKleinApp:
    def test_app_name(self, _flux_mod):
        assert _flux_mod.APP_NAME == "ugc-flux-klein"

    def test_default_model(self, _flux_mod):
        assert _flux_mod.DEFAULT_MODEL == "flux-klein-4b"

    def test_default_steps(self, _flux_mod):
        assert _flux_mod.DEFAULT_STEPS == 4

    def test_default_resolution(self, _flux_mod):
        assert _flux_mod.DEFAULT_RESOLUTION == "1024x1024"

    def test_health_endpoint_returns_dict(self, _flux_mod):
        result = _flux_mod.health()
        assert result["app"] == _flux_mod.APP_NAME
        assert result["status"] == "healthy"
        assert "flux-klein-4b" in result["models"]
        assert result["sglang_diffusion"] is False

    def test_generate_returns_error_on_exception(self, _flux_mod):
        with patch.object(_flux_mod, "_generate_flux_klein",
                          side_effect=RuntimeError("mock failure")):
            result = _flux_mod.generate(prompt="test image", steps=4)
        assert "error" in result
        assert "mock failure" in result["error"]

    def test_generate_clamps_n(self, _flux_mod):
        with patch.object(_flux_mod, "_generate_flux_klein",
                          return_value=["img"]):
            result = _flux_mod.generate(prompt="test", n=10)
        assert result["n"] <= 4

    def test_generate_returns_cost_and_gpu(self, _flux_mod):
        with patch.object(_flux_mod, "_generate_flux_klein",
                          return_value=["img_b64"]):
            result = _flux_mod.generate(prompt="test", steps=4)
        assert result["gpu"] == "A10G"
        assert result["cost_usd"] >= 0

    def test_generate_returns_proper_structure(self, _flux_mod):
        with patch.object(_flux_mod, "_generate_flux_klein",
                          return_value=["a", "b"]):
            result = _flux_mod.generate(prompt="sunset", steps=4, width=512, height=512, n=2)
        assert "images_b64" in result
        assert result["model"] == "flux-klein-4b"
        assert result["n"] == 2
        assert result["steps"] == 4
        assert result["resolution"] == "512x512"

    def test_app_is_modal_app(self, _flux_mod):
        assert _flux_mod.app is not None
        assert _flux_mod.app.name == "ugc-flux-klein"


# ---------------------------------------------------------------------------
# Integration-style tests
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_modal_deployer_uses_spend_tracker(self):
        tracker = {"spent": 0.0}
        d = ModalDeployer(token_id="id", token_secret="secret", budget_usd=5.0, spend_tracker=tracker)
        assert d.spend_tracker is tracker
        d.spend_tracker["spent"] = 1.0
        assert tracker["spent"] == 1.0

    def test_extract_url_from_output(self):
        url = ModalDeployer._extract_url(
            "Deployed 'my-app' at https://my-app.modal.app\n", "my-app"
        )
        assert "https://" in url
        assert "my-app" in url

    def test_extract_url_fallback(self):
        url = ModalDeployer._extract_url("some random output\n", "my-app")
        assert "my-app.modal.app" in url

    def test_modal_deployer_summary_consistent_with_tracker(self):
        tracker = {"spent": 3.0}
        d = ModalDeployer(token_id="a", token_secret="b", budget_usd=10.0, spend_tracker=tracker)
        s = d.summary()
        assert s["spent_usd"] == 3.0
        assert s["remaining_usd"] == 7.0
        assert s["budget_usd"] == 10.0

    def test_wan_video_gen_and_flux_klein_have_distinct_names(self, _wan_mod, _flux_mod):
        assert _wan_mod.APP_NAME != _flux_mod.APP_NAME

    def test_wan_and_flux_health_both_healthy(self, _wan_mod, _flux_mod):
        assert _wan_mod.health()["status"] == "healthy"
        assert _flux_mod.health()["status"] == "healthy"
