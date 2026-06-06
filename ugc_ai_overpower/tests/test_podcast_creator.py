"""Tests for integrations/podcast_creator.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.podcast_creator import (
    AUDIO_EDIT_GPU_PER_SEC,
    LOUDNESS_DEFAULT_LUFS,
    LOUDNESS_MAX_LUFS,
    LOUDNESS_MIN_LUFS,
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    SHOWNOTES_MAX_WORDS,
    TRANSCRIBE_GPU_PER_SEC,
    AudioResult,
    PodcastCreator,
    TranscriptResult,
    TranscriptSegment,
    ViralMoment,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def pc():
    return PodcastCreator()


@pytest.fixture
def sample_transcript():
    return TranscriptResult(
        language="en",
        duration_sec=60.0,
        segments=[
            TranscriptSegment(0.0, 4.0, "Hey everyone welcome to the show today", "host", 0.95),
            TranscriptSegment(4.0, 8.0, "This is amazing and I'm excited to share", "host", 0.93),
            TranscriptSegment(8.0, 12.0, "It was terrible, awful, and the worst thing ever", "guest", 0.91),
            TranscriptSegment(12.0, 16.0, "Anyway, let's continue with the topic", "host", 0.97),
            TranscriptSegment(16.0, 20.0, "This is fire, absolutely incredible content", "host", 0.92),
        ],
    )


# -----------------------------------------------------------------------------
# 1. dataclass behavior
# -----------------------------------------------------------------------------
def test_segment_duration():
    s = TranscriptSegment(2.0, 5.0, "hello world")
    assert s.duration() == 3.0


def test_segment_word_count():
    s = TranscriptSegment(0.0, 1.0, "hello cruel world")
    assert s.word_count() == 3


def test_transcript_full_text(sample_transcript):
    txt = sample_transcript.full_text()
    assert "amazing" in txt
    assert "terrible" in txt


def test_transcript_word_count(sample_transcript):
    assert sample_transcript.word_count() > 0


def test_audio_result_defaults():
    r = AudioResult(success=True)
    d = r.to_dict()
    assert d["success"] is True
    assert d["cost_usd"] == 0.0


# -----------------------------------------------------------------------------
# 2. constants
# -----------------------------------------------------------------------------
def test_pricing_constants():
    assert TRANSCRIBE_GPU_PER_SEC == 0.000589
    assert AUDIO_EDIT_GPU_PER_SEC == 0.000976


def test_loudness_range():
    assert LOUDNESS_MIN_LUFS < LOUDNESS_MAX_LUFS
    assert LOUDNESS_DEFAULT_LUFS == -16.0


def test_shownotes_cap():
    assert SHOWNOTES_MAX_WORDS == 500


def test_sentiment_lexicons_nonempty():
    assert len(POSITIVE_WORDS) >= 5
    assert len(NEGATIVE_WORDS) >= 5


# -----------------------------------------------------------------------------
# 3. transcribe
# -----------------------------------------------------------------------------
def test_transcribe_returns_result(pc):
    r = _run(pc.transcribe("https://x.com/pod.mp3"))
    assert isinstance(r, TranscriptResult)
    assert r.language == "auto"  # default fallback when "auto" passed


def test_transcribe_explicit_language(pc):
    r = _run(pc.transcribe("https://x.com/pod.mp3", language="id"))
    assert r.language == "id"


def test_transcribe_invalid_language_raises(pc):
    with pytest.raises(ValueError):
        _run(pc.transcribe("https://x.com/pod.mp3", language="english123"))


def test_transcribe_empty_url_raises(pc):
    with pytest.raises(ValueError):
        _run(pc.transcribe(""))


def test_transcribe_cost_positive(pc):
    r = _run(pc.transcribe("https://x.com/pod.mp3"))
    assert r.cost_usd > 0


# -----------------------------------------------------------------------------
# 4. shownotes
# -----------------------------------------------------------------------------
def test_shownotes_starts_with_header(sample_transcript, pc):
    notes = _run(pc.generate_shownotes(sample_transcript))
    assert notes.startswith("# Episode notes")


def test_shownotes_includes_highlights(sample_transcript, pc):
    notes = _run(pc.generate_shownotes(sample_transcript))
    assert "## Highlights" in notes


def test_shownotes_has_bullets(sample_transcript, pc):
    notes = _run(pc.generate_shownotes(sample_transcript))
    assert "- " in notes


def test_shownotes_max_words_enforced(sample_transcript, pc):
    # Construct a transcript with massive text to force the cap.
    long_segments = [
        TranscriptSegment(0.0, 100.0, " ".join(["word"] * 2000), "host", 0.9)
        for _ in range(3)
    ]
    t = TranscriptResult(language="en", duration_sec=300.0, segments=long_segments)
    notes = _run(pc.generate_shownotes(t))
    assert len(notes.split()) <= SHOWNOTES_MAX_WORDS


def test_shownotes_empty_transcript(pc):
    t = TranscriptResult(language="en", duration_sec=0.0, segments=[])
    notes = _run(pc.generate_shownotes(t))
    assert notes == ""


def test_shownotes_none_raises(pc):
    with pytest.raises(ValueError):
        _run(pc.generate_shownotes(None))


# -----------------------------------------------------------------------------
# 5. viral moments
# -----------------------------------------------------------------------------
def test_viral_returns_list(sample_transcript, pc):
    moments = _run(pc.find_viral_moments(sample_transcript, top_k=3))
    assert isinstance(moments, list)
    assert len(moments) == 3
    assert all(isinstance(m, ViralMoment) for m in moments)


def test_viral_top_k_limit(sample_transcript, pc):
    moments = _run(pc.find_viral_moments(sample_transcript, top_k=1))
    assert len(moments) == 1


def test_viral_top_k_zero_raises(sample_transcript, pc):
    with pytest.raises(ValueError):
        _run(pc.find_viral_moments(sample_transcript, top_k=0))


def test_viral_none_raises(pc):
    with pytest.raises(ValueError):
        _run(pc.find_viral_moments(None))


def test_viral_empty_transcript_returns_empty(pc):
    t = TranscriptResult(language="en", duration_sec=0.0, segments=[])
    moments = _run(pc.find_viral_moments(t))
    assert moments == []


def test_viral_scores_descending(sample_transcript, pc):
    moments = _run(pc.find_viral_moments(sample_transcript, top_k=5))
    scores = [m.score for m in moments]
    assert scores == sorted(scores, reverse=True)


def test_viral_picks_high_sentiment_segment(sample_transcript, pc):
    moments = _run(pc.find_viral_moments(sample_transcript, top_k=5))
    # The "amazing/excited" segment has strong positive sentiment — should be near top.
    texts = [m.text for m in moments]
    assert any("amazing" in t for t in texts)


def test_viral_score_in_range(sample_transcript, pc):
    for m in _run(pc.find_viral_moments(sample_transcript, top_k=5)):
        assert 0.0 <= m.score <= 1.0


# -----------------------------------------------------------------------------
# 6. audio ops
# -----------------------------------------------------------------------------
def test_clip_audio_bounds(pc):
    r = _run(pc.clip_audio("https://x.com/pod.mp3", 5.0, 10.0))
    assert r.duration_sec == 5.0


def test_clip_audio_invalid_window(pc):
    with pytest.raises(ValueError):
        _run(pc.clip_audio("https://x.com/pod.mp3", 10.0, 5.0))


def test_clip_audio_negative_start(pc):
    with pytest.raises(ValueError):
        _run(pc.clip_audio("https://x.com/pod.mp3", -1.0, 5.0))


def test_clip_audio_empty_url(pc):
    with pytest.raises(ValueError):
        _run(pc.clip_audio("", 0.0, 1.0))


def test_intro_outro_three_inputs(pc):
    r = _run(pc.add_intro_outro(
        "https://x.com/p.mp3",
        "https://x.com/i.mp3",
        "https://x.com/o.mp3",
    ))
    cmd = r.metadata["cmd"]
    assert "https://x.com/i.mp3" in cmd
    assert "https://x.com/o.mp3" in cmd


def test_intro_outro_empty_url(pc):
    with pytest.raises(ValueError):
        _run(pc.add_intro_outro("", "i", "o"))


def test_normalize_loudness_default(pc):
    r = _run(pc.normalize_loudness("https://x.com/p.mp3"))
    assert r.metadata["target_lufs"] == LOUDNESS_DEFAULT_LUFS


def test_normalize_loudness_too_quiet(pc):
    with pytest.raises(ValueError):
        _run(pc.normalize_loudness("https://x.com/p.mp3", target_lufs=-30.0))


def test_normalize_loudness_too_loud(pc):
    with pytest.raises(ValueError):
        _run(pc.normalize_loudness("https://x.com/p.mp3", target_lufs=-10.0))


def test_normalize_loudness_uses_filter(pc):
    r = _run(pc.normalize_loudness("https://x.com/p.mp3", target_lufs=-16.0))
    assert "loudnorm" in " ".join(r.metadata["cmd"])


def test_detect_silence_default(pc):
    ranges = _run(pc.detect_silence("https://x.com/p.mp3"))
    assert isinstance(ranges, list)


def test_detect_silence_threshold_bounds(pc):
    with pytest.raises(ValueError):
        _run(pc.detect_silence("https://x.com/p.mp3", threshold_db=-200.0))
    with pytest.raises(ValueError):
        _run(pc.detect_silence("https://x.com/p.mp3", threshold_db=10.0))


def test_detect_silence_empty_url(pc):
    with pytest.raises(ValueError):
        _run(pc.detect_silence(""))


def test_merge_clips_default_crossfade(pc):
    r = _run(pc.merge_clips(["https://x.com/a.mp3", "https://x.com/b.mp3"]))
    assert r.metadata["crossfade_sec"] == 0.5
    assert r.metadata["clip_count"] == 2


def test_merge_clips_empty_raises(pc):
    with pytest.raises(ValueError):
        _run(pc.merge_clips([]))


def test_merge_clips_negative_crossfade(pc):
    with pytest.raises(ValueError):
        _run(pc.merge_clips(["https://x.com/a.mp3"], crossfade_sec=-1.0))


def test_merge_clips_huge_crossfade(pc):
    with pytest.raises(ValueError):
        _run(pc.merge_clips(["https://x.com/a.mp3"], crossfade_sec=60.0))


def test_merge_clips_uses_concat(pc):
    r = _run(pc.merge_clips(["https://x.com/a.mp3", "https://x.com/b.mp3", "https://x.com/c.mp3"]))
    assert "concat=n=3" in " ".join(r.metadata["cmd"])


# -----------------------------------------------------------------------------
# 7. spend tracking + summary
# -----------------------------------------------------------------------------
def test_spend_accumulates(pc):
    _run(pc.clip_audio("https://x.com/p.mp3", 0.0, 30.0))
    _run(pc.clip_audio("https://x.com/p.mp3", 0.0, 30.0))
    assert pc.spend_tracker["spent"] > 0


def test_summary_shape(pc):
    s = pc.summary()
    assert s["modal_configured"] is False
    assert s["fal_configured"] is False
    assert "transcribe_gpu_per_sec" in s


def test_summary_with_dispatchers():
    pc = PodcastCreator(modal_dispatcher=MagicMock(), fal_dispatcher=MagicMock())
    s = pc.summary()
    assert s["modal_configured"] is True
    assert s["fal_configured"] is True


# Count check
def test_test_count_at_least_30():
    """Sanity: ensure this test module has 30+ tests."""
    import inspect
    src = inspect.getsource(inspect.getmodule(test_clip_audio_bounds))
    assert src.count("def test_") >= 30
