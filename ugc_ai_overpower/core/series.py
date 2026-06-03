"""Content series engine — structured series, episodes, auto-scheduling."""
import json, logging, random
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)


class SeriesEngine:
    """Generate structured content series with episode templates."""

    # Episode type templates for popular UGC niches
    TEMPLATES = {
        "review": {
            "structure": [
                "intro_hook", "unboxing", "first_impressions", "key_features",
                "pros_cons", "price_value", "final_verdict", "cta"
            ],
            "opening": [
                "Kalian harus lihat {product} ini!",
                "Gue baru nemu {product} yang bikin shock!",
                "Jangan beli {product} sebelum nonton ini!",
                "Review jujur {product} tanpa drama",
            ],
            "closing": [
                "Pokoknya worth it banget!",
                "Gue recommend banget deh!",
                "Murah meriah kualitas juara!",
                "Sayang banget kalo gak cobain!",
            ]
        },
        "tutorial": {
            "structure": [
                "problem_hook", "intro_product", "step_1", "step_2",
                "step_3", "result", "pro_tip", "cta"
            ],
            "opening": [
                "Cara pakai {product} yang bener nih!",
                "Masalah {problem}? Solusinya {product}!",
                "Gak nyangka semudah ini pake {product}!",
                "Stop lakuin ini! Pake {product} aja!",
            ],
            "closing": [
                "Gampang banget kan?",
                "Siapa tau berguna buat kalian!",
                "Yuk cobain juga!",
            ]
        },
        "comparison": {
            "structure": [
                "hook_comparison", "product_a", "product_b",
                "head_to_head", "price_war", "winner", "cta"
            ],
            "opening": [
                "{product_a} vs {product_b}, mana yang lebih bagus?",
                "Jangan salah pilih! Ini perbandingan {product_a} sama {product_b}",
                "Gue bandingin {product_a} dan {product_b} biar kalian gak nyesel!",
            ],
            "closing": [
                "Menurut gue {winner} lebih unggul!",
                "Dah jelas {winner} juaranya!",
            ]
        },
        "behind_scenes": {
            "structure": [
                "hook_bts", "setup", "process", "struggle",
                "result", "lesson", "inspiration", "cta"
            ],
            "opening": [
                "Ini dia behind the scene konten {product}!",
                "Proses bikin konten {product} ternyata...",
                "Kalian gak bakal percaya gimana prosesnya!",
            ],
            "closing": [
                "Gimana? Keren kan prosesnya?",
                "Yang penting hasilnya maksimal!",
            ]
        },
        "challenge": {
            "structure": [
                "challenge_hook", "rules", "attempt", "struggle",
                "result", "reaction", "nominate", "cta"
            ],
            "opening": [
                "Challenge: {challenge} dengan {product}!",
                "Gue tantang diri gue pake {product} selama {days} hari!",
                "30 hari pake {product}, ini hasilnya!",
            ],
            "closing": [
                "Cobain challenge-nya! Tag gue ya!",
                "Seru banget! Cobain juga!",
            ]
        }
    }

    def __init__(self, content_bank_v2):
        self.bank = content_bank_v2

    def create_series_plan(self, product: str, niche: str, platform: str = "tiktok",
                           total_episodes: int = 10, interval_hours: int = 24) -> dict:
        """Create a complete series plan from templates."""
        # Pick template types based on niche
        if niche in ("skincare", "makeup", "beauty"):
            types = ["review", "tutorial", "comparison", "behind_scenes", "challenge"]
        elif niche in ("gadget", "tech", "digital"):
            types = ["review", "comparison", "tutorial", "behind_scenes"]
        elif niche in ("fashion", "muslim"):
            types = ["review", "tutorial", "challenge", "behind_scenes"]
        elif niche in ("food", "kuliner"):
            types = ["review", "tutorial", "challenge"]
        else:
            types = ["review", "tutorial", "comparison"]

        # Generate episode plan
        episodes = []
        for i in range(total_episodes):
            ep_type = random.choice(types)
            template = self.TEMPLATES[ep_type]
            opening = random.choice(template["opening"])
            closing = random.choice(template["closing"])

            episode = {
                "number": i + 1,
                "type": ep_type,
                "template": template["structure"],
                "opening_hook": opening.format(product=product, problem="kulit kusam", challenge="pakai", days=7, product_a=product, product_b="kompetitor", winner=product),
                "closing": closing.format(product=product, winner=product),
                "scheduled_hours": i * interval_hours,
            }
            episodes.append(episode)

        plan = {
            "product": product,
            "niche": niche,
            "platform": platform,
            "total_episodes": total_episodes,
            "interval_hours": interval_hours,
            "total_duration_days": total_episodes * interval_hours / 24,
            "episodes": episodes,
        }

        # Save to bank
        series_id = self.bank.create_series(
            name=f"{product} Series",
            product_id=0,
            platform=platform,
            total_episodes=total_episodes,
            episode_interval_hours=interval_hours,
            tags=[niche, platform],
            template=plan,
        )
        plan["series_id"] = series_id
        return plan

    def get_next_episode_script(self, ai_router, episode: dict, product: str,
                                 influencer: dict, platform: str) -> str:
        """Generate script for a specific episode using AI."""
        structure = "\n".join([f"- {s}" for s in episode["template"]])
        prompt = (
            f"Buat script UGC untuk {product} episode {episode['number']} "
            f"({episode['type']}) sebagai {influencer['name']}.\n\n"
            f"Hook: {episode['opening_hook']}\n"
            f"Penutup: {episode['closing']}\n\n"
            f"Struktur konten:\n{structure}\n\n"
            f"Platform: {platform}\n"
            f"Bahasa Indonesia. Durasi 30-60 detik. Gaya ngobrol santai."
        )
        return ai_router.chat(prompt)
