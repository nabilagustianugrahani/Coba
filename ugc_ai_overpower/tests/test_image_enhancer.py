"""Tests for integrations/image_enhancer.py."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.image_enhancer import (
    ALLOWED_FIT_MODES,
    ALLOWED_FORMATS,
    ALLOWED_OPERATIONS,
    ALLOWED_POSITIONS,
    COST_PER_IMAGE_USD,
    EnhanceResult,
    ImageEnhancer,
)


def _run(coro):
    return asyncio.run(coro)


VALID_URL = "https://example.com/photo.png"


@pytest.fixture
def enhancer():
    return ImageEnhancer()


# ---------------------------------------------------------------------------
# EnhanceResult dataclass
# ---------------------------------------------------------------------------

def test_enhance_result_defaults():
    r = EnhanceResult(success=True)
    assert r.success is True
    assert r.output_url == ""
    assert r.operations_applied == []
    assert r.cost_usd == 0.0
    assert r.error == ""


def test_enhance_result_all_init_params():
    r = EnhanceResult(
        success=False,
        output_url="https://cdn.ugc.ai/x.png",
        operations_applied=["upscale", "sharpen"],
        cost_usd=0.0024,
        error="boom",
    )
    assert r.success is False
    assert r.output_url == "https://cdn.ugc.ai/x.png"
    assert r.operations_applied == ["upscale", "sharpen"]
    assert r.cost_usd == 0.0024
    assert r.error == "boom"


def test_enhance_result_to_dict():
    r = EnhanceResult(success=True, output_url="u", cost_usd=0.1)
    d = r.to_dict()
    assert d == {
        "success": True,
        "output_url": "u",
        "operations_applied": [],
        "cost_usd": 0.1,
        "error": "",
    }


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

def test_cost_per_image_constant():
    assert COST_PER_IMAGE_USD == 0.0008


def test_allowed_operations_constant():
    assert "upscale" in ALLOWED_OPERATIONS
    assert "face_enhance" in ALLOWED_OPERATIONS
    assert "auto_enhance" in ALLOWED_OPERATIONS


# ---------------------------------------------------------------------------
# upscale
# ---------------------------------------------------------------------------

def test_upscale_default_factor(enhancer):
    r = _run(enhancer.upscale(VALID_URL))
    assert r.success is True
    assert r.operations_applied == ["upscale"]
    assert r.cost_usd == COST_PER_IMAGE_USD


@pytest.mark.parametrize("factor", [2, 4, 8])
def test_upscale_valid_factors(enhancer, factor):
    r = _run(enhancer.upscale(VALID_URL, factor=factor))
    assert r.success is True
    assert r.cost_usd == COST_PER_IMAGE_USD


@pytest.mark.parametrize("factor", [3, 0, -1, 16, 1, 9])
def test_upscale_invalid_factors(enhancer, factor):
    r = _run(enhancer.upscale(VALID_URL, factor=factor))
    assert r.success is False
    assert r.cost_usd == 0.0
    assert "factor" in r.error


def test_upscale_invalid_url(enhancer):
    r = _run(enhancer.upscale("ftp://example.com/a.png"))
    assert r.success is False
    assert r.cost_usd == 0.0
    assert "scheme" in r.error.lower() or "Invalid" in r.error


def test_upscale_empty_url(enhancer):
    r = _run(enhancer.upscale(""))
    assert r.success is False
    assert r.cost_usd == 0.0


# ---------------------------------------------------------------------------
# remove_background
# ---------------------------------------------------------------------------

def test_remove_background_success(enhancer):
    r = _run(enhancer.remove_background(VALID_URL))
    assert r.success is True
    assert r.operations_applied == ["remove_background"]
    assert r.cost_usd == COST_PER_IMAGE_USD


def test_remove_background_invalid_url(enhancer):
    r = _run(enhancer.remove_background("ftp://nope/a.png"))
    assert r.success is False
    assert r.cost_usd == 0.0


def test_remove_background_empty_url(enhancer):
    r = _run(enhancer.remove_background("   "))
    assert r.success is False
    assert r.cost_usd == 0.0


# ---------------------------------------------------------------------------
# color_correct
# ---------------------------------------------------------------------------

def test_color_correct_defaults(enhancer):
    r = _run(enhancer.color_correct(VALID_URL))
    assert r.success is True
    assert r.operations_applied == ["color_correct"]
    assert r.cost_usd == COST_PER_IMAGE_USD


def test_color_correct_custom_params(enhancer):
    r = _run(enhancer.color_correct(VALID_URL, brightness=1.2, contrast=0.8, saturation=1.5))
    assert r.success is True
    assert r.cost_usd == COST_PER_IMAGE_USD


def test_color_correct_boundary_zero(enhancer):
    r = _run(enhancer.color_correct(VALID_URL, brightness=0.0))
    assert r.success is True


def test_color_correct_boundary_two(enhancer):
    r = _run(enhancer.color_correct(VALID_URL, brightness=2.0))
    assert r.success is True


def test_color_correct_brightness_below_range(enhancer):
    r = _run(enhancer.color_correct(VALID_URL, brightness=-0.1))
    assert r.success is False
    assert "brightness" in r.error


def test_color_correct_brightness_above_range(enhancer):
    r = _run(enhancer.color_correct(VALID_URL, brightness=2.1))
    assert r.success is False
    assert "brightness" in r.error


def test_color_correct_contrast_invalid(enhancer):
    r = _run(enhancer.color_correct(VALID_URL, contrast=3.0))
    assert r.success is False
    assert "contrast" in r.error


def test_color_correct_saturation_invalid(enhancer):
    r = _run(enhancer.color_correct(VALID_URL, saturation=-1.0))
    assert r.success is False
    assert "saturation" in r.error


def test_color_correct_invalid_url(enhancer):
    r = _run(enhancer.color_correct("ftp://x/a.png"))
    assert r.success is False
    assert r.cost_usd == 0.0


# ---------------------------------------------------------------------------
# denoise
# ---------------------------------------------------------------------------

def test_denoise_success(enhancer):
    r = _run(enhancer.denoise(VALID_URL))
    assert r.success is True
    assert r.operations_applied == ["denoise"]
    assert r.cost_usd == COST_PER_IMAGE_USD


def test_denoise_boundary_zero(enhancer):
    r = _run(enhancer.denoise(VALID_URL, strength=0.0))
    assert r.success is True


def test_denoise_boundary_one(enhancer):
    r = _run(enhancer.denoise(VALID_URL, strength=1.0))
    assert r.success is True


def test_denoise_below_range(enhancer):
    r = _run(enhancer.denoise(VALID_URL, strength=-0.1))
    assert r.success is False
    assert "strength" in r.error


def test_denoise_above_range(enhancer):
    r = _run(enhancer.denoise(VALID_URL, strength=1.1))
    assert r.success is False
    assert "strength" in r.error


def test_denoise_invalid_url(enhancer):
    r = _run(enhancer.denoise("not-a-url"))
    assert r.success is False
    assert r.cost_usd == 0.0


# ---------------------------------------------------------------------------
# sharpen
# ---------------------------------------------------------------------------

def test_sharpen_success(enhancer):
    r = _run(enhancer.sharpen(VALID_URL))
    assert r.success is True
    assert r.operations_applied == ["sharpen"]
    assert r.cost_usd == COST_PER_IMAGE_USD


def test_sharpen_boundary_zero(enhancer):
    r = _run(enhancer.sharpen(VALID_URL, amount=0.0))
    assert r.success is True


def test_sharpen_boundary_five(enhancer):
    r = _run(enhancer.sharpen(VALID_URL, amount=5.0))
    assert r.success is True


def test_sharpen_below_range(enhancer):
    r = _run(enhancer.sharpen(VALID_URL, amount=-1.0))
    assert r.success is False
    assert "amount" in r.error


def test_sharpen_above_range(enhancer):
    r = _run(enhancer.sharpen(VALID_URL, amount=5.1))
    assert r.success is False
    assert "amount" in r.error


def test_sharpen_invalid_url(enhancer):
    r = _run(enhancer.sharpen("ftp://x/y.png"))
    assert r.success is False


# ---------------------------------------------------------------------------
# face_enhance
# ---------------------------------------------------------------------------

def test_face_enhance_success(enhancer):
    r = _run(enhancer.face_enhance(VALID_URL))
    assert r.success is True
    assert r.operations_applied == ["face_enhance"]
    assert r.cost_usd == COST_PER_IMAGE_USD


def test_face_enhance_invalid_url(enhancer):
    r = _run(enhancer.face_enhance("file:///etc/passwd"))
    assert r.success is False
    assert r.cost_usd == 0.0


# ---------------------------------------------------------------------------
# auto_enhance
# ---------------------------------------------------------------------------

def test_auto_enhance_success(enhancer):
    r = _run(enhancer.auto_enhance(VALID_URL))
    assert r.success is True


def test_auto_enhance_all_five_ops(enhancer):
    r = _run(enhancer.auto_enhance(VALID_URL))
    assert r.operations_applied == [
        "upscale", "color_correct", "denoise", "sharpen", "face_enhance"
    ]
    assert len(r.operations_applied) == 5


def test_auto_enhance_cost_is_five_times(enhancer):
    r = _run(enhancer.auto_enhance(VALID_URL))
    assert r.cost_usd == 5 * COST_PER_IMAGE_USD


def test_auto_enhance_invalid_url(enhancer):
    r = _run(enhancer.auto_enhance("ftp://nope/a.png"))
    assert r.success is False
    assert r.cost_usd == 0.0


# ---------------------------------------------------------------------------
# resize
# ---------------------------------------------------------------------------

def test_resize_success(enhancer):
    r = _run(enhancer.resize(VALID_URL, 800, 600))
    assert r.success is True
    assert r.operations_applied == ["resize"]
    assert r.cost_usd == COST_PER_IMAGE_USD


@pytest.mark.parametrize("fit", ["cover", "contain", "fill", "inside", "outside"])
def test_resize_all_fit_modes(enhancer, fit):
    r = _run(enhancer.resize(VALID_URL, 100, 100, fit=fit))
    assert r.success is True


def test_resize_width_zero_invalid(enhancer):
    r = _run(enhancer.resize(VALID_URL, 0, 100))
    assert r.success is False
    assert r.cost_usd == 0.0


def test_resize_height_negative_invalid(enhancer):
    r = _run(enhancer.resize(VALID_URL, 100, -1))
    assert r.success is False
    assert r.cost_usd == 0.0


def test_resize_invalid_fit(enhancer):
    r = _run(enhancer.resize(VALID_URL, 100, 100, fit="diagonal"))
    assert r.success is False
    assert "fit" in r.error


def test_resize_invalid_url(enhancer):
    r = _run(enhancer.resize("ftp://x/y.png", 100, 100))
    assert r.success is False


# ---------------------------------------------------------------------------
# convert_format
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt", ["webp", "png", "jpg", "jpeg", "gif", "bmp", "tiff"])
def test_convert_format_valid(enhancer, fmt):
    r = _run(enhancer.convert_format(VALID_URL, target_format=fmt))
    assert r.success is True
    assert r.operations_applied == ["convert_format"]


def test_convert_format_leading_dot(enhancer):
    r = _run(enhancer.convert_format(VALID_URL, target_format=".webp"))
    assert r.success is True


def test_convert_format_uppercase_normalized(enhancer):
    r = _run(enhancer.convert_format(VALID_URL, target_format="WEBP"))
    assert r.success is True


def test_convert_format_invalid_format(enhancer):
    r = _run(enhancer.convert_format(VALID_URL, target_format="xyz"))
    assert r.success is False
    assert "target_format" in r.error


def test_convert_format_invalid_url(enhancer):
    r = _run(enhancer.convert_format("ftp://x/a.png"))
    assert r.success is False


# ---------------------------------------------------------------------------
# add_overlay
# ---------------------------------------------------------------------------

def test_add_overlay_success(enhancer):
    r = _run(enhancer.add_overlay(VALID_URL, "Hello World"))
    assert r.success is True
    assert r.operations_applied == ["add_overlay"]
    assert r.cost_usd == COST_PER_IMAGE_USD


@pytest.mark.parametrize(
    "position",
    ["top", "bottom", "center", "top-left", "top-right", "bottom-left", "bottom-right"],
)
def test_add_overlay_all_positions(enhancer, position):
    r = _run(enhancer.add_overlay(VALID_URL, "Hi", position=position))
    assert r.success is True


def test_add_overlay_default_font(enhancer):
    r = _run(enhancer.add_overlay(VALID_URL, "Hi"))
    assert r.success is True


def test_add_overlay_font_size_one(enhancer):
    r = _run(enhancer.add_overlay(VALID_URL, "Hi", font_size=1))
    assert r.success is True


def test_add_overlay_font_size_max(enhancer):
    r = _run(enhancer.add_overlay(VALID_URL, "Hi", font_size=500))
    assert r.success is True


def test_add_overlay_empty_text(enhancer):
    r = _run(enhancer.add_overlay(VALID_URL, ""))
    assert r.success is False
    assert r.cost_usd == 0.0


def test_add_overlay_whitespace_text(enhancer):
    r = _run(enhancer.add_overlay(VALID_URL, "   "))
    assert r.success is False
    assert r.cost_usd == 0.0


def test_add_overlay_invalid_position(enhancer):
    r = _run(enhancer.add_overlay(VALID_URL, "Hi", position="middle"))
    assert r.success is False
    assert "position" in r.error


def test_add_overlay_font_size_zero(enhancer):
    r = _run(enhancer.add_overlay(VALID_URL, "Hi", font_size=0))
    assert r.success is False
    assert r.cost_usd == 0.0


def test_add_overlay_font_size_too_large(enhancer):
    r = _run(enhancer.add_overlay(VALID_URL, "Hi", font_size=501))
    assert r.success is False
    assert r.cost_usd == 0.0


def test_add_overlay_invalid_url(enhancer):
    r = _run(enhancer.add_overlay("ftp://x/a.png", "Hi"))
    assert r.success is False


# ---------------------------------------------------------------------------
# total_cost_usd / reset_cost
# ---------------------------------------------------------------------------

def test_total_cost_starts_at_zero(enhancer):
    assert enhancer.total_cost_usd == 0.0


def test_total_cost_accumulates(enhancer):
    _run(enhancer.upscale(VALID_URL))
    _run(enhancer.denoise(VALID_URL))
    _run(enhancer.sharpen(VALID_URL))
    assert enhancer.total_cost_usd == pytest.approx(3 * COST_PER_IMAGE_USD)


def test_total_cost_failed_does_not_charge(enhancer):
    _run(enhancer.upscale("ftp://nope"))  # failure
    _run(enhancer.upscale(VALID_URL))     # success
    assert enhancer.total_cost_usd == COST_PER_IMAGE_USD


def test_reset_cost_clears(enhancer):
    _run(enhancer.upscale(VALID_URL))
    _run(enhancer.sharpen(VALID_URL))
    assert enhancer.total_cost_usd > 0
    enhancer.reset_cost()
    assert enhancer.total_cost_usd == 0.0


def test_reset_cost_clears_processed_list(enhancer):
    _run(enhancer.upscale(VALID_URL))
    assert len(enhancer._processed) == 1
    enhancer.reset_cost()
    assert enhancer._processed == []


# ---------------------------------------------------------------------------
# Output URL
# ---------------------------------------------------------------------------

def test_output_url_contains_cdn_prefix(enhancer):
    r = _run(enhancer.upscale(VALID_URL))
    assert r.output_url.startswith("https://cdn.ugc.ai/processed/")


def test_output_url_preserves_png_extension(enhancer):
    r = _run(enhancer.upscale("https://example.com/cat.png"))
    assert r.output_url.endswith(".png")


def test_output_url_preserves_webp_extension(enhancer):
    r = _run(enhancer.sharpen("https://example.com/cat.webp"))
    assert r.output_url.endswith(".webp")


def test_output_url_defaults_to_jpg_when_no_extension(enhancer):
    r = _run(enhancer.upscale("https://example.com/image"))
    assert r.output_url.endswith(".jpg")


def test_output_url_deterministic_same_inputs(enhancer):
    a = _run(enhancer.upscale(VALID_URL, factor=4))
    b = _run(enhancer.upscale(VALID_URL, factor=4))
    assert a.output_url == b.output_url


def test_output_url_changes_with_params(enhancer):
    a = _run(enhancer.upscale(VALID_URL, factor=2))
    b = _run(enhancer.upscale(VALID_URL, factor=4))
    assert a.output_url != b.output_url


# ---------------------------------------------------------------------------
# Failure mode shape
# ---------------------------------------------------------------------------

def test_failure_result_shape(enhancer):
    r = _run(enhancer.upscale(""))
    assert r.success is False
    assert r.error != ""
    assert r.cost_usd == 0.0
    assert r.output_url == ""
    assert r.operations_applied == []


# ---------------------------------------------------------------------------
# Integration: pipeline + cost tracking
# ---------------------------------------------------------------------------

def test_pipeline_cost_tracking(enhancer):
    r1 = _run(enhancer.upscale(VALID_URL, factor=4))
    r2 = _run(enhancer.color_correct(VALID_URL, brightness=1.1, contrast=1.1))
    r3 = _run(enhancer.face_enhance(VALID_URL))

    assert r1.success and r2.success and r3.success
    assert r1.cost_usd == COST_PER_IMAGE_USD
    assert r2.cost_usd == COST_PER_IMAGE_USD
    assert r3.cost_usd == COST_PER_IMAGE_USD
    assert enhancer.total_cost_usd == pytest.approx(3 * COST_PER_IMAGE_USD)


def test_pipeline_auto_enhance_then_overlay(enhancer):
    r1 = _run(enhancer.auto_enhance(VALID_URL))
    r2 = _run(enhancer.add_overlay(VALID_URL, "Sale!", position="top", font_size=72))

    assert r1.success
    assert r2.success
    assert r1.cost_usd == 5 * COST_PER_IMAGE_USD
    assert r2.cost_usd == COST_PER_IMAGE_USD
    assert enhancer.total_cost_usd == pytest.approx(6 * COST_PER_IMAGE_USD)


def test_pipeline_independent_enhancers_have_separate_costs():
    a = ImageEnhancer()
    b = ImageEnhancer()
    _run(a.upscale(VALID_URL))
    _run(a.sharpen(VALID_URL))
    _run(b.face_enhance(VALID_URL))
    assert a.total_cost_usd == 2 * COST_PER_IMAGE_USD
    assert b.total_cost_usd == COST_PER_IMAGE_USD
