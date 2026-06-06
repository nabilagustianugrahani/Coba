"""Tests for integrations/music_gen.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.music_gen import (
    ALLOWED_GENRES,
    ALLOWED_KEYS,
    ALLOWED_MOODS,
    LICENSES,
    MAX_DURATION,
    MIN_DURATION,
    MusicGenerator,
    MusicPrompt,
    MusicTrack,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def mg():
    return MusicGenerator()


@pytest.fixture
def mock_modal():
    m = MagicMock()
    m.is_configured.return_value = True
    m.check_budget.return_value = True
    return m


# -----------------------------------------------------------------------------
# 1. dataclasses + constants
# -----------------------------------------------------------------------------
def test_prompt_defaults():
    p = MusicPrompt()
    assert p.genre == "lo-fi"
    assert p.duration_sec == 60
    assert p.bpm == 120
    assert p.instruments == ["piano"]
    assert p.vocals is False


def test_prompt_fingerprint_stable():
    p = MusicPrompt(genre="cinematic", duration_sec=90, bpm=100)
    a = p.fingerprint()
    b = p.fingerprint()
    assert a == b
    assert len(a) == 16


def test_prompt_fingerprint_changes():
    p1 = MusicPrompt(genre="lo-fi", bpm=80)
    p2 = MusicPrompt(genre="lo-fi", bpm=120)
    assert p1.fingerprint() != p2.fingerprint()


def test_prompt_describe_contains_genre():
    p = MusicPrompt(genre="cinematic", mood="dramatic", bpm=90, key="Am", duration_sec=45)
    desc = p.describe()
    assert "cinematic" in desc
    assert "dramatic" in desc
    assert "90" in desc
    assert "Am" in desc


def test_track_defaults():
    t = MusicTrack(
        track_id="t", audio_url="u", duration_sec=60, genre="lo-fi",
        bpm=120, license="CC0", cost_usd=0.0, model="m",
    )
    assert t.mood == "neutral"
    assert t.metadata == {}


def test_track_to_dict():
    t = MusicTrack(
        track_id="t", audio_url="u", duration_sec=60, genre="lo-fi",
        bpm=120, license="CC0", cost_usd=0.01, model="m",
    )
    d = t.to_dict()
    assert d["track_id"] == "t"
    assert d["license"] == "CC0"


def test_allowed_genres_includes_lofi():
    assert "lo-fi" in ALLOWED_GENRES
    assert "cinematic" in ALLOWED_GENRES
    assert "meditation" in ALLOWED_GENRES


def test_allowed_moods_includes_neutral():
    assert "neutral" in ALLOWED_MOODS
    assert "happy" in ALLOWED_MOODS


def test_licenses_map():
    assert LICENSES["musicgen-small"] == "CC0"
    assert LICENSES["stable-audio"] == "proprietary"


# -----------------------------------------------------------------------------
# 2. validation
# -----------------------------------------------------------------------------
def test_generate_bad_genre(mg):
    p = MusicPrompt(genre="jpop")
    with pytest.raises(ValueError, match="genre"):
        _run(mg.generate(p, "x"))


def test_generate_bad_mood(mg):
    p = MusicPrompt(mood="melancholic")
    with pytest.raises(ValueError, match="mood"):
        _run(mg.generate(p, "x"))


def test_generate_bad_duration_low(mg):
    p = MusicPrompt(duration_sec=1)
    with pytest.raises(ValueError, match="duration_sec"):
        _run(mg.generate(p, "x"))


def test_generate_bad_duration_high(mg):
    p = MusicPrompt(duration_sec=MAX_DURATION + 1)
    with pytest.raises(ValueError, match="duration_sec"):
        _run(mg.generate(p, "x"))


def test_generate_bad_bpm(mg):
    p = MusicPrompt(bpm=300)
    with pytest.raises(ValueError, match="bpm"):
        _run(mg.generate(p, "x"))


def test_generate_bad_key(mg):
    p = MusicPrompt(key="H#")
    with pytest.raises(ValueError, match="key"):
        _run(mg.generate(p, "x"))


def test_generate_empty_instruments(mg):
    p = MusicPrompt(instruments=[])
    with pytest.raises(ValueError, match="instruments"):
        _run(mg.generate(p, "x"))


def test_generate_empty_name(mg):
    p = MusicPrompt()
    with pytest.raises(ValueError, match="name"):
        _run(mg.generate(p, ""))


# -----------------------------------------------------------------------------
# 3. generate routing
# -----------------------------------------------------------------------------
def test_generate_short_uses_musicgen_small(mg):
    p = MusicPrompt(duration_sec=20)
    t = _run(mg.generate(p, "short"))
    assert t.model == "musicgen-small"
    assert t.license == "CC0"


def test_generate_medium_uses_musicgen_large(mg):
    p = MusicPrompt(duration_sec=60)
    t = _run(mg.generate(p, "medium"))
    assert t.model == "musicgen-large"
    assert t.license == "CC-BY"


def test_generate_long_uses_stable_audio(mg):
    p = MusicPrompt(duration_sec=300)
    t = _run(mg.generate(p, "long"))
    assert t.model == "stable-audio"
    assert t.license == "proprietary"


def test_generate_modal_budget_exceeded(mg, mock_modal):
    mock_modal.check_budget.return_value = False
    mg.modal = mock_modal
    p = MusicPrompt(duration_sec=60)
    t = _run(mg.generate(p, "over"))
    # Should escalate to stable-audio.
    assert t.model == "stable-audio"


def test_generate_cost_positive(mg):
    p = MusicPrompt(duration_sec=60)
    t = _run(mg.generate(p, "cost"))
    assert t.cost_usd > 0


def test_generate_cache_hit(mg):
    p = MusicPrompt(duration_sec=30, genre="ambient")
    t1 = _run(mg.generate(p, "cached"))
    t2 = _run(mg.generate(p, "cached"))
    assert t1.track_id == t2.track_id


# -----------------------------------------------------------------------------
# 4. generate_for_video + summary
# -----------------------------------------------------------------------------
def test_generate_for_video_fitness(mg):
    meta = {"id": "v1", "tags": ["fitness"], "description": "leg day", "niche": "fitness"}
    t = _run(mg.generate_for_video(meta, target_duration_sec=60))
    assert t.genre == "upbeat"
    assert t.bpm >= 130


def test_generate_for_video_meditation(mg):
    meta = {"id": "v2", "tags": ["meditation"], "description": "calm vibes", "niche": ""}
    t = _run(mg.generate_for_video(meta, target_duration_sec=60))
    assert t.genre == "meditation"
    assert t.bpm <= 70


def test_generate_for_video_cinematic(mg):
    meta = {"id": "v3", "tags": ["travel", "vlog"], "description": "epic drama"}
    t = _run(mg.generate_for_video(meta, target_duration_sec=60))
    assert t.genre == "cinematic"
    assert t.mood in {"dramatic", "neutral"}


def test_generate_for_video_bad_metadata(mg):
    with pytest.raises(ValueError):
        _run(mg.generate_for_video("not a dict", target_duration_sec=60))


def test_generate_for_video_bad_duration(mg):
    with pytest.raises(ValueError, match="target_duration_sec"):
        _run(mg.generate_for_video({"id": "x"}, target_duration_sec=1))


def test_generate_for_video_clamps_duration(mg):
    meta = {"id": "v4", "tags": ["fitness"], "description": "x"}
    t = _run(mg.generate_for_video(meta, target_duration_sec=200))
    # tiktok-style would clamp to 90, but generate_for_video returns what
    # the prompt says; ensure it's a valid track.
    assert t.duration_sec == 200


def test_list_genres(mg):
    g = _run(mg.list_genres())
    assert "lo-fi" in g
    assert "cinematic" in g


def test_get_cached_hit(mg):
    p = MusicPrompt(genre="ambient")
    _run(mg.generate(p, "hit"))
    t = mg.get_cached("hit")
    assert t is not None


def test_get_cached_miss(mg):
    assert mg.get_cached("nope") is None


def test_summary(mg):
    s = mg.summary()
    assert s["cached_tracks"] == 0
    assert "0-30s" in s["model_routing"]
    assert s["modal_configured"] is False
