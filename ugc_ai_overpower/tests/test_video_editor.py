"""Tests for integrations/video_editor.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.video_editor import (
    ALLOWED_CAPTION_FONTS,
    ALLOWED_TRANSITIONS,
    ASPECT_SQUARE,
    ASPECT_VERTICAL,
    FFMPEG_GPU_PER_SEC,
    MAX_DURATION_SEC,
    MIN_DURATION_SEC,
    WATERMARK_POSITIONS,
    VideoEditResult,
    VideoEditor,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def editor():
    return VideoEditor()


@pytest.fixture
def mock_dispatcher():
    d = MagicMock()
    d.spend_tracker = {"spent": 0.0}
    return d


# -----------------------------------------------------------------------------
# 1. result + constants
# -----------------------------------------------------------------------------
def test_result_defaults():
    r = VideoEditResult(success=True)
    assert r.success is True
    assert r.output_url == ""
    assert r.cost_usd == 0.0
    assert r.metadata == {}
    assert r.error == ""


def test_result_to_dict():
    r = VideoEditResult(success=True, cost_usd=0.01, duration_sec=4.0)
    d = r.to_dict()
    assert d["success"] is True
    assert d["cost_usd"] == 0.01
    assert d["duration_sec"] == 4.0
    assert isinstance(d["metadata"], dict)


def test_gpu_price_constant():
    assert FFMPEG_GPU_PER_SEC == 0.000976


def test_watermark_positions_count():
    assert len(WATERMARK_POSITIONS) == 5
    for p in ("top-left", "top-right", "bottom-left", "bottom-right", "center"):
        assert p in WATERMARK_POSITIONS


def test_caption_fonts_nonempty():
    assert "Arial" in ALLOWED_CAPTION_FONTS
    assert len(ALLOWED_CAPTION_FONTS) >= 5


def test_transitions_include_fade():
    assert "none" in ALLOWED_TRANSITIONS
    assert "fade" in ALLOWED_TRANSITIONS


def test_aspect_constants():
    assert ASPECT_VERTICAL == (1080, 1920)
    assert ASPECT_SQUARE == (1080, 1080)


# -----------------------------------------------------------------------------
# 2. trim
# -----------------------------------------------------------------------------
def test_trim_returns_result(editor):
    r = _run(editor.trim("https://x.com/v.mp4", 0.0, 5.0))
    assert isinstance(r, VideoEditResult)
    assert r.success is True
    assert r.duration_sec == 5.0


def test_trim_contains_ffmpeg(editor):
    r = _run(editor.trim("https://x.com/v.mp4", 1.0, 4.0))
    assert r.metadata["cmd"][0] == "ffmpeg"
    assert "-ss" in r.metadata["cmd"]


def test_trim_empty_url_raises(editor):
    with pytest.raises(ValueError):
        _run(editor.trim("", 0.0, 1.0))


def test_trim_negative_start_raises(editor):
    with pytest.raises(ValueError):
        _run(editor.trim("https://x.com/v.mp4", -1.0, 5.0))


def test_trim_end_before_start_raises(editor):
    with pytest.raises(ValueError):
        _run(editor.trim("https://x.com/v.mp4", 5.0, 2.0))


def test_trim_too_short_raises(editor):
    with pytest.raises(ValueError):
        _run(editor.trim("https://x.com/v.mp4", 0.0, 0.05))


def test_trim_too_long_raises(editor):
    with pytest.raises(ValueError):
        _run(editor.trim("https://x.com/v.mp4", 0.0, MAX_DURATION_SEC + 1))


def test_trim_cost_matches_duration(editor):
    r = _run(editor.trim("https://x.com/v.mp4", 0.0, 10.0))
    assert r.cost_usd == round(10.0 * FFMPEG_GPU_PER_SEC, 6)


# -----------------------------------------------------------------------------
# 3. concat
# -----------------------------------------------------------------------------
def test_concat_preserves_order(editor):
    urls = ["https://x.com/a.mp4", "https://x.com/b.mp4", "https://x.com/c.mp4"]
    r = _run(editor.concat(urls))
    assert r.metadata["clip_count"] == 3
    cmd = r.metadata["cmd"]
    assert urls[0] in cmd and urls[1] in cmd and urls[2] in cmd


def test_concat_empty_raises(editor):
    with pytest.raises(ValueError):
        _run(editor.concat([]))


def test_concat_bad_transition_raises(editor):
    with pytest.raises(ValueError):
        _run(editor.concat(["https://x.com/a.mp4"], transition="zoop"))


def test_concat_records_spend(editor):
    _run(editor.concat(["https://x.com/a.mp4", "https://x.com/b.mp4"]))
    assert editor.spend_tracker["spent"] > 0


# -----------------------------------------------------------------------------
# 4. captions
# -----------------------------------------------------------------------------
def test_captions_valid_font(editor):
    r = _run(editor.add_captions("https://x.com/v.mp4", "https://x.com/s.srt", "Arial"))
    assert r.success
    assert r.metadata["font"] == "Arial"


def test_captions_invalid_font(editor):
    with pytest.raises(ValueError):
        _run(editor.add_captions("https://x.com/v.mp4", "https://x.com/s.srt", "ComicPapyrus"))


def test_captions_empty_srt(editor):
    with pytest.raises(ValueError):
        _run(editor.add_captions("https://x.com/v.mp4", "", "Arial"))


# -----------------------------------------------------------------------------
# 5. watermark
# -----------------------------------------------------------------------------
def test_watermark_each_position(editor):
    for pos in WATERMARK_POSITIONS:
        r = _run(editor.add_watermark("https://x.com/v.mp4", "https://x.com/wm.png", pos))
        assert r.metadata["position"] == pos


def test_watermark_invalid_position(editor):
    with pytest.raises(ValueError):
        _run(editor.add_watermark("https://x.com/v.mp4", "https://x.com/wm.png", "nowhere"))


def test_watermark_empty_url(editor):
    with pytest.raises(ValueError):
        _run(editor.add_watermark("", "https://x.com/wm.png"))


def test_watermark_cmd_contains_overlay(editor):
    r = _run(editor.add_watermark("https://x.com/v.mp4", "https://x.com/wm.png", "center"))
    assert "overlay" in " ".join(r.metadata["cmd"])


# -----------------------------------------------------------------------------
# 6. bgm
# -----------------------------------------------------------------------------
def test_bgm_default_volume(editor):
    r = _run(editor.add_bgm("https://x.com/v.mp4", "https://x.com/a.mp3"))
    assert r.metadata["volume_db"] == -12.0


def test_bgm_valid_volume(editor):
    r = _run(editor.add_bgm("https://x.com/v.mp4", "https://x.com/a.mp3", -6.0))
    assert r.metadata["volume_db"] == -6.0


def test_bgm_volume_too_loud(editor):
    with pytest.raises(ValueError):
        _run(editor.add_bgm("https://x.com/v.mp4", "https://x.com/a.mp3", 12.0))


def test_bgm_volume_too_quiet(editor):
    with pytest.raises(ValueError):
        _run(editor.add_bgm("https://x.com/v.mp4", "https://x.com/a.mp3", -80.0))


def test_bgm_uses_amix(editor):
    r = _run(editor.add_bgm("https://x.com/v.mp4", "https://x.com/a.mp3"))
    assert "amix" in " ".join(r.metadata["cmd"])


# -----------------------------------------------------------------------------
# 7. thumbnail
# -----------------------------------------------------------------------------
def test_thumbnail_default_width(editor):
    r = _run(editor.extract_thumbnail("https://x.com/v.mp4", 2.0))
    assert r.metadata["width"] == 720


def test_thumbnail_negative_time(editor):
    with pytest.raises(ValueError):
        _run(editor.extract_thumbnail("https://x.com/v.mp4", -1.0))


def test_thumbnail_width_bounds(editor):
    with pytest.raises(ValueError):
        _run(editor.extract_thumbnail("https://x.com/v.mp4", 1.0, width=2))


def test_thumbnail_cmd_uses_scale(editor):
    r = _run(editor.extract_thumbnail("https://x.com/v.mp4", 1.0, width=480))
    assert "scale=480" in " ".join(r.metadata["cmd"])


# -----------------------------------------------------------------------------
# 8. compress
# -----------------------------------------------------------------------------
def test_compress_default_target(editor):
    r = _run(editor.compress("https://x.com/v.mp4"))
    assert r.metadata["target_mb"] == 5.0


def test_compress_zero_target_raises(editor):
    with pytest.raises(ValueError):
        _run(editor.compress("https://x.com/v.mp4", target_mb=0.0))


def test_compress_huge_target_raises(editor):
    with pytest.raises(ValueError):
        _run(editor.compress("https://x.com/v.mp4", target_mb=1000.0))


def test_compress_uses_libx264(editor):
    r = _run(editor.compress("https://x.com/v.mp4", target_mb=3.0))
    assert "libx264" in r.metadata["cmd"]


# -----------------------------------------------------------------------------
# 9. resize
# -----------------------------------------------------------------------------
def test_resize_normal(editor):
    r = _run(editor.resize("https://x.com/v.mp4", 1280, 720))
    assert r.metadata["width"] == 1280
    assert r.metadata["height"] == 720


def test_resize_width_too_small(editor):
    with pytest.raises(ValueError):
        _run(editor.resize("https://x.com/v.mp4", 4, 720))


def test_resize_height_too_large(editor):
    with pytest.raises(ValueError):
        _run(editor.resize("https://x.com/v.mp4", 1280, 99999))


# -----------------------------------------------------------------------------
# 10. vertical / square
# -----------------------------------------------------------------------------
def test_to_vertical_dimensions(editor):
    r = _run(editor.to_vertical("https://x.com/v.mp4"))
    assert r.metadata["width"] == 1080
    assert r.metadata["height"] == 1920


def test_to_square_dimensions(editor):
    r = _run(editor.to_square("https://x.com/v.mp4"))
    assert r.metadata["width"] == 1080
    assert r.metadata["height"] == 1080


def test_to_vertical_empty_url(editor):
    with pytest.raises(ValueError):
        _run(editor.to_vertical(""))


def test_to_square_uses_pad(editor):
    r = _run(editor.to_square("https://x.com/v.mp4"))
    assert "pad=" in " ".join(r.metadata["cmd"])


# -----------------------------------------------------------------------------
# 11. extract_audio + intro_outro
# -----------------------------------------------------------------------------
def test_extract_audio_uses_mp3(editor):
    r = _run(editor.extract_audio("https://x.com/v.mp4"))
    assert "libmp3lame" in r.metadata["cmd"]


def test_extract_audio_empty_url(editor):
    with pytest.raises(ValueError):
        _run(editor.extract_audio(""))


def test_intro_outro_three_inputs(editor):
    r = _run(editor.add_intro_outro(
        "https://x.com/v.mp4",
        "https://x.com/i.mp4",
        "https://x.com/o.mp4",
    ))
    cmd = r.metadata["cmd"]
    assert "https://x.com/i.mp4" in cmd
    assert "https://x.com/v.mp4" in cmd
    assert "https://x.com/o.mp4" in cmd


def test_intro_outro_uses_concat(editor):
    r = _run(editor.add_intro_outro(
        "https://x.com/v.mp4",
        "https://x.com/i.mp4",
        "https://x.com/o.mp4",
    ))
    assert "concat=n=3" in " ".join(r.metadata["cmd"])


# -----------------------------------------------------------------------------
# 12. spend tracking + summary
# -----------------------------------------------------------------------------
def test_spend_tracks_across_ops(editor):
    _run(editor.trim("https://x.com/v.mp4", 0.0, 4.0))
    _run(editor.trim("https://x.com/v.mp4", 0.0, 6.0))
    expected = (4.0 + 6.0) * FFMPEG_GPU_PER_SEC
    assert editor.spend_tracker["spent"] == round(expected, 6)


def test_summary_shape(editor):
    s = editor.summary()
    assert s["operations"] == 13
    assert s["modal_configured"] is False
    assert s["spent_usd"] == 0.0


def test_summary_with_dispatcher(mock_dispatcher):
    e = VideoEditor(modal_dispatcher=mock_dispatcher)
    assert e.summary()["modal_configured"] is True


def test_min_max_duration_constants():
    assert MIN_DURATION_SEC > 0
    assert MAX_DURATION_SEC > MIN_DURATION_SEC


# -----------------------------------------------------------------------------
# 13. edge cases
# -----------------------------------------------------------------------------
def test_all_ops_return_video_edit_result(editor):
    ops = [
        editor.trim("https://x.com/v.mp4", 0.0, 2.0),
        editor.concat(["https://x.com/a.mp4"]),
        editor.add_captions("https://x.com/v.mp4", "https://x.com/s.srt"),
        editor.add_watermark("https://x.com/v.mp4", "https://x.com/wm.png"),
        editor.add_bgm("https://x.com/v.mp4", "https://x.com/a.mp3"),
        editor.extract_thumbnail("https://x.com/v.mp4", 1.0),
        editor.compress("https://x.com/v.mp4"),
        editor.resize("https://x.com/v.mp4", 640, 360),
        editor.to_vertical("https://x.com/v.mp4"),
        editor.to_square("https://x.com/v.mp4"),
        editor.extract_audio("https://x.com/v.mp4"),
        editor.add_intro_outro("https://x.com/v.mp4", "https://x.com/i.mp4", "https://x.com/o.mp4"),
    ]
    for r in [_run(op) for op in ops]:
        assert isinstance(r, VideoEditResult)
        assert r.success
        assert r.cost_usd > 0


def test_trim_op_name_in_metadata(editor):
    r = _run(editor.trim("https://x.com/v.mp4", 0.0, 1.0))
    assert r.metadata["op"] == "trim"


def test_concat_op_records_all_urls_in_order(editor):
    urls = [f"https://x.com/{i}.mp4" for i in range(4)]
    r = _run(editor.concat(urls))
    cmd = r.metadata["cmd"]
    last_seen = -1
    for u in urls:
        idx = cmd.index(u)
        assert idx > last_seen
        last_seen = idx


# Count check
def test_test_count_at_least_35():
    """Local sanity: ensure test module has 35+ tests."""
    import inspect
    src = inspect.getsource(inspect.getmodule(test_trim_returns_result))
    assert src.count("def test_") >= 35
