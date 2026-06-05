"""Tests for integrations/modal_dispatch.py and modal_apps/."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.modal_dispatch import (
    MODELS,
    VOICE_PRESETS,
    DEFAULT_BUDGET_USD,
    GenerationResult,
    ModalBudgetExceeded,
    ModalDispatch,
)

modal = pytest.importorskip("modal", reason="modal package not installed")


@pytest.fixture
def tracker():
    return {"spent": 0.0}


@pytest.fixture
def dispatcher(tracker):
    return ModalDispatch(
        token_id="test_id",
        token_secret="test_secret",
        budget_usd=5.0,
        spend_tracker=tracker,
    )


@pytest.fixture
def unconfigured_dispatcher():
    return ModalDispatch(token_id="", token_secret="", budget_usd=5.0, spend_tracker={"spent": 0.0})


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


def test_is_configured_true(dispatcher):
    assert dispatcher.is_configured() is True


def test_is_configured_false(unconfigured_dispatcher):
    assert unconfigured_dispatcher.is_configured() is False


def test_default_budget_constant():
    assert DEFAULT_BUDGET_USD == 5.0


def test_models_registry_has_all_tiers():
    assert "flux-klein-4b" in MODELS
    assert "flux-1.1-pro-ultra" in MODELS
    assert "wan-2.1-1.3b" in MODELS
    assert "wan-2.1-14b" in MODELS
    assert "hunyuan-video-13b" in MODELS
    assert "cosyvoice-2" in MODELS


def test_models_have_required_fields():
    for name, cfg in MODELS.items():
        assert "type" in cfg, f"{name} missing type"
        assert "gpu" in cfg, f"{name} missing gpu"
        assert "tier" in cfg, f"{name} missing tier"
        assert "gpu_per_sec" in cfg, f"{name} missing gpu_per_sec"
        assert cfg["gpu_per_sec"] > 0


def test_list_models_tier_1(dispatcher):
    tier1 = dispatcher.list_models(tier=1)
    assert "flux-klein-4b" in tier1
    assert "wan-2.1-1.3b" in tier1
    assert "cosyvoice-2" in tier1
    assert "wan-2.1-14b" not in tier1


def test_list_models_tier_2(dispatcher):
    tier2 = dispatcher.list_models(tier=2)
    assert "wan-2.1-14b" in tier2
    assert "hunyuan-video-13b" in tier2
    assert "flux-1.1-pro-ultra" in tier2


def test_list_models_image_modality(dispatcher):
    images = dispatcher.list_models(modality="image")
    assert "flux-klein-4b" in images
    assert "flux-1.1-pro-ultra" in images
    assert "wan-2.1-1.3b" not in images


def test_list_models_video_modality(dispatcher):
    videos = dispatcher.list_models(modality="video")
    assert "wan-2.1-1.3b" in videos
    assert "wan-2.1-14b" in videos
    assert "hunyuan-video-13b" in videos


def test_gpu_for_model_known(dispatcher):
    assert dispatcher.gpu_for_model("flux-klein-4b") == "A10G"
    assert dispatcher.gpu_for_model("wan-2.1-14b") == "H100"
    assert dispatcher.gpu_for_model("cosyvoice-2") == "T4"


def test_gpu_for_model_unknown(dispatcher):
    with pytest.raises(ValueError, match="Unknown model"):
        dispatcher.gpu_for_model("nonexistent-model")


def test_estimate_cost_image_default(dispatcher):
    cost = dispatcher.estimate_cost("flux-klein-4b", n=1)
    expected = 0.000976 * 4
    assert cost == round(expected, 6)


def test_estimate_cost_image_with_steps(dispatcher):
    cost = dispatcher.estimate_cost("flux-klein-4b", n=2, steps=8)
    expected = 0.000976 * 8 * 2
    assert cost == round(expected, 6)


def test_estimate_cost_video_with_duration(dispatcher):
    cost = dispatcher.estimate_cost("wan-2.1-1.3b", n=1, duration_sec=10)
    expected = 0.000976 * 10
    assert cost == round(expected, 6)


def test_estimate_cost_audio(dispatcher):
    cost = dispatcher.estimate_cost("cosyvoice-2", duration_sec=15)
    expected = 0.000589 * 15
    assert cost == round(expected, 6)


def test_estimate_cost_unknown_model(dispatcher):
    with pytest.raises(ValueError):
        dispatcher.estimate_cost("nonexistent")


def test_check_budget_under(dispatcher):
    assert dispatcher.check_budget(0.10) is True
    assert dispatcher.check_budget(4.99) is True


def test_check_budget_over(dispatcher, tracker):
    tracker["spent"] = 4.95
    assert dispatcher.check_budget(0.10) is False


def test_remaining_budget(dispatcher, tracker):
    tracker["spent"] = 1.50
    assert dispatcher.remaining_budget() == 3.5


def test_remaining_budget_full(dispatcher):
    assert dispatcher.remaining_budget() == 5.0


def test_text_to_image_success(dispatcher, tracker):
    results = _run(dispatcher.text_to_image("a beautiful sunset", model="flux-klein-4b", n=2))
    assert len(results) == 2
    for r in results:
        assert r.model == "flux-klein-4b"
        assert r.modality == "image"
        assert r.gpu == "A10G"
        assert r.cost_usd > 0
    assert tracker["spent"] > 0


def test_text_to_image_empty_prompt_raises(dispatcher):
    with pytest.raises(ValueError, match="prompt cannot be empty"):
        _run(dispatcher.text_to_image(""))


def test_text_to_image_wrong_model_type(dispatcher):
    with pytest.raises(ValueError, match="not an image model"):
        _run(dispatcher.text_to_image("test", model="wan-2.1-1.3b"))


def test_text_to_image_budget_exceeded(dispatcher, tracker):
    tracker["spent"] = 4.999
    with pytest.raises(ModalBudgetExceeded):
        _run(dispatcher.text_to_image("test", n=4, steps=100))


def test_text_to_image_no_config(unconfigured_dispatcher):
    with pytest.raises(RuntimeError, match="Modal not configured"):
        _run(unconfigured_dispatcher.text_to_image("test"))


def test_text_to_video_success(dispatcher, tracker):
    results = _run(
        dispatcher.text_to_video("a cat playing", model="wan-2.1-1.3b", n=1, duration_sec=5.0)
    )
    assert len(results) == 1
    assert results[0].modality == "video"
    assert results[0].gpu == "A10G"
    assert results[0].duration_sec == 5.0
    assert tracker["spent"] > 0


def test_text_to_video_premium_uses_h100(dispatcher):
    results = _run(dispatcher.text_to_video("test", model="wan-2.1-14b", n=1))
    assert results[0].gpu == "H100"


def test_text_to_video_wrong_model(dispatcher):
    with pytest.raises(ValueError, match="not a video model"):
        _run(dispatcher.text_to_video("test", model="flux-klein-4b"))


def test_text_to_video_empty_prompt(dispatcher):
    with pytest.raises(ValueError):
        _run(dispatcher.text_to_video(""))


def test_voice_synth_success(dispatcher, tracker):
    result = _run(dispatcher.voice_synth("Halo dunia", voice_id="id_female_1"))
    assert result.model == "cosyvoice-2"
    assert result.modality == "audio"
    assert result.gpu == "T4"
    assert result.cost_usd > 0
    assert result.metadata["voice_id"] == "id_female_1"
    assert tracker["spent"] > 0


def test_voice_synth_unknown_voice(dispatcher):
    with pytest.raises(ValueError, match="Unknown voice_id"):
        _run(dispatcher.voice_synth("test", voice_id="invalid_voice"))


def test_voice_synth_empty_text(dispatcher):
    with pytest.raises(ValueError):
        _run(dispatcher.voice_synth(""))


def test_voice_presets_have_indonesian():
    assert "id_female_1" in VOICE_PRESETS
    assert "id_female_2" in VOICE_PRESETS
    assert "id_male_1" in VOICE_PRESETS
    assert "id_male_2" in VOICE_PRESETS


def test_summary_structure(dispatcher):
    s = dispatcher.summary()
    assert s["configured"] is True
    assert s["budget_usd"] == 5.0
    assert s["spent_usd"] == 0.0
    assert s["remaining_usd"] == 5.0
    assert s["models_available"] == len(MODELS)
    assert "flux-klein-4b" in s["models"]


def test_summary_unconfigured(unconfigured_dispatcher):
    s = unconfigured_dispatcher.summary()
    assert s["configured"] is False


def test_modal_apps_imports():
    from ugc_ai_overpower.integrations.modal_apps import (
        APP_NAMES, DEFAULT_GPU_MAP, COST_PER_SECOND
    )
    assert "ugc-text-to-image" in APP_NAMES
    assert DEFAULT_GPU_MAP["ugc-text-to-image"] == "A10G"
    assert COST_PER_SECOND["T4"] < COST_PER_SECOND["A10G"] < COST_PER_SECOND["H100"]


def test_modal_apps_text_to_image_app_defined():
    from ugc_ai_overpower.integrations.modal_apps.text_to_image import (
        APP_NAME, DEFAULT_MODEL, DEFAULT_STEPS, app,
    )
    assert APP_NAME == "ugc-text-to-image"
    assert DEFAULT_MODEL == "flux-klein-4b"
    assert DEFAULT_STEPS == 4
    assert app is not None


def test_modal_apps_text_to_video_app_defined():
    from ugc_ai_overpower.integrations.modal_apps.text_to_video import (
        APP_NAME, DEFAULT_MODEL, DEFAULT_DURATION, app,
    )
    assert APP_NAME == "ugc-text-to-video"
    assert DEFAULT_MODEL == "wan-2.1-1.3b"
    assert DEFAULT_DURATION == 5.0
    assert app is not None


def test_modal_apps_voice_synth_app_defined():
    from ugc_ai_overpower.integrations.modal_apps.voice_synth import (
        APP_NAME, DEFAULT_VOICE, VOICE_PRESETS, app,
    )
    assert APP_NAME == "ugc-voice-synth"
    assert DEFAULT_VOICE == "id_female_1"
    assert "id_female_1" in VOICE_PRESETS
    assert app is not None


def test_voice_preset_metadata():
    from ugc_ai_overpower.integrations.modal_apps.voice_synth import VOICE_PRESETS as VP
    for vid, preset in VP.items():
        assert "name" in preset
        assert "language" in preset
        assert "gender" in preset
        assert "age" in preset
        assert "style" in preset


def test_generation_result_to_dict():
    r = GenerationResult(model="flux-klein-4b", modality="image", cost_usd=0.01, gpu="A10G")
    d = r.to_dict()
    assert d["model"] == "flux-klein-4b"
    assert d["modality"] == "image"
    assert d["cost_usd"] == 0.01
    assert d["gpu"] == "A10G"


def test_5_dollar_budget_can_run_many_images(dispatcher):
    cost_per_image = dispatcher.estimate_cost("flux-klein-4b", n=1)
    n_possible = int(5.0 / cost_per_image)
    assert n_possible > 100


def test_record_spend(dispatcher, tracker):
    dispatcher._record_spend(0.10)
    assert tracker["spent"] == 0.10
    dispatcher._record_spend(0.25)
    assert tracker["spent"] == 0.35


def test_spend_over_budget_raises(dispatcher, tracker):
    tracker["spent"] = 4.95
    with pytest.raises(ModalBudgetExceeded):
        _run(dispatcher.text_to_image("test", n=4, steps=50))
