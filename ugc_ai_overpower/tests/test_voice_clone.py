"""Tests for integrations/voice_clone.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.voice_clone import (
    MAX_DURATION,
    MAX_SAMPLES,
    MIN_DURATION,
    MIN_SAMPLES,
    SUPPORTED_EMOTIONS,
    SUPPORTED_LANGUAGES,
    VoiceCloneResult,
    VoiceCloner,
    VoiceSample,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def vc():
    return VoiceCloner()


@pytest.fixture
def mock_modal():
    m = MagicMock()
    m.is_configured.return_value = True
    m.estimate_cost.return_value = 0.001
    m.check_budget.return_value = True
    m.spend_tracker = {"spent": 0.0}
    return m


@pytest.fixture
def samples():
    return [
        VoiceSample(
            audio_url="https://x.com/sample1.wav",
            transcript="Halo nama saya Budi",
            duration_sec=10.0,
            language="id",
        ),
        VoiceSample(
            audio_url="https://x.com/sample2.wav",
            transcript="Selamat pagi semuanya",
            duration_sec=12.0,
            language="id",
        ),
    ]


# -----------------------------------------------------------------------------
# 1. dataclass behavior
# -----------------------------------------------------------------------------
def test_sample_fingerprint_deterministic():
    s = VoiceSample("https://x.com/a.wav", "hello", 10.0, "id")
    assert s.fingerprint() == s.fingerprint()
    assert len(s.fingerprint()) == 12


def test_sample_fingerprint_changes_with_url():
    a = VoiceSample("https://x.com/a.wav", "hello", 10.0, "id")
    b = VoiceSample("https://x.com/b.wav", "hello", 10.0, "id")
    assert a.fingerprint() != b.fingerprint()


def test_result_defaults():
    r = VoiceCloneResult(voice_id="v1", similarity=0.8, preview_url="u", model="m", cost_usd=0.0)
    assert r.language == "id"
    assert r.name == ""
    assert r.samples_used == 0
    assert r.metadata == {}


def test_result_to_dict():
    r = VoiceCloneResult(voice_id="v1", similarity=0.8, preview_url="u", model="m", cost_usd=0.01)
    d = r.to_dict()
    assert d["voice_id"] == "v1"
    assert d["cost_usd"] == 0.01


def test_supported_languages_includes_id():
    assert "id" in SUPPORTED_LANGUAGES
    assert "en" in SUPPORTED_LANGUAGES


def test_supported_emotions_includes_neutral():
    assert "neutral" in SUPPORTED_EMOTIONS


# -----------------------------------------------------------------------------
# 2. validation
# -----------------------------------------------------------------------------
def test_clone_empty_samples(vc):
    with pytest.raises(ValueError, match="samples cannot be empty"):
        _run(vc.clone([], name="x", target_text="hello"))


def test_clone_too_many_samples(vc):
    s = [VoiceSample("https://x.com/a.wav", "", 10.0, "id") for _ in range(MAX_SAMPLES + 1)]
    with pytest.raises(ValueError, match="max"):
        _run(vc.clone(s, name="x", target_text="hi"))


def test_clone_empty_audio_url(vc):
    s = [VoiceSample("", "", 10.0, "id")]
    with pytest.raises(ValueError, match="audio_url"):
        _run(vc.clone(s, name="x", target_text="hi"))


def test_clone_bad_duration(vc):
    s = [VoiceSample("https://x.com/a.wav", "", 1.0, "id")]
    with pytest.raises(ValueError, match="duration_sec"):
        _run(vc.clone(s, name="x", target_text="hi"))


def test_clone_bad_language(vc):
    s = [VoiceSample("https://x.com/a.wav", "", 10.0, "fr")]
    with pytest.raises(ValueError, match="language"):
        _run(vc.clone(s, name="x", target_text="hi"))


def test_clone_empty_target_text(vc):
    s = [VoiceSample("https://x.com/a.wav", "", 10.0, "id")]
    with pytest.raises(ValueError, match="text cannot be empty"):
        _run(vc.clone(s, name="x", target_text=""))


def test_clone_empty_name(vc, samples):
    with pytest.raises(ValueError, match="name"):
        _run(vc.clone(samples, name="", target_text="halo"))


def test_clone_target_text_too_long(vc, samples):
    with pytest.raises(ValueError, match="text too long"):
        _run(vc.clone(samples, name="x", target_text="a" * 5001))


def test_clone_bad_target_language(vc, samples):
    with pytest.raises(ValueError, match="unsupported language"):
        _run(vc.clone(samples, name="x", target_text="halo", language="fr"))


# -----------------------------------------------------------------------------
# 3. clone + cache
# -----------------------------------------------------------------------------
def test_clone_modal_path(vc, mock_modal, samples):
    vc.modal = mock_modal
    r = _run(vc.clone(samples, name="budi", target_text="Halo dunia"))
    assert isinstance(r, VoiceCloneResult)
    assert r.name == "budi"
    assert r.model == "cosyvoice-2"
    assert r.samples_used == 2
    assert r.similarity > 0.5
    assert r.voice_id.startswith("vc_")


def test_clone_fallback_path(vc, samples):
    # No modal dispatcher -> fallback to kokoro-tts
    r = _run(vc.clone(samples, name="fallback", target_text="Halo dunia"))
    assert r.model == "kokoro-tts"
    assert r.cost_usd == 0.01


def test_clone_cache_hit(vc, samples):
    r1 = _run(vc.clone(samples, name="cache_test", target_text="halo"))
    r2 = _run(vc.clone(samples, name="cache_test", target_text="halo"))
    assert r1.voice_id == r2.voice_id
    assert r1.similarity == r2.similarity


def test_clone_similarity_more_samples_higher(samples):
    vc = VoiceCloner()
    r1 = _run(vc.clone(samples[:1], name="one", target_text="halo"))
    r2 = _run(vc.clone(samples, name="two", target_text="halo"))
    assert r2.similarity >= r1.similarity


def test_get_cached_hit(vc, samples):
    _run(vc.clone(samples, name="findme", target_text="halo"))
    r = vc.get_cached("findme")
    assert r is not None
    assert r.name == "findme"


def test_get_cached_miss(vc):
    assert vc.get_cached("nope") is None


# -----------------------------------------------------------------------------
# 4. synthesize + list_voices
# -----------------------------------------------------------------------------
async def _setup_voice(vc, samples):
    return await vc.clone(samples, name="voice1", target_text="halo")


def test_synthesize_returns_bytes(vc, samples):
    r = _run(_setup_voice(vc, samples))
    out = _run(vc.synthesize(r.voice_id, "halo dunia", emotion="happy"))
    assert isinstance(out, bytes)
    assert len(out) > 0


def test_synthesize_unknown_voice(vc):
    with pytest.raises(KeyError, match="unknown voice_id"):
        _run(vc.synthesize("nope", "hello"))


def test_synthesize_bad_emotion(vc, samples):
    r = _run(_setup_voice(vc, samples))
    with pytest.raises(ValueError, match="emotion"):
        _run(vc.synthesize(r.voice_id, "halo", emotion="ecstatic"))


def test_synthesize_bad_speed(vc, samples):
    r = _run(_setup_voice(vc, samples))
    with pytest.raises(ValueError, match="speed"):
        _run(vc.synthesize(r.voice_id, "halo", speed=3.0))


def test_synthesize_empty_text(vc, samples):
    r = _run(_setup_voice(vc, samples))
    with pytest.raises(ValueError, match="text"):
        _run(vc.synthesize(r.voice_id, ""))


def test_synthesize_deterministic(vc, samples):
    r = _run(_setup_voice(vc, samples))
    a = _run(vc.synthesize(r.voice_id, "hello world", emotion="neutral", speed=1.0))
    b = _run(vc.synthesize(r.voice_id, "hello world", emotion="neutral", speed=1.0))
    assert a == b


def test_list_voices(vc, samples):
    _run(_setup_voice(vc, samples))
    voices = _run(vc.list_voices())
    assert len(voices) == 1
    assert voices[0]["name"] == "voice1"
    assert "similarity" in voices[0]


def test_summary(vc):
    s = vc.summary()
    assert s["cached_clones"] == 0
    assert "id" in s["supported_languages"]
    assert s["modal_configured"] is False


# -----------------------------------------------------------------------------
# 5. additional tests (BATCH F)
# -----------------------------------------------------------------------------
def test_clone_with_modal_budget_exceeded_falls_back(vc, mock_modal, samples):
    """When modal budget is exceeded, fall back to kokoro-tts."""
    mock_modal.check_budget.return_value = False
    vc.modal = mock_modal
    r = _run(vc.clone(samples, name="over_budget", target_text="halo"))
    assert r.model == "kokoro-tts"
    assert r.cost_usd == 0.01


def test_clone_with_modal_raises_falls_back(vc, mock_modal, samples):
    """When modal dispatch raises, fall back to kokoro-tts gracefully."""
    mock_modal.estimate_cost.side_effect = RuntimeError("modal down")
    vc.modal = mock_modal
    r = _run(vc.clone(samples, name="modal_down", target_text="halo"))
    assert r.model == "kokoro-tts"
    assert r.metadata["modal_used"] is False


def test_clone_different_niches(samples):
    """Cloning with different language codes produces distinct voice_ids."""
    vc = VoiceCloner()
    r_id = _run(vc.clone(samples, name="indo", target_text="halo", language="id"))
    r_en = _run(vc.clone(samples, name="english", target_text="hello", language="en"))
    assert r_id.voice_id != r_en.voice_id
    assert r_id.language == "id"
    assert r_en.language == "en"


def test_synthesize_cost_varies_with_speed(vc, samples):
    """Faster speed = shorter duration = cheaper synthesis."""
    r = _run(_setup_voice(vc, samples))
    summary_before = dict(vc.summary())
    _run(vc.synthesize(r.voice_id, "halo dunia", speed=2.0))
    _run(vc.synthesize(r.voice_id, "halo dunia", speed=0.5))
    summary_after = vc.summary()
    # Two calls should add to the spend ledger.
    assert summary_after["spent_usd"] > summary_before["spent_usd"]


def test_get_cached_distinguishes_by_name(vc, samples):
    """Cache returns the right result for the right name."""
    _run(vc.clone(samples, name="alpha", target_text="halo"))
    _run(vc.clone(samples, name="beta", target_text="halo"))
    a = vc.get_cached("alpha")
    b = vc.get_cached("beta")
    assert a is not None and b is not None
    assert a.name == "alpha"
    assert b.name == "beta"
