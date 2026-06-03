"""Content Recycler — repurposes old content with new hooks, CTAs, formats.

Features:
  - Takes old scripts/videos → generates fresh variants with AI
  - Multiple recycling strategies: new hook, new angle, new platform
  - A/B testing aware: uses winning hook types from SmartScheduler
  - Batch recycling: processes queue of aged content, outputs ready-to-post
  - Prevents content fatigue: tracks reuse count per piece

Strategies:
  1. new_hook     — Replace hook, keep body (fastest)
  2. new_angle    — Change template angle (e.g. review → comparison)
  3. new_platform — Adapt for different platform format
  4. remix        — Combine multiple old scripts into one
  5. sequel       — "Day 30 update" version of old content
"""
import json, logging, random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

STRATEGIES = ["new_hook", "new_angle", "new_platform", "remix", "sequel"]
PLATFORM_FORMATS = {
    "tiktok": "15-60s vertical, fast paced, trendy audio",
    "instagram": "reel, aesthetic, slow-mo moments, text overlay",
    "youtube": "long form 8-15min, storytelling, high production value",
}


class ContentRecycler:
    """Recycle old content into fresh variants using AI.

    Usage:
        recycler = ContentRecycler(ai_router)
        recycled = recycler.recycle_batch(old_scripts, "skincare")
        # recycled[0]["fresh_script"] → new version ready to produce
    """

    def __init__(self, ai_router=None):
        self.ai_router = ai_router
        self._recycle_count: dict[str, int] = {}  # content_id → times recycled

    def recycle_script(self, old_script: dict, niche: str = "general",
                       strategy: str = "new_hook") -> dict:
        """Recycle a single old script into a fresh version.

        Args:
            old_script: dict with keys: script, hook, angle, platform, hashtags
            niche: target niche
            strategy: recycling strategy to use

        Returns:
            dict with fresh_script, new_hook, strategy_used, recycle_id
        """
        if strategy not in STRATEGIES:
            strategy = random.choice(STRATEGIES)

        old_hook = old_script.get("hook", "")
        old_body = old_script.get("script", "")
        old_angle = old_script.get("angle", "honest_review")
        old_platform = old_script.get("platform", "tiktok")

        recycle_id = f"recycled_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(100,999)}"

        if self.ai_router:
            fresh = self._recycle_with_ai(old_body, old_hook, old_angle,
                                          old_platform, niche, strategy)
        else:
            fresh = self._recycle_fallback(old_hook, old_body, niche, strategy)

        fresh["recycle_id"] = recycle_id
        fresh["strategy_used"] = strategy
        fresh["original_hook"] = old_hook
        fresh["recycled_at"] = datetime.now().isoformat()

        content_id = old_script.get("content_id", old_hook[:20])
        self._recycle_count[content_id] = self._recycle_count.get(content_id, 0) + 1

        return fresh

    def recycle_batch(self, old_scripts: list[dict], niche: str = "general",
                      count: Optional[int] = None) -> list[dict]:
        """Recycle multiple old scripts, distributing strategies for variety."""
        if not old_scripts:
            return []

        target = min(count or len(old_scripts), len(old_scripts))
        recycled = []

        for i in range(target):
            script = old_scripts[i % len(old_scripts)]
            strategy = STRATEGIES[i % len(STRATEGIES)]
            result = self.recycle_script(script, niche, strategy)
            recycled.append(result)

        log.info("[RECYCLER] Recycled %d/%d scripts (%d strategies used)",
                 len(recycled), target, len(STRATEGIES))
        return recycled

    def find_aged_content(self, age_days: int = 7,
                          min_recycles: int = 0) -> list[dict]:
        """Find content older than N days that hasn't been recycled yet.

        In production, queries ContentBank for old content.
        """
        try:
            from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
            bank = ContentBankV2()
            all_content = bank.get_stats().get("content", [])
            cutoff = datetime.now() - timedelta(days=age_days)
            aged = []
            for c in all_content:
                created = c.get("created_at", "")
                if created and datetime.fromisoformat(created) < cutoff:
                    content_id = c.get("id", c.get("title", ""))
                    if self._recycle_count.get(content_id, 0) <= min_recycles:
                        aged.append(c)
            return aged
        except Exception:
            return []

    def _recycle_with_ai(self, old_body: str, old_hook: str, old_angle: str,
                         old_platform: str, niche: str, strategy: str) -> dict:
        """Use AI router to intelligently recycle content."""
        format_desc = PLATFORM_FORMATS.get(old_platform, "short form video")

        strategy_prompts = {
            "new_hook": f"Buat HOOK BARU yg lebih engaging untuk konten {niche} ini. Hook original: '{old_hook}'.",
            "new_angle": f"Ubah angle konten dari '{old_angle}' ke angle lain (storytelling/comparison/tutorial/myth_busting).",
            "new_platform": f"Adaptasikan konten dari format {format_desc} ke platform lain dengan format berbeda.",
            "remix": f"Buat versi REMIX: gabungkan ide2 dari beberapa script jadi 1 script fresh yg lebih engaging.",
            "sequel": f"Buat versi SEQUEL: 'Update after 30 more days' — tambahkan insight baru, hasil terbaru.",
        }

        strategy_desc = strategy_prompts.get(strategy, strategy_prompts["new_hook"])

        prompt = (
            f"[RECYCLE] Konten UGC {niche} ({old_platform}).\n"
            f"Strategi: {strategy}\n"
            f"{strategy_desc}\n\n"
            f"Konten original:\n{old_body[:500]}\n\n"
            f"Buat versi fresh:\n"
            f"1. Hook baru (max 10 kata, stop scrolling)\n"
            f"2. Script baru (30-45 detik, Bahasa Indonesia natural)\n"
            f"3. CTA baru\n"
            f"4. 5 hashtag baru\n\n"
            f"Format:\n"
            f"Hook: <hook>\n"
            f"Script: <script>\n"
            f"CTA: <cta>\n"
            f"Hashtags: <tags>"
        )

        try:
            raw = self.ai_router.chat(prompt)
            return self._parse_recycled(raw)
        except Exception as e:
            log.warning("[RECYCLER] AI recycle failed: %s", e)
            return self._recycle_fallback(old_hook, old_body, niche, strategy)

    def _recycle_fallback(self, old_hook: str, old_body: str,
                          niche: str, strategy: str) -> dict:
        """Fallback without AI — template-based recycling."""
        new_hooks = {
            "new_hook": f"Gue GA NYANGKA {niche} ini hasilnya segini!",
            "new_angle": f"Perbandingan {niche} mahal vs murah... mengejutkan!",
            "new_platform": f"{niche} version buat IG — lebih aesthetic!",
            "remix": f"SEMUA yg perlu lo tau tentang {niche} dalam 1 video!",
            "sequel": f"30 HARI UPDATE: {niche} — hasil akhirnya bikin speechless!",
        }
        new_ctas = [
            "Komen pendapat lo di bawah!",
            "Share ke temen yg perlu! Follow buat part selanjutnya!",
            "Save dulu, cobain nanti! 🫶",
            "Tag temen lo yg harus tau ini!",
        ]

        hook = new_hooks.get(strategy, new_hooks["new_hook"])
        cta = random.choice(new_ctas)
        body_lines = old_body.split("\n") if old_body else [f"Ini dia {niche} yg lagi viral!"]
        fresh_body = "\n".join(body_lines[:5]) + f"\n\n{cta}"

        return {
            "fresh_script": f"Hook: {hook}\n{fresh_body}",
            "new_hook": hook,
            "cta": cta,
            "hashtags": [niche, "fyp", "viral", "review", "recycled"],
        }

    def _parse_recycled(self, raw: str) -> dict:
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        hook = ""
        script_lines = []
        cta = ""
        hashtags = []

        for line in lines:
            lower = line.lower()
            if lower.startswith("hook:"):
                hook = line[5:].strip()
            elif lower.startswith("script:"):
                script_lines.append(line[7:].strip())
            elif lower.startswith("cta:"):
                cta = line[4:].strip()
            elif lower.startswith("hashtags:"):
                raw_tags = line[9:].strip()
                hashtags = [t.strip().lstrip("#") for t in raw_tags.split(",") if t.strip()]

        if not script_lines:
            content_started = False
            for line in lines:
                if "script:" in line.lower():
                    content_started = True
                    continue
                if content_started:
                    if "cta:" in line.lower() or "hashtags:" in line.lower():
                        break
                    script_lines.append(line)

        full_script = "\n".join(script_lines) if script_lines else raw[:300]

        return {
            "fresh_script": full_script,
            "new_hook": hook or f"Gue coba lagi {random.choice(['skincare','fashion','food'])} ini!",
            "cta": cta or random.choice([
                "Komen di bawah ya!", "Share ke temen!", "Follow buat lanjutan!",
            ]),
            "hashtags": hashtags or ["fyp", "foryou", "viral", "trending"],
        }

    def get_stats(self) -> dict:
        """Recycling statistics."""
        total = sum(self._recycle_count.values())
        unique = len(self._recycle_count)
        return {
            "total_recycles": total,
            "unique_content_recycled": unique,
            "avg_recycles_per_content": round(total / max(unique, 1), 1),
        }
