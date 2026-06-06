"""Generate CTAs (calls to action) tailored to niche + platform + funnel stage.

Supports 8 niches × 4 funnel stages × 3 tones = 96 template combinations.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

NICHES: tuple[str, ...] = ("fashion", "tech", "beauty", "food", "fitness", "travel", "finance", "lifestyle")
FUNNEL_STAGES: tuple[str, ...] = ("awareness", "consideration", "conversion", "retention")
TONES: tuple[str, ...] = ("casual", "professional", "playful")

# 8 niches × 4 stages × 3 tones = 96 combinations
TEMPLATES: dict[str, dict[str, dict[str, list[str]]]] = {
    "fashion": {
        "awareness": {
            "casual": ["Swipe untuk OOTD hari ini!", "Yang mana favorite kamu? 💕", "Coba tebak brand apa ini?"],
            "professional": ["Discover the latest trends in fashion.", "Elevate your wardrobe with curated pieces."],
            "playful": ["Get ready to slay! 🔥", "Your outfit just got an upgrade!"],
        },
        "consideration": {
            "casual": ["Komen 'LINK' ya buat detail!", "Save dulu, nanti checkout!", "Cek review lengkapnya di bio!"],
            "professional": ["Read our full style guide for details.", "Compare features and find your perfect fit."],
            "playful": ["Spill the tea — check the link! ☕", "Don't sleep on this deal!"],
        },
        "conversion": {
            "casual": ["Shop now, link di bio!", "Gak mau kehabisan? Checkout sekarang!", "Diskon terbatas, grab now!"],
            "professional": ["Purchase now with free shipping.", "Limited stock — order today."],
            "playful": ["Add to cart, bestie! 🛒", "Your wallet said yes already 💸"],
        },
        "retention": {
            "casual": ["Follow for daily OOTD inspo!", "Share with your fashion bestie!", "Jangan lupa subscribe ya!"],
            "professional": ["Subscribe to our newsletter for curated looks.", "Follow us for daily style inspiration."],
            "playful": ["Stay fab, bestie! ✨", "You know you want more — follow!"],
        },
    },
    "tech": {
        "awareness": {
            "casual": ["Tech update hari ini!", "Cek spesifikasi lengkapnya!", "Gadget mana yang paling menarik?"],
            "professional": ["Stay ahead with the latest tech insights.", "Discover innovative solutions for your workflow."],
            "playful": ["Your next upgrade is here! 🚀", "Say hi to the future!"],
        },
        "consideration": {
            "casual": ["Komen 'REVIEW' untuk detail!", "Baca perbandingan lengkap di blog!", "Cek harga terbaru di link bio!"],
            "professional": ["Read our in-depth analysis and benchmarks.", "Compare specs side-by-side."],
            "playful": ["The specs will blow your mind! 🤯", "Swipe for the full breakdown!"],
        },
        "conversion": {
            "casual": ["Beli sekarang, harga naik besok!", "Link pembelian di bio!", "Pastiin kamu gak ketinggalan!"],
            "professional": ["Order now with exclusive launch pricing.", "Secure your unit today."],
            "playful": ["Take my money already! 💳", "Add to cart, thank us later!"],
        },
        "retention": {
            "casual": ["Follow for tech tips setiap hari!", "Share ke temen tech kamu!", "Subscribe buat review selanjutnya!"],
            "professional": ["Subscribe for weekly tech digests.", "Follow for industry updates."],
            "playful": ["Never miss a drop! 🛸", "Stay connected — hit follow!"],
        },
    },
    "beauty": {
        "awareness": {
            "casual": ["Holy grail alert! ✨", "Coba tebak produk apa ini?", "Routine kamu bakal berubah!"],
            "professional": ["Introducing our new skincare formulation.", "Discover the science behind the glow."],
            "playful": ["Glow up incoming! 💅", "Your skin is about to thank you!"],
        },
        "consideration": {
            "casual": ["Komen 'SKINCARE' buat link!", "Review lengkap di IGTV!", "Save buat belanja nanti!"],
            "professional": ["Read our dermatologist-reviewed guide.", "Check ingredient analysis in bio."],
            "playful": ["Your skincare routine called — it needs this! 📞"],
        },
        "conversion": {
            "casual": ["Shop sekarang, link di bio!", "Diskon 20% hari ini doang!", "Gak nyesel beli ini!"],
            "professional": ["Purchase now with our money-back guarantee.", "Limited batch — order while stocks last."],
            "playful": ["Treat yourself, you deserve it! 🎀", "Add to cart — no regrets!"],
        },
        "retention": {
            "casual": ["Follow buat tips skincare harian!", "Tag temen yang perlu skincare!", "Subscribe for more glow!"],
            "professional": ["Subscribe for weekly beauty insights.", "Follow for science-backed skincare tips."],
            "playful": ["Stay glowing, gorgeous! ✨", "You + us = best skin ever!"],
        },
    },
    "food": {
        "awareness": {
            "casual": ["Makanan enak banget nih!", "Coba tebak menu apa ini?", "Lapar? Cocok banget!"],
            "professional": ["Discover culinary experiences worth trying.", "A curated taste journey awaits."],
            "playful": ["Your taste buds are screaming! 😋", "Food coma incoming!"],
        },
        "consideration": {
            "casual": ["Komen 'RESEP' buat detail!", "Alamatnya cek bio ya!", "Rating 9/10, wajib coba!"],
            "professional": ["Read our full restaurant review.", "Check the menu and pricing."],
            "playful": ["Swipe for the recipe reveal! 🍜", "Your kitchen called — make this!"],
        },
        "conversion": {
            "casual": ["Pesan sekarang, link di bio!", "Promo terbatas, grab fast!", "Delivery hari ini juga!"],
            "professional": ["Order now via our partners.", "Exclusive discount for first-time customers."],
            "playful": ["Don't let it get cold — order now! 🍕", "Your stomach said yes!"],
        },
        "retention": {
            "casual": ["Follow for rekomendasi makanan!", "Tag temen yang hobi makan!", "Subscribe for more food content!"],
            "professional": ["Subscribe for curated food guides.", "Follow us for your next meal inspiration."],
            "playful": ["Never eat alone again! 🍽️", "Stay hungry, stay following!"],
        },
    },
    "fitness": {
        "awareness": {
            "casual": ["Hari ini workout apa?", "Coba gerakan baru ini!", "Your fitness journey starts here!"],
            "professional": ["Optimize your training with science-based routines.", "Transform your approach to fitness."],
            "playful": ["No pain, no gain — let's go! 💪", "Your gym crush is watching!"],
        },
        "consideration": {
            "casual": ["Komen 'WORKOUT' buat program!", "Full tutorial di bio!", "Cek form yang benar di sini!"],
            "professional": ["Read our evidence-based training guide.", "Compare program structures and results."],
            "playful": ["Swipe for the burn! 🔥", "Your muscles are about to feel this!"],
        },
        "conversion": {
            "casual": ["Join program sekarang, link di bio!", "Early bird diskon 30%!", "Transformasi 30 hari, mulai hari ini!"],
            "professional": ["Enroll in our certified training program.", "Start your transformation today."],
            "playful": ["Summer body ready? Let's go! 🏋️", "Sign up and crush your goals!"],
        },
        "retention": {
            "casual": ["Follow for daily workout tips!", "Tag your gym buddy!", "Subscribe buat progress update!"],
            "professional": ["Subscribe for weekly fitness plans.", "Join our community of dedicated athletes."],
            "playful": ["Keep grinding, fam! 💪", "Stay fit, stay following!"],
        },
    },
    "travel": {
        "awareness": {
            "casual": ["Hidden gem di Indonesia!", "Coba tebak destinasi ini!", "Liburan impian lo ada di sini!"],
            "professional": ["Discover extraordinary destinations.", "Plan your next journey with confidence."],
            "playful": ["Pack your bags! ✈️", "Your next adventure starts here!"],
        },
        "consideration": {
            "casual": ["Komen 'GUIDE' buat itinerary!", "Tips traveling lengkap di bio!", "Budget-friendly guide di sini!"],
            "professional": ["Read our comprehensive travel guide.", "Compare routes, prices, and experiences."],
            "playful": ["Swipe for the ultimate travel hack! 🗺️", "Your passport is ready!"],
        },
        "conversion": {
            "casual": ["Booking sekarang, link di bio!", "Promo hotel 50% — hari ini aja!", "Jangan sampe kehabisan tiket!"],
            "professional": ["Book now with our exclusive rates.", "Limited spots — reserve your journey."],
            "playful": ["Adventure awaits — book now! 🌴", "Say yes to new places!"],
        },
        "retention": {
            "casual": ["Follow for travel inspo setiap hari!", "Tag temen traveling kamu!", "Subscribe for more adventures!"],
            "professional": ["Subscribe for weekly travel inspiration.", "Follow us for your next getaway idea."],
            "playful": ["The world is calling! 🌍", "Stay wandering, stay following!"],
        },
    },
    "finance": {
        "awareness": {
            "casual": ["Tips finansial hari ini!", "Coba tebak instrumen investasi apa?", "Uang kamu bisa berkembang!"],
            "professional": ["Smart financial strategies for modern investors.", "Build wealth with data-driven decisions."],
            "playful": ["Your money is sleeping — wake it up! 💰", "Rich mindset incoming!"],
        },
        "consideration": {
            "casual": ["Komen 'INVEST' buat panduan!", "Analisis lengkap di blog!", "Cek reksadana terbaik di bio!"],
            "professional": ["Read our comprehensive market analysis.", "Compare portfolio options and risk profiles."],
            "playful": ["Don't just save — invest! 📈", "Your future self will thank you!"],
        },
        "conversion": {
            "casual": ["Mulai investasi sekarang, link di bio!", "Bonus deposit 100rb, terbatas!", "Jangan tunda kekayaan kamu!"],
            "professional": ["Open your account with zero fees.", "Start building your portfolio today."],
            "playful": ["Make your money work harder! 💸", "Invest now, retire early!"],
        },
        "retention": {
            "casual": ["Follow for daily financial tips!", "Share with your money bestie!", "Subscribe for market update!"],
            "professional": ["Subscribe for weekly market insights.", "Follow for expert financial analysis."],
            "playful": ["Stay rich, stay following! 🪙", "Your wallet is growing already!"],
        },
    },
    "lifestyle": {
        "awareness": {
            "casual": ["Daily life update!", "Coba tebak aktivitas hari ini?", "Inspirasi baru buat kamu!"],
            "professional": ["Curated lifestyle content for the modern individual.", "Elevate your daily routine."],
            "playful": ["Living your best life! ✨", "Your daily dose of inspo!"],
        },
        "consideration": {
            "casual": ["Komen 'TIPS' buat selengkapnya!", "Full story di blog!", "Cek rekomendasi di bio!"],
            "professional": ["Read our curated lifestyle recommendations.", "Explore products that match your values."],
            "playful": ["You need this in your life! 💫", "Swipe for the full story!"],
        },
        "conversion": {
            "casual": ["Shop now, link di bio!", "Diskon spesial untuk followers!", "Grab yours before sold out!"],
            "professional": ["Purchase with our curated selection.", "Limited edition — order now."],
            "playful": ["Treat yo self! 🎉", "Your cart is waiting!"],
        },
        "retention": {
            "casual": ["Follow for more lifestyle tips!", "Tag temen yang suka lifestyle!", "Subscribe for daily inspo!"],
            "professional": ["Subscribe for weekly lifestyle curation.", "Follow for mindful living tips."],
            "playful": ["Stay inspired, bestie! 💕", "You're part of the family now!"],
        },
    },
}

# Historical CTR estimates per niche (0-1)
_CTR_MAP: dict[str, float] = {
    "fashion": 0.045, "tech": 0.038, "beauty": 0.052, "food": 0.048,
    "fitness": 0.041, "travel": 0.055, "finance": 0.035, "lifestyle": 0.042,
}

# Emoji suggestions per niche
_EMOJI_MAP: dict[str, str] = {
    "fashion": "💕", "tech": "🚀", "beauty": "✨", "food": "😋",
    "fitness": "💪", "travel": "✈️", "finance": "💰", "lifestyle": "💫",
}


@dataclass
class CTAInput:
    niche: str = "general"
    platform: str = "instagram"
    funnel_stage: str = "awareness"
    tone: str = "casual"


@dataclass
class CTAResult:
    primary_cta: str
    alternative_ctas: list[str] = field(default_factory=list)
    emoji_suggestion: str = ""
    estimated_ctr: float = 0.0  # 0-1


class CTAGenerator:
    def __init__(self) -> None:
        self._rng = random.Random(42)

    def generate(self, cta_input: CTAInput) -> CTAResult:
        niche = cta_input.niche.lower()
        platform = cta_input.platform.lower()
        stage = cta_input.funnel_stage.lower()
        tone = cta_input.tone.lower()

        if niche not in NICHES:
            raise ValueError(f"Unsupported niche: {niche}. Supported: {list(NICHES)}")
        if stage not in FUNNEL_STAGES:
            raise ValueError(f"Unsupported funnel_stage: {stage}. Supported: {list(FUNNEL_STAGES)}")
        if tone not in TONES:
            raise ValueError(f"Unsupported tone: {tone}. Supported: {list(TONES)}")
        if platform not in ("tiktok", "instagram", "twitter", "youtube", "linkedin"):
            raise ValueError(f"Unsupported platform: {platform}")

        templates = TEMPLATES.get(niche, {}).get(stage, {}).get(tone, [])
        if not templates:
            raise ValueError(f"No templates for {niche}/{stage}/{tone}")

        primary = templates[0]
        alternatives = templates[1:] if len(templates) > 1 else templates[:1]

        emoji = _EMOJI_MAP.get(niche, "✨")
        ctr = _CTR_MAP.get(niche, 0.040)

        return CTAResult(
            primary_cta=primary,
            alternative_ctas=alternatives,
            emoji_suggestion=emoji,
            estimated_ctr=ctr,
        )

    def ab_test_variants(self, niche: str, count: int = 3) -> list[str]:
        """Return ``count`` CTA variants across different tones for A/B testing."""
        if niche.lower() not in NICHES:
            raise ValueError(f"Unsupported niche: {niche}")

        niche_templates = TEMPLATES.get(niche.lower(), {})
        variants: list[str] = []
        # Collect one from each stage × tone mix
        stages = list(niche_templates.keys())
        self._rng.shuffle(stages)
        for stage in stages:
            for tone in TONES:
                pool = niche_templates.get(stage, {}).get(tone, [])
                if pool:
                    pick = self._rng.choice(pool)
                    if pick not in variants:
                        variants.append(pick)
                    if len(variants) >= count:
                        return variants[:count]
        return variants[:count] if variants else ["Check link in bio!"]


__all__ = [
    "CTAInput",
    "CTAResult",
    "CTAGenerator",
    "FUNNEL_STAGES",
    "NICHES",
    "TEMPLATES",
    "TONES",
]
