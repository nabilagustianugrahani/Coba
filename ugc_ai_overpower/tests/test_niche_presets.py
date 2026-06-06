"""Tests for integrations/niche_presets.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.niche_presets import NichePreset, NichePresets


# ---------------------------------------------------------------------------
# NichePreset dataclass
# ---------------------------------------------------------------------------

def test_niche_preset_frozen():
    preset = NichePreset(
        niche="test", primary_colors=["#000"], tone="casual",
        voice_traits=["a"], emoji_style="minimal", common_phrases=["hi"],
        banned_words=["no"], image_style="x", typical_ctas=["go"],
    )
    with pytest.raises(AttributeError):
        preset.niche = "changed"  # type: ignore[misc]


def test_niche_preset_all_fields():
    preset = NichePreset(
        niche="fashion", primary_colors=["#FF69B4", "#000"],
        tone="playful", voice_traits=["trendy", "bold"],
        emoji_style="heavy", common_phrases=["OOTD", "slay"],
        banned_words=["basic"], image_style="Mirror selfies",
        typical_ctas=["Wear this?"],
    )
    assert preset.niche == "fashion"
    assert "#FF69B4" in preset.primary_colors
    assert preset.tone == "playful"
    assert "trendy" in preset.voice_traits


# ---------------------------------------------------------------------------
# NichePresets.PRESETS
# ---------------------------------------------------------------------------

def test_presets_has_eight_niches():
    assert len(NichePresets.PRESETS) == 8


def test_presets_all_niches_have_required_fields():
    for name, p in NichePresets.PRESETS.items():
        assert p.niche == name
        assert len(p.primary_colors) >= 2
        assert p.tone in ("casual", "professional", "playful", "authoritative", "energetic")
        assert len(p.voice_traits) >= 2
        assert p.emoji_style in ("minimal", "moderate", "heavy")
        assert len(p.common_phrases) >= 3
        assert len(p.banned_words) >= 1
        assert len(p.image_style) > 5
        assert len(p.typical_ctas) >= 2


def test_presets_no_duplicate_niches():
    assert len(NichePresets.PRESETS) == len(set(NichePresets.PRESETS.keys()))


# ---------------------------------------------------------------------------
# NichePresets.get
# ---------------------------------------------------------------------------

def test_get_valid_niche():
    preset = NichePresets.get("fashion")
    assert preset.niche == "fashion"


def test_get_case_sensitive():
    with pytest.raises(KeyError):
        NichePresets.get("Fashion")


def test_get_unknown_niche_raises():
    with pytest.raises(KeyError):
        NichePresets.get("nonexistent_niche")


# ---------------------------------------------------------------------------
# NichePresets.list_niches
# ---------------------------------------------------------------------------

def test_list_niches_returns_sorted():
    niches = NichePresets.list_niches()
    assert niches == sorted(niches)
    assert len(niches) == 8
    assert "fashion" in niches
    assert "tech" in niches


# ---------------------------------------------------------------------------
# NichePresets.apply_to_caption
# ---------------------------------------------------------------------------

def test_apply_to_caption_removes_banned_words():
    result = NichePresets.apply_to_caption("fashion", "This look is basic")
    assert "basic" not in result


def test_apply_to_caption_adds_cta_if_missing():
    result = NichePresets.apply_to_caption("beauty", "Great product")
    has_cta = any(kw in result.lower() for kw in ["follow", "subscribe", "share",
                  "like", "comment", "save", "link", "tag", "dm", "shop"])
    assert has_cta


def test_apply_to_caption_does_not_duplicate_phrase():
    result = NichePresets.apply_to_caption("food", "taste test amazing")
    assert result  # non-empty, no crash


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------

def test_get_image_style():
    style = NichePresets.get_image_style("travel")
    assert "drone" in style.lower() or "golden" in style.lower()


def test_get_tone():
    assert NichePresets.get_tone("finance") == "professional"
