"""Tests for integrations/cta_generator.py — 18 tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.cta_generator import (
    CTAInput,
    CTAResult,
    CTAGenerator,
    FUNNEL_STAGES,
    NICHES,
    TEMPLATES,
    TONES,
)


@pytest.fixture
def gen():
    return CTAGenerator()


# ---------- dataclass basics ----------

def test_cta_input_defaults():
    ci = CTAInput()
    assert ci.niche == "general"
    assert ci.platform == "instagram"
    assert ci.funnel_stage == "awareness"
    assert ci.tone == "casual"


def test_cta_result_fields():
    r = CTAResult(primary_cta="Shop now!", alternative_ctas=["Buy now"], emoji_suggestion="🔥", estimated_ctr=0.045)
    assert r.primary_cta == "Shop now!"
    assert r.estimated_ctr == 0.045


# ---------- TEMPLATES structure ----------

def test_templates_all_niches_present():
    for niche in NICHES:
        assert niche in TEMPLATES, f"Missing niche: {niche}"


def test_templates_all_stages_present():
    for niche in NICHES:
        for stage in FUNNEL_STAGES:
            assert stage in TEMPLATES[niche], f"Missing stage {stage} for {niche}"


def test_templates_all_tones_present():
    for niche in NICHES:
        for stage in FUNNEL_STAGES:
            for tone in TONES:
                assert tone in TEMPLATES[niche][stage], f"Missing tone {tone} for {niche}/{stage}"


def test_templates_have_content():
    for niche in NICHES:
        for stage in FUNNEL_STAGES:
            for tone in TONES:
                ctas = TEMPLATES[niche][stage][tone]
                assert len(ctas) >= 1, f"Empty template for {niche}/{stage}/{tone}"


# ---------- generate() ----------

def test_generate_returns_result(gen):
    r = gen.generate(CTAInput(niche="fashion", platform="instagram", funnel_stage="awareness", tone="casual"))
    assert isinstance(r, CTAResult)


def test_generate_primary_cta_not_empty(gen):
    r = gen.generate(CTAInput(niche="tech", platform="tiktok", funnel_stage="conversion", tone="playful"))
    assert r.primary_cta and r.primary_cta.strip()


def test_generate_alternative_ctas(gen):
    r = gen.generate(CTAInput(niche="food", platform="instagram", funnel_stage="consideration", tone="professional"))
    assert len(r.alternative_ctas) >= 1


def test_generate_emoji_suggestion(gen):
    r = gen.generate(CTAInput(niche="beauty", platform="instagram", funnel_stage="retention", tone="casual"))
    assert r.emoji_suggestion in ("✨", "💕", "🚀", "😋", "💪", "✈️", "💰", "💫")


def test_generate_estimated_ctr_in_range(gen):
    for niche in NICHES:
        r = gen.generate(CTAInput(niche=niche, platform="instagram", funnel_stage="awareness", tone="casual"))
        assert 0.0 <= r.estimated_ctr <= 1.0


def test_generate_tone_differentiation(gen):
    casual = gen.generate(CTAInput(niche="fashion", platform="instagram", funnel_stage="awareness", tone="casual"))
    professional = gen.generate(CTAInput(niche="fashion", platform="instagram", funnel_stage="awareness", tone="professional"))
    assert casual.primary_cta != professional.primary_cta


# ---------- validation ----------

def test_generate_invalid_niche(gen):
    with pytest.raises(ValueError, match="Unsupported niche"):
        gen.generate(CTAInput(niche="invalid"))


def test_generate_invalid_stage(gen):
    with pytest.raises(ValueError, match="Unsupported funnel_stage"):
        gen.generate(CTAInput(niche="fashion", funnel_stage="invalid"))


def test_generate_invalid_tone(gen):
    with pytest.raises(ValueError, match="Unsupported tone"):
        gen.generate(CTAInput(niche="fashion", tone="invalid"))


def test_generate_invalid_platform(gen):
    with pytest.raises(ValueError, match="Unsupported platform"):
        gen.generate(CTAInput(niche="fashion", platform="invalid"))


# ---------- ab_test_variants ----------

def test_ab_test_variants_returns_list(gen):
    variants = gen.ab_test_variants("fashion", 3)
    assert isinstance(variants, list)
    assert len(variants) == 3


def test_ab_test_variants_all_different(gen):
    variants = gen.ab_test_variants("tech", 5)
    unique = set(variants)
    assert len(unique) == len(variants)


def test_ab_test_variants_invalid_niche(gen):
    with pytest.raises(ValueError, match="Unsupported niche"):
        gen.ab_test_variants("invalid")
