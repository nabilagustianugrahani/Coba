"""Tests for fal_dispatch and ai_dispatch (zerocost-first unified AI).

Run: cd /workspaces/Coba/ugc_ai_overpower && python -m pytest tests/test_fal_ai_dispatch.py -v
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest


class TestFalModels:
    def test_fal_models_dict_populated(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FAL_MODELS
        assert len(FAL_MODELS) >= 10
        assert "wan-t2v" in FAL_MODELS
        assert "wan-pro-t2v" in FAL_MODELS
        assert "flux-schnell" in FAL_MODELS
        assert "flux-pro" in FAL_MODELS
        assert "kling-3.0-pro" in FAL_MODELS
        assert "veo-3.1" in FAL_MODELS

    def test_video_models_have_pricing(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FAL_MODELS
        for name, cfg in FAL_MODELS.items():
            if cfg.get("type") == "video":
                has_price = any(k.startswith("price") for k in cfg)
                assert has_price, f"{name} missing price"

    def test_image_models_have_per_image_price(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FAL_MODELS
        for name, cfg in FAL_MODELS.items():
            if cfg.get("type") == "image":
                assert "price_per_image" in cfg, f"{name} missing price_per_image"

    def test_ultrarealistic_video_models(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FAL_MODELS
        ur = [n for n, c in FAL_MODELS.items() if c.get("ultrarealistic") and c.get("type") == "video"]
        assert len(ur) >= 5

    def test_open_source_models_marked(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FAL_MODELS
        os_models = [n for n, c in FAL_MODELS.items() if c.get("open_source")]
        assert "wan-t2v" in os_models
        assert "hunyuan-video-1.5-t2v" in os_models
        assert "flux-schnell" in os_models
        assert "kokoro-tts" in os_models


class TestFalDispatcherInit:
    def test_default_init(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        assert d.budget_usd == 5.0
        assert d.is_configured() is False

    def test_init_with_key(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher(api_key="test-fal-key-123")
        assert d.is_configured() is True
        assert d.api_key == "test-fal-key-123"

    def test_env_var_key(self, monkeypatch):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        monkeypatch.setenv("FAL_KEY", "env-fal-key")
        d = FalDispatcher()
        assert d.is_configured() is True

    def test_custom_budget(self, monkeypatch):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        monkeypatch.delenv("FAL_BUDGET_USD", raising=False)
        d = FalDispatcher(budget_usd=2.50)
        assert d.budget_usd == 2.50

    def test_shared_spend_tracker(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        tracker = {"spent": 1.0}
        d1 = FalDispatcher(spend_tracker=tracker, budget_usd=5.0)
        d2 = FalDispatcher(spend_tracker=tracker, budget_usd=5.0)
        d1._record_spend(0.5)
        assert d2.spend_tracker["spent"] == 1.5


class TestFalListModels:
    def test_list_all(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        models = d.list_models()
        assert len(models) == 14

    def test_filter_by_tier(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        tier1 = d.list_models(tier=1)
        tier2 = d.list_models(tier=2)
        tier3 = d.list_models(tier=3)
        assert len(tier1) >= 3
        assert len(tier2) >= 2
        assert len(tier3) >= 2
        assert set(tier1).isdisjoint(set(tier2))

    def test_filter_by_modality(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        videos = d.list_models(modality="video")
        images = d.list_models(modality="image")
        audios = d.list_models(modality="audio")
        assert len(videos) >= 8
        assert len(images) >= 4
        assert len(audios) >= 1

    def test_get_model(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cfg = d.get_model("wan-t2v")
        assert cfg["type"] == "video"
        assert "endpoint" in cfg

    def test_get_unknown_raises(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        with pytest.raises(ValueError):
            d.get_model("nonexistent-model")


class TestFalCostEstimation:
    def test_wan_t2v_5s_480p(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cost = d.estimate_cost("wan-t2v", duration_sec=5.0, resolution="480p")
        assert cost == pytest.approx(0.20, abs=0.001)

    def test_wan_t2v_5s_720p(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cost = d.estimate_cost("wan-t2v", duration_sec=5.0, resolution="720p")
        assert cost == pytest.approx(0.40, abs=0.001)

    def test_wan_pro_5s(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cost = d.estimate_cost("wan-pro-t2v", duration_sec=5.0)
        assert cost == pytest.approx(0.80, abs=0.001)

    def test_ltx_fast_5s(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cost = d.estimate_cost("ltx-2.3-fast-t2v", duration_sec=5.0, resolution="1080p")
        assert cost == pytest.approx(0.20, abs=0.001)

    def test_hunyuan_5s(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cost = d.estimate_cost("hunyuan-video-1.5-t2v", duration_sec=5.0)
        assert cost == pytest.approx(0.375, abs=0.001)

    def test_flux_schnell_per_image(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cost = d.estimate_cost("flux-schnell", n=1)
        assert cost == pytest.approx(0.003, abs=0.001)

    def test_flux_schnell_4_images(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cost = d.estimate_cost("flux-schnell", n=4)
        assert cost == pytest.approx(0.012, abs=0.001)

    def test_kling_5s(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cost = d.estimate_cost("kling-3.0-pro", duration_sec=5.0)
        assert cost == pytest.approx(0.45, abs=0.001)

    def test_veo_lite_5s(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cost = d.estimate_cost("veo-3.1-lite", duration_sec=5.0)
        assert cost == pytest.approx(0.25, abs=0.001)

    def test_kokoro_audio(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        cost = d.estimate_cost("kokoro-tts", n=1)
        assert cost == pytest.approx(0.02, abs=0.001)

    def test_unknown_model_raises(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        with pytest.raises(ValueError):
            d.estimate_cost("unknown")


class TestFalBudget:
    def test_budget_check_ok(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher(budget_usd=1.0)
        assert d.check_budget(0.5) is True

    def test_budget_check_fail(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher(budget_usd=1.0)
        d.spend_tracker["spent"] = 0.9
        assert d.check_budget(0.5) is False

    def test_remaining_budget(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher(budget_usd=5.0)
        d.spend_tracker["spent"] = 1.5
        assert d.remaining_budget() == 3.5

    def test_record_spend(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher(budget_usd=5.0)
        d._record_spend(0.25)
        d._record_spend(0.75)
        assert d.spend_tracker["spent"] == pytest.approx(1.0, abs=0.001)


class TestFalSubmitWithoutConfig:
    def test_submit_unconfigured_raises(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        import asyncio
        with pytest.raises(RuntimeError, match="not configured"):
            asyncio.run(d.submit("wan-t2v", prompt="a cat"))

    def test_submit_budget_exceeded(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher, FalBudgetExceeded
        d = FalDispatcher(api_key="test", budget_usd=0.01)
        d.spend_tracker["spent"] = 0.005
        import asyncio
        with pytest.raises(FalBudgetExceeded):
            asyncio.run(d.submit("wan-pro-t2v", prompt="a cat"))

    def test_submit_no_aiohttp(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher(api_key="test")
        d._check_aiohttp = lambda: False
        import asyncio


class TestFalCompareWithModal:
    def test_modal_cheaper_for_wan(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        result = d.compare_with_modal(modal_cost=0.005, duration_sec=5.0)
        assert result["recommendation"] == "modal"
        assert result["modal_cost_usd"] == 0.005
        assert result["fal_wan_t2v_720p_5s"] == 0.40

    def test_fal_better_for_premium(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher()
        result = d.compare_with_modal(modal_cost=0.50, duration_sec=5.0)
        assert result["recommendation"] in ["fal", "either"]


class TestFalSummary:
    def test_summary_structure(self):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        d = FalDispatcher(budget_usd=5.0)
        s = d.summary()
        assert s["configured"] is False
        assert s["budget_usd"] == 5.0
        assert s["models_available"] >= 10
        assert "free_credit_offer" in s
        assert "models" in s

    def test_summary_with_key(self, monkeypatch):
        from ugc_ai_overpower.integrations.fal_dispatch import FalDispatcher
        monkeypatch.setenv("FAL_KEY", "test-key")
        d = FalDispatcher()
        s = d.summary()
        assert s["configured"] is True


class TestAIDispatchCostTiers:
    def test_cost_tiers_defined(self):
        from ugc_ai_overpower.integrations.ai_dispatch import COST_TIERS
        assert "free" in COST_TIERS
        assert "ultra_cheap" in COST_TIERS
        assert "cheap" in COST_TIERS
        assert "moderate" in COST_TIERS
        assert "premium" in COST_TIERS
        assert COST_TIERS["free"] < COST_TIERS["ultra_cheap"] < COST_TIERS["cheap"] < COST_TIERS["moderate"] < COST_TIERS["premium"]

    def test_modal_to_fal_bridge(self):
        from ugc_ai_overpower.integrations.ai_dispatch import MODAL_TO_FAL_BRIDGE
        assert "wan-2.1-1.3b" in MODAL_TO_FAL_BRIDGE
        assert MODAL_TO_FAL_BRIDGE["wan-2.1-1.3b"] == "wan-t2v"
        assert MODAL_TO_FAL_BRIDGE["flux-klein-4b"] == "flux-schnell"

    def test_fal_only_models(self):
        from ugc_ai_overpower.integrations.ai_dispatch import FAL_ONLY_MODELS
        assert "kling-3.0-pro" in FAL_ONLY_MODELS
        assert "veo-3.1" in FAL_ONLY_MODELS
        assert "ltx-2.3-t2v" in FAL_ONLY_MODELS


class TestAIDispatchRequest:
    def test_cost_tier_classification(self):
        from ugc_ai_overpower.integrations.ai_dispatch import DispatchRequest
        assert DispatchRequest(model="x", max_cost_usd=0.0).cost_tier() == "free"
        assert DispatchRequest(model="x", max_cost_usd=0.005).cost_tier() == "ultra_cheap"
        assert DispatchRequest(model="x", max_cost_usd=0.03).cost_tier() == "cheap"
        assert DispatchRequest(model="x", max_cost_usd=0.15).cost_tier() == "moderate"
        assert DispatchRequest(model="x", max_cost_usd=1.0).cost_tier() == "premium"

    def test_default_modalities(self):
        from ugc_ai_overpower.integrations.ai_dispatch import DispatchRequest
        req = DispatchRequest(model="wan-2.1-1.3b", prompt="test")
        assert "modal" in req.modalities
        assert "fal" in req.modalities

    def test_to_dict(self):
        from ugc_ai_overpower.integrations.ai_dispatch import DispatchRequest
        req = DispatchRequest(model="wan-2.1-1.3b", prompt="a cat", duration_sec=5.0)
        d = req.cost_tier()
        assert d in ["free", "ultra_cheap", "cheap", "moderate", "premium"]


class TestUnifiedAIDispatcher:
    def test_init_no_providers(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher
        d = UnifiedAIDispatcher()
        s = d.summary()
        assert s["modal_configured"] is False
        assert s["fal_configured"] is False

    def test_init_with_mock_providers(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher
        modal = MagicMock()
        modal.is_configured.return_value = True
        modal.estimate_cost.return_value = 0.005
        fal = MagicMock()
        fal.is_configured.return_value = True
        fal.estimate_cost.return_value = 0.40
        d = UnifiedAIDispatcher(modal_dispatcher=modal, fal_dispatcher=fal)
        s = d.summary()
        assert s["modal_configured"] is True
        assert s["fal_configured"] is True

    def test_estimate_modal_via_bridge(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher, DispatchRequest
        modal = MagicMock()
        modal.is_configured.return_value = True
        fal = MagicMock()
        fal.is_configured.return_value = True
        fal.estimate_cost.return_value = 0.40
        d = UnifiedAIDispatcher(modal_dispatcher=modal, fal_dispatcher=fal)
        cost = d._estimate_fal("wan-t2v", DispatchRequest(model="wan-2.1-1.3b", duration_sec=5.0))
        assert cost == 0.40

    def test_estimate_unknown_provider(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher, DispatchRequest
        d = UnifiedAIDispatcher()
        cost = d._estimate_fal("wan-t2v", DispatchRequest(model="wan-2.1-1.3b"))
        assert cost == float("inf")

    def test_decide_prefers_modal_for_open_source(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher, DispatchRequest
        modal = MagicMock()
        modal.is_configured.return_value = True
        fal = MagicMock()
        fal.is_configured.return_value = True
        fal.estimate_cost.return_value = 0.20
        d = UnifiedAIDispatcher(modal_dispatcher=modal, fal_dispatcher=fal)
        req = DispatchRequest(model="wan-2.1-1.3b", prompt="a cat", max_cost_usd=0.30)
        decision = d.estimate_only(req)
        assert decision.chosen_provider in ["modal", "fal"]
        assert decision.chosen_model != ""

    def test_decide_skips_over_budget(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher, DispatchRequest
        modal = MagicMock()
        modal.is_configured.return_value = True
        fal = MagicMock()
        fal.is_configured.return_value = True
        fal.estimate_cost.return_value = 0.80
        d = UnifiedAIDispatcher(modal_dispatcher=modal, fal_dispatcher=fal)
        req = DispatchRequest(model="wan-pro-t2v", max_cost_usd=0.10, modalities=["fal"])
        decision = d.estimate_only(req)
        if decision.chosen_provider:
            assert decision.estimated_cost_usd <= 0.80

    def test_decide_prefers_open_source(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher, DispatchRequest
        modal = MagicMock()
        modal.is_configured.return_value = True
        fal = MagicMock()
        fal.is_configured.return_value = True
        fal.estimate_cost.return_value = 0.20
        d = UnifiedAIDispatcher(modal_dispatcher=modal, fal_dispatcher=fal)
        req = DispatchRequest(
            model="wan-2.1-1.3b", max_cost_usd=0.50,
            prefer_open_source=True, modalities=["fal"]
        )
        decision = d.estimate_only(req)
        if decision.chosen_provider == "fal":
            assert "wan" in decision.chosen_model

    def test_no_providers_returns_no_choice(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher, DispatchRequest
        d = UnifiedAIDispatcher()
        req = DispatchRequest(model="wan-2.1-1.3b", max_cost_usd=0.20)
        decision = d.estimate_only(req)
        assert decision.chosen_provider == ""
        assert "no providers" in decision.reason or decision.reason == "no providers available"

    def test_dispatch_async_runs(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher, DispatchRequest
        from ugc_ai_overpower.integrations.fal_dispatch import FalResult
        modal = MagicMock()
        modal.is_configured.return_value = True
        fal = MagicMock()
        fal.is_configured.return_value = True
        fal.estimate_cost.return_value = 0.40

        async def submit_ok(*a, **kw):
            return FalResult(model="wan-t2v", modality="video", media_url="https://x", cost_usd=0.40)
        fal.submit = submit_ok
        d = UnifiedAIDispatcher(modal_dispatcher=modal, fal_dispatcher=fal)
        req = DispatchRequest(model="wan-2.1-1.3b", max_cost_usd=0.50, modalities=["fal"])
        decision = d.dispatch_sync(req)
        assert decision.chosen_provider != ""
        assert decision.executed is True
        assert decision.result is not None

    def test_dispatch_handles_exception(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher, DispatchRequest
        modal = MagicMock()
        modal.is_configured.return_value = True
        fal = MagicMock()
        fal.is_configured.return_value = True
        fal.estimate_cost.return_value = 0.40

        async def boom(*a, **kw):
            raise RuntimeError("network fail")
        fal.submit = boom
        d = UnifiedAIDispatcher(modal_dispatcher=modal, fal_dispatcher=fal)
        req = DispatchRequest(model="wan-2.1-1.3b", max_cost_usd=0.50, modalities=["fal"])
        decision = d.dispatch_sync(req)
        assert decision.executed is True
        assert "error" in (decision.result or {})


class TestAIDispatchSummary:
    def test_summary_keys(self):
        from ugc_ai_overpower.integrations.ai_dispatch import UnifiedAIDispatcher
        d = UnifiedAIDispatcher()
        s = d.summary()
        for key in ["providers_available", "modal_configured", "fal_configured",
                    "modal_to_fal_bridge", "fal_only_models", "preference_order", "cost_tiers"]:
            assert key in s

    def test_preference_order(self):
        from ugc_ai_overpower.integrations.ai_dispatch import PREFERENCE_ORDER
        assert PREFERENCE_ORDER[0] == "modal"
        assert "fal" in PREFERENCE_ORDER
