"""UGC Mass Production — one command → 100 viral-ready UGC videos."""
import os, json, time, random, logging, concurrent.futures, re
from datetime import datetime
from typing import Optional

from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)


class UGCMassProduction:
    """Factory for mass-producing UGC content at scale.

    Flow: generate scripts → generate voiceovers → compose videos → queue → post
    All steps run in parallel with configurable worker counts.
    """

    def __init__(self, output_dir: str = "output/videos/mass", max_workers: dict = None):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.max_workers = max_workers or {
            "scripts": 20,   # parallel AI calls
            "videos": 4,     # parallel video rendering (CPU-bound)
            "posts": 3,      # parallel posting
        }

    # ── Templates ────────────────────────────────────────────────
    UGC_TEMPLATES = {
        "honest_review": {
            "angle": "jujur tanpa drama",
            "structure": ["Hook", "Kenalan sama produk", "First impression", "Dipakai rutin", "Hasil", "Kesimpulan", "CTA"],
        },
        "storytelling": {
            "angle": "cerita personal relateable",
            "structure": ["Masalah", "Ketemu produk", "Pake pertama", "Transformasi", "Testimoni", "CTA"],
        },
        "comparison": {
            "angle": "sebelum-sesudah / vs kompetitor",
            "structure": ["Hook perbandingan", "Produk A", "Produk B", "Head to head", "Pemenang", "CTA"],
        },
        "tutorial_hack": {
            "angle": "tips & trik rahasia",
            "structure": ["Hook hack", "Yang salah selama ini", "Cara bener", "Hasil maksimal", "Pro tip", "CTA"],
        },
        "challenge": {
            "angle": "tantangan X hari",
            "structure": ["Hook challenge", "Day 1", "Day 3", "Day 7", "Hasil akhir", "CTA"],
        },
        "myth_busting": {
            "angle": "mitos vs fakta",
            "structure": ["Mitos umum", "Fakta sebenarnya", "Bukti nyata", "Penjelasan", "Kesimpulan", "CTA"],
        },
        "asmr_unboxing": {
            "angle": "ASMR unboxing satisfying",
            "structure": ["Unboxing", "Look pertama", "Tekstur", "Coba langsung", "First reaction", "CTA"],
        },
        "day_in_life": {
            "angle": "daily routine with product",
            "structure": ["Pagi", "Pertengahan hari", "Sore", "Malam", "Refleksi", "CTA"],
        },
    }

    UGC_HOOKS = {
        "skincare": [
            "Jangan beli {product} sebelum nonton ini!",
            "Dokter bilang {product} ini berbahaya!",
            "Gue pake {product} selama 30 hari, ini hasilnya...",
            "{product} bikin gue shock!",
            "Ini skincare termurah yang ever gue cobain!",
        ],
        "fashion": [
            "Outfit pake {product} langsung disukai gebetan!",
            "{product} ini bikin lo keliatan kaya!",
            "Gak nyangka {product} sekualitas ini!",
            "Styling {product} untuk pemula!",
            "Review {product}: worth it atau overrated?",
        ],
        "food": [
            "Resep {product} paling enak se-Indonesia!",
            "Gue coba {product} viral, ini kejujuran!",
            "Berapa harga {product}? Jawabannya bikin kaget!",
            "Ini {product} terenak yang pernah gue makan!",
        ],
        "tech": [
            "{product} review paling jujur!",
            "5 fitur {product} yang gak lo tau!",
            "Apakah {product} worth it? Gue spill semua!",
            "Ini dia {product} yang lagi viral di TikTok!",
        ],
        "general": [
            "STOP! Jangan beli {product} kalo belum nonton ini!",
            "Gue baru nemu {product} yang bikin nagih!",
            "Review {product} dari pembeli beneran!",
            "Ini alasan kenapa {product} lagi hits!",
            "Coba {product} dulu baru percaya!",
        ],
    }

    UGC_CTA = [
        "Komen pendapat lo di bawah!",
        "Share ke temen yang butuh!",
        "Follow buat review lainnya!",
        "Save dulu biar gak ilang!",
        "Tag temen lo yang harus liat ini!",
        "Yang udah coba, komen dong!",
    ]

    def get_hooks_for_niche(self, niche: str, product: str, count: int = 5) -> list:
        hooks_pool = self.UGC_HOOKS.get(niche, self.UGC_HOOKS["general"])
        return [h.format(product=product) for h in random.sample(hooks_pool, min(count, len(hooks_pool)))]

    # ── Script Generation (Parallel) ─────────────────────────────
    def generate_scripts(self, ai_router, product: str, niche: str, count: int,
                          platforms: list = None, hooks: list = None) -> list:
        """Generate *count* unique UGC scripts in parallel."""
        platforms = platforms or ["tiktok"]
        hooks = hooks or self.get_hooks_for_niche(niche, product, count)
        influencers_pool = ["sari", "budi", "dian", "rudi", "intan", "agus", "dewi", "fikri", "rina", "tono"]

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self.max_workers["scripts"], count)
        ) as pool:
            futures = []
            for i in range(count):
                template = random.choice(list(self.UGC_TEMPLATES.values()))
                influencer = random.choice(influencers_pool)
                platform = random.choice(platforms)
                hook = hooks[i % len(hooks)]
                gender = "female" if influencer in ["sari", "dian", "intan", "dewi", "rina"] else "male"

                prompt = (
                    f"[INST] Tulis SCRIPT UGC EPISODE #{i+1} untuk produk '{product}'.\n\n"
                    f"Influencer: {influencer} ({gender})\n"
                    f"Platform: {platform}\n"
                    f"Hook: \"{hook}\"\n"
                    f"Angle: {template['angle']}\n"
                    f"Struktur: {', '.join(template['structure'])}\n"
                    f"CTA: {random.choice(self.UGC_CTA)}\n"
                    f"Durasi: 30-60 detik | Bahasa: Indonesia santai, natural\n\n"
                    f"RULES:\n"
                    f"- TULIS ONLY the script, NO intro/penjelasan/formatting\n"
                    f"- Langsung dialog dari influencer, jangan pake tanda petik\n"
                    f"- Natural, kayak ngomong temen, include filler kayak 'nih', 'si', 'deh'\n"
                    f"- Akhiri dengan CTA di atas\n"
                    f"- Every word harus bisa diucapkan (buat voiceover) [/INST]"
                )

                futures.append(pool.submit(
                    self._gen_script, ai_router, prompt, {
                        "influencer": influencer, "gender": gender,
                        "platform": platform, "hook": hook,
                        "angle": template["angle"], "template": template["structure"],
                    }
                ))

            results = []
            for fut in concurrent.futures.as_completed(futures):
                try:
                    r = fut.result()
                    if r:
                        results.append(r)
                except Exception as e:
                    log.warning("Script gen failed: %s", e)

        # Sort to maintain some semblance of order
        return results

    @staticmethod
    def _clean_script(raw: str) -> str:
        lines = raw.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r'^(berikut|tentu|oke|ok|baik|ini dia|halo|hai|hallo)', stripped, re.I):
                continue
            if re.match(r'^##?\s', stripped):
                continue
            if re.match(r'^\[/', stripped):
                continue
            cleaned.append(stripped)
        return "\n".join(cleaned) if cleaned else raw

    def _gen_script(self, ai_router, prompt: str, meta: dict) -> Optional[dict]:
        try:
            raw = ai_router.chat(prompt)
            if not raw or len(raw) < 30:
                return None
            script = self._clean_script(raw)

            # Generate hashtags
            h_prompt = f"Generate 8 hashtag. Format: #tag1 #tag2 #tag3 (NO other text). Konten: {meta['hook']}"
            h_raw = ai_router.chat(h_prompt)
            hashtags = re.findall(r'#(\w+)', h_raw)[:8]
            if not hashtags:
                hashtags = [h.strip().lstrip("#") for h in h_raw.replace("\n", ",").split(",") if h.strip()][:8]

            return {
                "script": script,
                "hook": meta["hook"],
                "influencer": meta["influencer"],
                "gender": meta["gender"],
                "platform": meta["platform"],
                "angle": meta.get("angle", ""),
                "hashtags": hashtags,
                "add_intro": True,
                "add_outro": True,
            }
        except Exception as e:
            log.warning("_gen_script error: %s", e)
            return None

    # ── Full Pipeline ─────────────────────────────────────────────
    def run(
        self,
        ai_router,
        product: str,
        niche: str = "general",
        count: int = 50,
        platforms: list = None,
        product_image: str = "",
        generate_video: bool = False,
        auto_post: bool = False,
        theme: str = "default",
        watermark: str = "",
        use_affiliate: bool = True,
        affiliate_niche: str = "",
    ) -> dict:
        """Run the complete UGC mass production pipeline.

        Returns stats dict with paths to all generated assets.
        """
        start = time.time()

        # Phase 1: Generate scripts
        log.info("📝 Phase 1: Generating %d scripts...", count)
        scripts = self.generate_scripts(ai_router, product, niche, count, platforms)
        log.info("✅ %d scripts generated", len(scripts))

        # Phase 1.5: Auto affiliate
        affiliate_matched = 0
        if use_affiliate and scripts:
            try:
                from ugc_ai_overpower.core.affiliator import Affiliator
                aff = Affiliator()
                aff_niche = affiliate_niche or niche or product
                matches = aff.run_pipeline(scripts, aff_niche, ai_router)
                for m in matches:
                    if m.injected_script:
                        scripts[m.script_index]["script"] = m.injected_script
                        scripts[m.script_index]["affiliate_link"] = m.affiliate_link
                        scripts[m.script_index]["affiliate_product"] = m.product.name
                        affiliate_matched += 1
            except Exception as e:
                log.warning("Affiliate pipeline skipped: %s", e)
        log.info("💰 %d scripts matched with affiliate products", affiliate_matched)

        # Phase 2: Generate videos
        videos = []
        if generate_video and scripts:
            log.info("🎬 Phase 2: Generating %d videos...", len(scripts))
            use_editor = skynet_config.get("avatar", "use_video_editor", default=True)
            face_image = skynet_config.get("avatar", "face_image", default="")
            if face_image and not os.path.exists(face_image):
                face_image = ""
            try:
                if use_editor:
                    self._render_with_editor(scripts, product_image, face_image, niche, theme, watermark, videos)
                else:
                    self._render_with_composer(scripts, product_image, niche, theme, watermark, videos)
            except Exception as e:
                log.warning("Video generation skipped: %s", e)

        # Phase 3: Queue & post
        posted = 0
        if auto_post:
            log.info("📤 Phase 3: Auto-posting...")
            try:
                from ugc_ai_overpower.browser.content_queue import ContentQueue
                q = ContentQueue()
                for s in scripts:
                    if s.get("video_path"):
                        q.enqueue(0, s.get("platform", "tiktok"))
                        posted += 1
                log.info("✅ %d content queued for posting", posted)
            except Exception as e:
                log.warning("Auto-post failed: %s", e)

        elapsed = round(time.time() - start, 1)
        log.info("🏁 UGC Mass Production complete in %.1fs", elapsed)

        # Save manifest
        manifest = {
            "product": product,
            "niche": niche,
            "count_target": count,
            "scripts_generated": len(scripts),
            "videos_generated": len(videos),
            "affiliate_matched": affiliate_matched,
            "queued": posted,
            "elapsed_seconds": elapsed,
            "generated_at": datetime.now().isoformat(),
        }
        manifest_path = os.path.join(self.output_dir, f"manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        return manifest

    @staticmethod
    def _render_with_editor(scripts, product_image, face_image, niche, theme, watermark, videos):
        from ugc_ai_overpower.gpu.video_editor import UGCVideoEditor
        editor = UGCVideoEditor(theme=theme, watermark=watermark)
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(scripts))) as pool:
            fut_map = {}
            for i, s in enumerate(scripts):
                fut = pool.submit(
                    editor.render,
                    script=s["script"],
                    product_image=product_image or None,
                    face_image=face_image or None,
                    gender=s.get("gender", "male"),
                    niche=niche,
                )
                fut_map[fut] = i
            for fut in concurrent.futures.as_completed(fut_map):
                idx = fut_map[fut]
                try:
                    path = fut.result()
                    if path:
                        scripts[idx]["video_path"] = path
                        videos.append(path)
                except Exception as e:
                    log.warning("Editor video %d failed: %s", idx, e)

    @staticmethod
    def _render_with_composer(scripts, product_image, niche, theme, watermark, videos):
        from ugc_ai_overpower.gpu.video_composer import VideoComposer
        vc = VideoComposer(watermark_text=watermark)
        if theme:
            vc.set_theme(theme)
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(scripts))) as pool:
            fut_map = {}
            for i, s in enumerate(scripts):
                fut = pool.submit(
                    vc.create_ugc_video,
                    script=s["script"],
                    influencer=s["influencer"],
                    product_image=product_image or None,
                    niche=niche,
                    gender=s.get("gender", "male"),
                    add_intro=s.get("add_intro", True),
                    add_outro=s.get("add_outro", True),
                    theme_override=theme if theme != "default" else None,
                )
                fut_map[fut] = i
            for fut in concurrent.futures.as_completed(fut_map):
                idx = fut_map[fut]
                try:
                    path = fut.result()
                    if path:
                        scripts[idx]["video_path"] = path
                        videos.append(path)
                except Exception as e:
                    log.warning("Composer video %d failed: %s", idx, e)
