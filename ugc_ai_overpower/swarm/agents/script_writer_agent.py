"""Script Writer Agent — generates UGC scripts via AI.

Listens for: generate_scripts
Broadcasts: scripts_ready
"""
import json, logging, concurrent.futures, random
from typing import Optional

from swarm.base_agent import BaseAgent
from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)

TEMPLATES = {
    "honest_review": {"angle": "jujur tanpa drama", "structure": ["Hook", "Kenalan sama produk", "First impression", "Dipakai rutin", "Hasil", "Kesimpulan", "CTA"]},
    "storytelling": {"angle": "cerita personal relateable", "structure": ["Masalah", "Ketemu produk", "Pake pertama", "Transformasi", "Testimoni", "CTA"]},
    "comparison": {"angle": "sebelum-sesudah", "structure": ["Hook perbandingan", "Produk A", "Produk B", "Head to head", "Pemenang", "CTA"]},
    "tutorial_hack": {"angle": "tips & trik rahasia", "structure": ["Hook hack", "Yang salah selama ini", "Cara bener", "Hasil maksimal", "Pro tip", "CTA"]},
    "challenge": {"angle": "tantangan X hari", "structure": ["Hook challenge", "Day 1", "Day 3", "Day 7", "Hasil akhir", "CTA"]},
    "myth_busting": {"angle": "mitos vs fakta", "structure": ["Mitos umum", "Fakta sebenarnya", "Bukti nyata", "Penjelasan", "Kesimpulan", "CTA"]},
    "asmr_unboxing": {"angle": "ASMR unboxing", "structure": ["Unboxing", "Look pertama", "Tekstur", "Coba langsung", "First reaction", "CTA"]},
    "day_in_life": {"angle": "daily routine", "structure": ["Pagi", "Siang", "Sore", "Malam", "Refleksi", "CTA"]},
}

HOOKS = {
    "skincare": ["Jangan beli {product} sebelum nonton ini!", "Dokter bilang {product} ini berbahaya!", "Gue pake {product} selama 30 hari, ini hasilnya..."],
    "fashion": ["Outfit pake {product} langsung disukai gebetan!", "{product} ini bikin lo keliatan kaya!"],
    "food": ["Resep {product} paling enak se-Indonesia!", "Gue coba {product} viral, ini kejujuran!"],
    "general": ["STOP! Jangan beli {product} kalo belum nonton ini!", "Gue baru nemu {product} yang bikin nagih!"],
}

CTA_LIST = [
    "Komen pendapat lo di bawah!", "Share ke temen yang butuh!",
    "Follow buat review lainnya!", "Save dulu biar gak ilang!",
]

INFLUENCERS = [
    {"name": "sari", "gender": "female"}, {"name": "budi", "gender": "male"},
    {"name": "dian", "gender": "female"}, {"name": "rudi", "gender": "male"},
    {"name": "intan", "gender": "female"}, {"name": "agus", "gender": "male"},
]


class ScriptWriterAgent(BaseAgent):
    name = "script_writer"

    def __init__(self, ai_router=None):
        super().__init__(poll_interval=0.5, max_concurrent=5)
        self.ai_router = ai_router
        self._router_url = skynet_config.get("router", "base_url", default="http://localhost:20128")
        self._router_key = skynet_config.get("router", "api_key", default="")

    def handle_generate_scripts(self, msg: dict) -> dict:
        payload = msg["payload"]
        campaign_id = payload.get("campaign_id", "")
        product = payload.get("product", "")
        niche = payload.get("niche", "general")
        count = payload.get("count", 50)
        platforms = payload.get("platforms", ["tiktok"])

        hooks_pool = HOOKS.get(niche, HOOKS["general"])
        hooks = [h.format(product=product) for h in hooks_pool]

        log.info("[SW] Generating %d scripts for %s (campaign=%s)", count, product, campaign_id)

        scripts = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, count)) as pool:
            futures = []
            for i in range(count):
                template = random.choice(list(TEMPLATES.values()))
                inf = random.choice(INFLUENCERS)
                platform = random.choice(platforms)
                hook = hooks[i % len(hooks)]
                prompt = (
                    f"[INST] Tulis SCRIPT UGC EPISODE #{i+1} untuk '{product}'.\n"
                    f"Influencer: {inf['name']} ({inf['gender']})\nPlatform: {platform}\n"
                    f"Hook: \"{hook}\"\nAngle: {template['angle']}\n"
                    f"Struktur: {', '.join(template['structure'])}\n"
                    f"CTA: {random.choice(CTA_LIST)}\nDurasi: 30-60 detik\n"
                    f"Bahasa Indonesia santai natural. Langsung dialog. [/INST]"
                )
                futures.append(pool.submit(self._gen_one, prompt, inf, platform, hook, template))

            for fut in concurrent.futures.as_completed(futures):
                try:
                    r = fut.result()
                    if r:
                        scripts.append(r)
                except Exception as e:
                    log.warning("[SW] Script gen failed: %s", e)

        log.info("[SW] %d scripts generated for campaign %s", len(scripts), campaign_id)

        self.send("orchestrator", "scripts_ready", {
            "campaign_id": campaign_id,
            "scripts": scripts,
            "product": product,
            "niche": niche,
            "platforms": platforms,
            "use_affiliate": payload.get("use_affiliate", True),
        })

        return {"campaign_id": campaign_id, "scripts_count": len(scripts)}

    def _gen_one(self, prompt, inf, platform, hook, template) -> Optional[dict]:
        if not self.ai_router:
            return {
                "script": f"Halo guys! Hari ini gue mau review produk nih! {hook}",
                "hook": hook, "influencer": inf["name"], "gender": inf["gender"],
                "platform": platform, "angle": template["angle"],
                "hashtags": ["fyp", "review", "ugc"],
            }
        try:
            raw = self.ai_router.chat(prompt)
            if not raw or len(raw) < 30:
                return None
            script = self._clean(raw)
            h_prompt = f"Generate 5 hashtag untuk: {hook}. Format: #tag1 #tag2 #tag3"
            h_raw = self.ai_router.chat(h_prompt)
            import re
            hashtags = re.findall(r'#(\w+)', h_raw)[:5]
            return {
                "script": script, "hook": hook, "influencer": inf["name"],
                "gender": inf["gender"], "platform": platform,
                "angle": template["angle"], "hashtags": hashtags,
            }
        except Exception as e:
            log.warning("[SW] AI call failed, using fallback: %s", e)
            return {
                "script": f"Halo guys! Hari ini gue mau review produk nih! {hook}",
                "hook": hook, "influencer": inf["name"], "gender": inf["gender"],
                "platform": platform, "angle": template["angle"],
                "hashtags": ["fyp", "review"],
            }

    @staticmethod
    def _clean(raw: str) -> str:
        import re
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        cleaned = []
        for l in lines:
            if re.match(r'^(berikut|tentu|oke|baik|ini dia|halo|hai)', l, re.I):
                continue
            if re.match(r'^##?\s', l) or re.match(r'^\[/', l):
                continue
            cleaned.append(l)
        return "\n".join(cleaned) if cleaned else raw
