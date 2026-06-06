"""Per-niche content presets for UGC content generation.

Each niche has a frozen preset defining colors, tone, voice, emoji style,
common phrases, banned words, image style, and typical CTAs.

8 niches: fashion, tech, beauty, food, fitness, travel, finance, lifestyle
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NichePreset:
    niche: str
    primary_colors: list[str]  # hex codes
    tone: str  # casual, professional, playful, authoritative, energetic
    voice_traits: list[str]
    emoji_style: str  # minimal, moderate, heavy
    common_phrases: list[str]
    banned_words: list[str]
    image_style: str
    typical_ctas: list[str]


class NichePresets:
    """Registry of per-niche presets with lookup and caption application."""

    PRESETS: dict[str, NichePreset] = {
        "fashion": NichePreset(
            niche="fashion",
            primary_colors=["#FF69B4", "#FFD700", "#000000"],
            tone="playful",
            voice_traits=["trendy", "confident", "stylish", "bold"],
            emoji_style="heavy",
            common_phrases=["OOTD", "slay", "fit check", "style inspo", "capsule wardrobe"],
            banned_words=["basic", "trying too hard", "outdated"],
            image_style="Mirror selfies, OOTD grids, color-coordinated backgrounds",
            typical_ctas=["Outfit details in comments", "Tag a friend who needs this",
                          "Would you wear this?", "Save this look"],
        ),
        "tech": NichePreset(
            niche="tech",
            primary_colors=["#1E90FF", "#00FF00", "#2F2F2F"],
            tone="authoritative",
            voice_traits=["analytical", "precise", "knowledgeable", "objective"],
            emoji_style="minimal",
            common_phrases=["specs", "benchmark", "review", "unboxing", "performance"],
            banned_words=["meh", "it's fine", "overhyped"],
            image_style="Clean desk setup, dark mode, side-by-side comparisons",
            typical_ctas=["Full review in bio", "Drop your questions below",
                          "Which one would you pick?", "Read the benchmarks"],
        ),
        "beauty": NichePreset(
            niche="beauty",
            primary_colors=["#FFC0CB", "#FF69B4", "#FFFFFF"],
            tone="casual",
            voice_traits=["glowing", "enthusiastic", "relatable", "generous"],
            emoji_style="heavy",
            common_phrases=["glow up", "holy grail", "skincare routine", "makeup tutorial",
                            "product review"],
            banned_words=["cheap", "boring", "overrated"],
            image_style="Bright well-lit close-ups, before/after, soft pinks/golds",
            typical_ctas=["Save this for your next haul", "DM me for the link",
                          "Comment your skin type below", "Tag a beauty bestie"],
        ),
        "food": NichePreset(
            niche="food",
            primary_colors=["#FF4500", "#FFD700", "#8B4513"],
            tone="playful",
            voice_traits=["hungry", "adventurous", "honest", "enthusiastic"],
            emoji_style="heavy",
            common_phrases=["taste test", "homemade", "foodie", "comfort food", "hidden gem"],
            banned_words=["gross", "inedible", "disgusting"],
            image_style="Close-up food shots, steam shots, color-popping plates",
            typical_ctas=["Recipe in comments", "Try this and tag me",
                          "Where should I eat next?", "Save this recipe"],
        ),
        "fitness": NichePreset(
            niche="fitness",
            primary_colors=["#00FF00", "#FF0000", "#000000"],
            tone="energetic",
            voice_traits=["motivated", "disciplined", "strong", "determined"],
            emoji_style="moderate",
            common_phrases=["grind", "gains", "no pain no gain", "workout routine",
                            "transformation"],
            banned_words=["lazy", "skip leg day", "give up"],
            image_style="Gym mirror shots, sweat details, before/after progress",
            typical_ctas=["Save this workout", "Tag your gym buddy",
                          "Drop your PR in comments", "Try this routine"],
        ),
        "travel": NichePreset(
            niche="travel",
            primary_colors=["#00BFFF", "#FFD700", "#228B22"],
            tone="casual",
            voice_traits=["wanderlust", "curious", "free-spirited", "adventurous"],
            emoji_style="moderate",
            common_phrases=["hidden gem", "wanderlust", "adventure", "itinerary",
                            "bucket list"],
            banned_words=["tourist trap", "overrated destination"],
            image_style="Drone shots, golden hour, scenic landscapes, food close-ups",
            typical_ctas=["Full itinerary in bio", "Save this for your next trip",
                          "Where should I go next?", "Tag your travel buddy"],
        ),
        "finance": NichePreset(
            niche="finance",
            primary_colors=["#006400", "#FFD700", "#F5F5DC"],
            tone="professional",
            voice_traits=["smart", "cautious", "forward-thinking", "educated"],
            emoji_style="minimal",
            common_phrases=["invest", "passive income", "financial freedom", "budget",
                            "portfolio"],
            banned_words=["get rich quick", "guaranteed returns", "risk-free"],
            image_style="Charts, calculator, minimal desk setup, clean infographics",
            typical_ctas=["Full breakdown in carousel", "Save for later",
                          "What's your biggest financial goal?", "Share this tip"],
        ),
        "lifestyle": NichePreset(
            niche="lifestyle",
            primary_colors=["#DDA0DD", "#87CEEB", "#F5F5DC"],
            tone="casual",
            voice_traits=["balanced", "mindful", "authentic", "warm"],
            emoji_style="moderate",
            common_phrases=["self-care", "daily routine", "balance", "mindfulness",
                            "simple living"],
            banned_words=["perfect", "effortless", "hustle culture"],
            image_style="Soft natural lighting, daily moments, cozy aesthetics",
            typical_ctas=["Follow for more tips", "Share your routine",
                          "How do you unwind?", "Tag someone who needs this"],
        ),
    }

    @classmethod
    def get(cls, niche: str) -> NichePreset:
        """Look up a preset by niche name. Raises KeyError if not found."""
        if niche not in cls.PRESETS:
            raise KeyError(
                f"Unknown niche: {niche}. Available: {cls.list_niches()}"
            )
        return cls.PRESETS[niche]

    @classmethod
    def list_niches(cls) -> list[str]:
        """Return sorted list of available niche names."""
        return sorted(cls.PRESETS.keys())

    @classmethod
    def apply_to_caption(cls, niche: str, caption: str) -> str:
        """Apply niche preset to a caption: inject tone, swap banned words, add CTA.

        This is a simplified rule-based transformation (no LLM).
        """
        preset = cls.get(niche)

        # 1. Remove banned words (case-insensitive)
        for bw in preset.banned_words:
            caption = re.sub(rf"\b{re.escape(bw)}\b", "", caption, flags=re.IGNORECASE)
        caption = re.sub(r"  +", " ", caption).strip()

        # 2. Inject a random common phrase at the end if not already present
        for phrase in preset.common_phrases:
            if phrase.lower() in caption.lower():
                break
        else:
            import random
            phrase = random.choice(preset.common_phrases)
            caption += f" {phrase}"

        # 3. Add a CTA if none detected
        cta_keywords = ["follow", "subscribe", "share", "like", "comment", "save",
                        "check link", "link in bio", "tag", "dm", "shop"]
        has_cta = any(kw in caption.lower() for kw in cta_keywords)
        if not has_cta:
            import random
            caption += f" {random.choice(preset.typical_ctas)}"

        return caption.strip()

    @classmethod
    def get_image_style(cls, niche: str) -> str:
        """Return the image style guide for a niche."""
        return cls.get(niche).image_style

    @classmethod
    def get_tone(cls, niche: str) -> str:
        """Return the recommended tone for a niche."""
        return cls.get(niche).tone


__all__ = [
    "NichePreset",
    "NichePresets",
]
