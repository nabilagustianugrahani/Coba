"""Content recycler — remix top performers into fresh variations."""
import json, logging, random, hashlib
from typing import Optional

log = logging.getLogger(__name__)

REFRESH_PROMPTS = [
    "Ubah sudut pandang jadi orang pertama",
    "Buat versi lebih pendek (15 detik)",
    "Tambah elemen storytelling",
    "Ubah gaya jadi lebih formal",
    "Buat versi Q&A dari konten ini",
    "Tambahkan humor ringan",
    "Ubah hook-nya pakai pertanyaan",
    "Buat versi 'day in the life'",
    "Ubah format jadi listicle",
    "Tambah fakta menarik di tengah",
]


class ContentRecycler:
    """Remix top-performing content into fresh variations."""

    def __init__(self, bank_v2):
        self.bank = bank_v2

    def find_recycle_candidates(self, platform: str = "", min_engagement: float = 2.0,
                                 limit: int = 10) -> list:
        """Find top performing content that should be remixed."""
        top = self.bank.get_top_performing(platform, days=30, limit=limit)
        return [c for c in top if c.get("engagement_score", 0) >= min_engagement]

    def generate_variations(self, ai_router, content: dict, count: int = 3,
                             platform: str = "") -> list:
        """Create *count* variations of a top content piece."""
        variations = []
        prompts_used = random.sample(REFRESH_PROMPTS, min(count, len(REFRESH_PROMPTS)))

        for prompt in prompts_used:
            try:
                variation = self._remix_one(ai_router, content, prompt, platform or content.get("platform", "tiktok"))
                if variation:
                    variations.append(variation)
            except Exception as e:
                log.warning("Remix failed: %s", e)

        return variations

    def _remix_one(self, ai_router, content: dict, instruction: str, platform: str) -> Optional[dict]:
        """Generate one remixed version."""
        original_script = content.get("script", "")
        original_hook = content.get("hook", "")
        hashtags = json.loads(content.get("hashtags", "[]"))

        prompt = (
            f"Remix konten UGC ini dengan instruksi: {instruction}\n\n"
            f"Original hook: {original_hook}\n"
            f"Original script:\n{original_script}\n\n"
            f"Buat versi baru yang fresh untuk {platform}.\n"
            f"Bahasa Indonesia. Durasi 30-60 detik."
        )

        new_script = ai_router.chat(prompt)
        if not new_script:
            return None

        new_hook = new_script.split("\n")[0][:60] if new_script else original_hook

        # Mix old hashtags with some new ones
        new_hashtag_prompt = f"Generate 5 hashtag baru untuk konten remix ini: {new_hook}. Pisahkan dengan koma."
        new_raw = ai_router.chat(new_hashtag_prompt)
        new_hashtags = [h.strip().lstrip("#") for h in new_raw.split(",") if h.strip()]
        mixed = list(set(hashtags + new_hashtags))[:10]

        return {
            "hook": new_hook,
            "script": new_script,
            "hashtags": mixed,
            "is_recycle": True,
            "source_content_id": content["id"],
            "remix_instruction": instruction,
            "platform": platform,
        }

    def auto_recycle(self, ai_router, platform: str = "", min_engagement: float = 2.0,
                      variations_per: int = 2) -> list:
        """Auto-find top content and generate variations."""
        candidates = self.find_recycle_candidates(platform, min_engagement)
        log.info("Found %d recycle candidates", len(candidates))

        all_variations = []
        for c in candidates[:5]:  # Process top 5
            log.info("Recycling content #%d (score=%.1f)", c["id"], c.get("engagement_score", 0))
            vars = self.generate_variations(ai_router, c, count=variations_per, platform=platform)
            for v in vars:
                content_id = self.bank.add_content(
                    hook=v["hook"],
                    script=v["script"],
                    platform=v["platform"],
                    hashtags=v["hashtags"],
                    influencer_id=c.get("influencer_id"),
                    product_id=c.get("product_id"),
                    status="draft",
                    is_recycle=True,
                    source_content_id=c["id"],
                    tags=["recycle", platform],
                )
                v["content_id"] = content_id
                all_variations.append(v)

        log.info("Generated %d recycled variations", len(all_variations))
        return all_variations

    def get_recycle_stats(self) -> dict:
        """Get stats about recycled content performance."""
        conn = self.bank._connect()
        try:
            original = conn.execute(
                "SELECT COUNT(*) FROM content_v2 WHERE is_recycle=0 AND views > 0"
            ).fetchone()[0]
            recycled = conn.execute(
                "SELECT COUNT(*) FROM content_v2 WHERE is_recycle=1 AND views > 0"
            ).fetchone()[0]
            orig_avg = conn.execute(
                "SELECT AVG(engagement_score) FROM content_v2 WHERE is_recycle=0 AND engagement_score>0"
            ).fetchone()[0] or 0
            rec_avg = conn.execute(
                "SELECT AVG(engagement_score) FROM content_v2 WHERE is_recycle=1 AND engagement_score>0"
            ).fetchone()[0] or 0
            return {
                "original_content": original,
                "recycled_content": recycled,
                "original_avg_engagement": round(orig_avg, 2),
                "recycled_avg_engagement": round(rec_avg, 2),
                "improvement_pct": round((rec_avg - orig_avg) / max(orig_avg, 0.01) * 100, 1),
            }
        finally:
            conn.close()
