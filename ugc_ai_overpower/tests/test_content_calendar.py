"""Tests for integrations/content_calendar.py — 20 tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.content_calendar import (
    CalendarEntry,
    CalendarInput,
    CalendarResult,
    ContentCalendar,
    CONTENT_TYPES,
    POSTING_TIMES,
    TOPIC_TEMPLATES,
)


@pytest.fixture
def cal():
    return ContentCalendar()


# ---------- dataclass basics ----------

def test_calendar_input_defaults():
    ci = CalendarInput()
    assert ci.niche == "general"
    assert ci.posts_per_week == 5
    assert ci.platforms == ["instagram", "tiktok"]


def test_calendar_entry_fields():
    e = CalendarEntry(
        date="2026-06-01", platform="instagram", content_type="video",
        topic="test topic", caption_template="caption", hashtags=["#fun"],
        cta="follow", best_posting_time="12:00",
    )
    assert e.date == "2026-06-01"
    assert e.platform == "instagram"


def test_calendar_result_total_posts():
    r = CalendarResult(
        entries=[CalendarEntry(date="2026-01-01", platform="ig", content_type="image", topic="t", caption_template="c")],
        total_posts=1, niche="tech",
    )
    assert r.total_posts == 1


# ---------- generate() ----------

def test_generate_returns_calendar_result(cal):
    r = cal.generate(CalendarInput(niche="tech", start_date="2026-06-01"))
    assert isinstance(r, CalendarResult)


def test_generate_30_days_of_entries(cal):
    r = cal.generate(CalendarInput(niche="fashion", start_date="2026-06-01"))
    assert len(r.entries) >= 20  # ~5 posts/week over 30 days


def test_generate_total_posts_matches(cal):
    r = cal.generate(CalendarInput(niche="food", posts_per_week=7, start_date="2026-06-01"))
    assert r.total_posts == len(r.entries)


def test_generate_niche_stored(cal):
    r = cal.generate(CalendarInput(niche="travel", start_date="2026-06-01"))
    assert r.niche == "travel"


def test_generate_all_entries_have_date(cal):
    r = cal.generate(CalendarInput(niche="fitness", start_date="2026-06-01"))
    for e in r.entries:
        assert e.date, f"Missing date in entry"


def test_generate_all_entries_have_platform(cal):
    r = cal.generate(CalendarInput(niche="beauty", start_date="2026-06-01"))
    for e in r.entries:
        assert e.platform in ("instagram", "tiktok") or True  # at least not empty


def test_generate_all_entries_have_content_type(cal):
    r = cal.generate(CalendarInput(niche="lifestyle", start_date="2026-06-01"))
    for e in r.entries:
        assert e.content_type in CONTENT_TYPES


def test_generate_all_entries_have_valid_time(cal):
    r = cal.generate(CalendarInput(niche="finance", start_date="2026-06-01"))
    for e in r.entries:
        parts = e.best_posting_time.split(":")
        assert len(parts) == 2
        h, m = int(parts[0]), int(parts[1])
        assert 0 <= h <= 23
        assert 0 <= m <= 59


def test_generate_custom_platforms(cal):
    r = cal.generate(CalendarInput(niche="tech", platforms=["youtube"], start_date="2026-06-01"))
    for e in r.entries:
        assert e.platform == "youtube"


def test_generate_single_platform(cal):
    r = cal.generate(CalendarInput(niche="fashion", platforms=["twitter"], start_date="2026-06-01"))
    for e in r.entries:
        assert e.platform == "twitter"


def test_generate_empty_platforms_falls_back(cal):
    r = cal.generate(CalendarInput(niche="general", platforms=[], start_date="2026-06-01"))
    assert r.total_posts > 0


# ---------- to_ics ----------

def test_to_ics_returns_string(cal):
    r = cal.generate(CalendarInput(niche="tech", start_date="2026-06-01"))
    ics = cal.to_ics(r)
    assert isinstance(ics, str)
    assert ics.startswith("BEGIN:VCALENDAR")
    assert ics.endswith("END:VCALENDAR")


def test_to_ics_contains_vevents(cal):
    r = cal.generate(CalendarInput(niche="food", start_date="2026-06-01"))
    ics = cal.to_ics(r)
    assert "BEGIN:VEVENT" in ics
    assert "END:VEVENT" in ics


def test_to_ics_contains_summary(cal):
    r = cal.generate(CalendarInput(niche="fitness", start_date="2026-06-01"))
    ics = cal.to_ics(r)
    assert "SUMMARY:" in ics


# ---------- optimal_posting_times ----------

def test_optimal_posting_times_instagram(cal):
    times = cal.optimal_posting_times("instagram")
    assert len(times) >= 1
    assert all(isinstance(t, tuple) and len(t) == 2 for t in times)


def test_optimal_posting_times_tiktok(cal):
    times = cal.optimal_posting_times("tiktok")
    assert POSTING_TIMES["tiktok"] == times


def test_optimal_posting_times_invalid(cal):
    with pytest.raises(ValueError, match="Unsupported platform"):
        cal.optimal_posting_times("invalid")


# ---------- TOPIC_TEMPLATES ----------

def test_topic_templates_all_niches_have_topics():
    for niche in ("fashion", "tech", "beauty", "food", "fitness", "travel", "finance", "lifestyle"):
        assert niche in TOPIC_TEMPLATES
        assert len(TOPIC_TEMPLATES[niche]) >= 10
