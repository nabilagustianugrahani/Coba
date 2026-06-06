"""Auto-generate 30-day content calendar for a niche.

Includes optimal posting times (Indonesia timezone UTC+7):
  - Instagram: 11:00-13:00, 19:00-21:00
  - TikTok:    10:00-12:00, 18:00-20:00
  - YouTube:   17:00-20:00
  - Twitter:   12:00-15:00, 21:00-23:00
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from ugc_ai_overpower.integrations.character_agent import Character

log = logging.getLogger(__name__)

CONTENT_TYPES: tuple[str, ...] = ("image", "video", "carousel", "story")

POSTING_TIMES: dict[str, list[tuple[int, int]]] = {
    "instagram": [(11, 0), (12, 0), (19, 0), (20, 0)],
    "tiktok":    [(10, 0), (11, 0), (18, 0), (19, 0)],
    "youtube":   [(17, 0), (18, 0), (19, 0)],
    "twitter":   [(12, 0), (13, 0), (21, 0), (22, 0)],
}

TOPIC_TEMPLATES: dict[str, list[str]] = {
    "fashion": [
        "OOTD inspo", "Thrifted finds", "Style tips", "Capsule wardrobe",
        "Seasonal trends", "Brand review", "Fashion haul", "Mix & match",
        "Color palette", "Wardrobe essentials", "Shoe styling", "Accessory guide",
        "Work outfit", "Date night look", "Budget fashion",
    ],
    "tech": [
        "Gadget review", "Specs breakdown", "Price comparison", "Unboxing",
        "Hidden features", "Software tips", "Tech news", "Accessories",
        "Budget picks", "Flagship vs midrange", "Battery test", "Camera test",
        "Performance review", "Buying guide", "Setup tour",
    ],
    "beauty": [
        "Skincare routine", "Makeup tutorial", "Product review", "Glow up tips",
        "Ingredient deep dive", "Budget beauty", "Luxury picks", "Hair care",
        "Nail art", "Body care", "Morning routine", "Night routine",
        "Sunscreen guide", "Serum comparison", "Tool review",
    ],
    "food": [
        "Easy recipe", "Street food review", "Hidden gem", "Budget meal",
        "Meal prep", "Dessert recipe", "Drink recipe", "Restaurant review",
        "Cooking hack", "Ingredient guide", "Food challenge", "Local cuisine",
        "Healthy meal", "Comfort food", "Food plating",
    ],
    "fitness": [
        "Home workout", "Gym routine", "Stretching guide", "Cardio session",
        "Strength training", "HIIT workout", "Yoga flow", "Meal prep",
        "Supplement review", "Progress update", "Form check", "Recovery tips",
        "Motivation", "Gym essentials", "Outdoor workout",
    ],
    "travel": [
        "Destination guide", "Hidden gem", "Itinerary", "Budget trip",
        "Travel hack", "Hotel review", "Food guide", "Packing list",
        "Solo travel", "Road trip", "Cultural guide", "Nature spot",
        "City guide", "Beach getaway", "Mountain adventure",
    ],
    "finance": [
        "Saving tips", "Investment 101", "Budget template", "Side hustle",
        "Passive income", "Crypto basics", "Stock tips", "Reksadana guide",
        "Insurance guide", "Tax tips", "Retirement plan", "Emergency fund",
        "Debt management", "Credit card hack", "Financial goal",
    ],
    "lifestyle": [
        "Daily routine", "Productivity hack", "Self care", "Reading list",
        "Minimalism", "Goal setting", "Journaling", "Home decor",
        "Organization", "Morning routine", "Evening routine", "Mindfulness",
        "Digital detox", "Habit tracker", "Gratitude list",
    ],
    "general": [
        "Daily vlog", "Behind the scenes", "Q&A", "Challenge",
        "Story time", "Tips and tricks", "Review", "Comparison",
        "Tutorial", "FAQ", "Update", "Collaboration",
    ],
}


@dataclass
class CalendarInput:
    niche: str = "general"
    start_date: str = ""  # YYYY-MM-DD
    posts_per_week: int = 5
    platforms: list[str] = field(default_factory=lambda: ["instagram", "tiktok"])
    character_id: Optional[str] = None


@dataclass
class CalendarEntry:
    date: str
    platform: str
    content_type: str
    topic: str
    caption_template: str
    hashtags: list[str] = field(default_factory=list)
    cta: str = ""
    best_posting_time: str = "12:00"


@dataclass
class CalendarResult:
    entries: list[CalendarEntry] = field(default_factory=list)
    total_posts: int = 0
    niche: str = ""

    def to_ics(self) -> str:
        """Generate a simple ICS string for calendar import."""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//UGC AI//ContentCalendar//EN",
        ]
        for entry in self.entries:
            dt_start = entry.date.replace("-", "") + "T" + entry.best_posting_time.replace(":", "") + "00"
            lines.append("BEGIN:VEVENT")
            lines.append(f"UID:{hash(entry.date + entry.platform + entry.topic)}")
            lines.append(f"DTSTART:{dt_start}")
            lines.append(f"SUMMARY:{entry.platform}: {entry.topic}")
            lines.append(f"DESCRIPTION:Type: {entry.content_type} | CTA: {entry.cta}")
            lines.append("END:VEVENT")
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)


def _deterministic_pick(seed: str, items: list[str]) -> str:
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % max(1, len(items))
    return items[idx]


def _rotate_list(items: list[str], offset: int) -> list[str]:
    if not items:
        return items
    o = offset % len(items)
    return items[o:] + items[:o]


class ContentCalendar:
    def __init__(self, character: Optional[Character] = None) -> None:
        self.character = character

    def generate(self, calendar_input: CalendarInput) -> CalendarResult:
        niche = calendar_input.niche.lower()
        posts_per_week = max(1, min(calendar_input.posts_per_week, 7))
        platforms = [p.lower() for p in calendar_input.platforms]
        if not platforms:
            platforms = ["instagram", "tiktok"]

        # Parse start date
        start: datetime
        if calendar_input.start_date:
            try:
                start = datetime.strptime(calendar_input.start_date, "%Y-%m-%d")
            except ValueError:
                start = datetime.utcnow()
        else:
            start = datetime.utcnow()

        topic_pool = TOPIC_TEMPLATES.get(niche, TOPIC_TEMPLATES["general"])
        entries: list[CalendarEntry] = []
        total_days = 30

        for day_offset in range(total_days):
            day = start + timedelta(days=day_offset)
            # Skip weekends? No — include all days, allocate posts_per_week across 7 days
            day_of_week = day.weekday()
            # Posts per day: distribute posts_per_week across 7 days
            posts_today_count = 0
            for p in range(posts_per_week):
                if (p * 7 // posts_per_week) == day_of_week:
                    posts_today_count += 1

            for p_idx in range(posts_today_count):
                platform = platforms[(day_offset + p_idx) % len(platforms)]
                content_type = _deterministic_pick(
                    f"{day.isoformat()}_{platform}_{p_idx}_type",
                    list(CONTENT_TYPES),
                )
                rotated_topics = _rotate_list(topic_pool, day_offset + p_idx)
                topic = rotated_topics[p_idx % len(rotated_topics)] if rotated_topics else "Content"
                hashtag_seed = f"{day.isoformat()}_{platform}_{p_idx}_tags"

                # Generate hashtags deterministically
                hashtag_pool = [f"#{niche}", f"#{topic.lower().replace(' ', '')}", f"#{platform}"]
                hashtags = hashtag_pool[:3]

                # Pick best posting time
                times = POSTING_TIMES.get(platform, [(12, 0)])
                time_idx = (day_offset + p_idx) % len(times)
                h, m = times[time_idx]
                best_time = f"{h:02d}:{m:02d}"

                cta = f"Follow for more {niche} content!"
                caption = f"New {topic} post! Check it out on {platform}."

                entries.append(CalendarEntry(
                    date=day.strftime("%Y-%m-%d"),
                    platform=platform,
                    content_type=content_type,
                    topic=topic,
                    caption_template=caption,
                    hashtags=hashtags,
                    cta=cta,
                    best_posting_time=best_time,
                ))

        return CalendarResult(
            entries=entries,
            total_posts=len(entries),
            niche=niche,
        )

    def to_ics(self, calendar: CalendarResult) -> str:
        """Generate ICS string for a CalendarResult."""
        return calendar.to_ics()

    def optimal_posting_times(self, platform: str, niche: str = "") -> list[tuple[int, int]]:
        """Return optimal posting time slots for a platform."""
        p = platform.lower()
        if p not in POSTING_TIMES:
            raise ValueError(f"Unsupported platform: {p}. Supported: {list(POSTING_TIMES)}")
        return list(POSTING_TIMES[p])


__all__ = [
    "CalendarEntry",
    "CalendarInput",
    "CalendarResult",
    "ContentCalendar",
    "CONTENT_TYPES",
    "POSTING_TIMES",
    "TOPIC_TEMPLATES",
]
