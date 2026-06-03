import json
import logging
import os
import threading
from typing import Optional

log = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, bank, ai_router):
        self.bank = bank
        self.ai = ai_router
        from ugc_ai_overpower.mcp_server.tools.influencer_tools import InfluencerManager
        from ugc_ai_overpower.core.psychology import PsychologyEngine
        from ugc_ai_overpower.mcp_server.tools.scraper_tools import ScraperTools
        self.influencer_mgr = InfluencerManager()
        self.psychology = PsychologyEngine()
        self.scraper = ScraperTools()

    def analyze_market(self, product):
        return self.ai.analyze_product(product)

    def find_products(self, keyword):
        return self.scraper.search_best_commission(keyword)

    def plan_campaign(self, product):
        group, group_info = self.psychology.get_target_group(product)
        influencers = self.influencer_mgr.select_for_campaign(product)
        triggers = self.psychology.get_triggers_for_product(product)

        return {
            "product": product,
            "target_group": group,
            "target_description": group_info["description"],
            "recommended_platforms": group_info["preferred_platforms"],
            "psychology_triggers": [t["name"] for t in triggers],
            "assigned_influencers": [i["name"] for i in influencers[:3]],
            "total_content_planned": len(influencers) * 2,
        }

    def generate_content_batch(self, product, influencer):
        group, _ = self.psychology.get_target_group(product)
        platform = "tiktok"
        prompt = f"Buat script UGC untuk {product} sebagai {influencer['name']} ({influencer['personality']}). Gaya: {influencer['voice_style']}. Platform: {platform}. Bahasa Indonesia."
        script = self.ai.chat(prompt)
        hook = script.split("\n")[0][:50] if script else f"Review {product}"
        hashtag_prompt = f"Generate 8 hashtag TikTok trending Indonesia untuk niche {influencer['niche']}. Pisahkan dengan koma."
        hashtag_raw = self.ai.chat(hashtag_prompt)
        hashtags = [h.strip().lstrip("#") for h in hashtag_raw.split(",") if h.strip()]
        return {
            "influencer": influencer["name"],
            "platform": platform,
            "hook": hook,
            "script": script,
            "hashtags": hashtags,
            "target_group": group,
        }

    def run_campaign(self, product, niches=None, product_image=None, price=""):
        """Run a full campaign for *product*.

        When *product_image* is provided the pipeline also generates a video
        clip for each content item via :class:`VideoComposer` and enqueues it
        in the content queue as type ``"video"``.
        """
        campaign_id = self.bank.create_campaign(f"Campaign: {product}")
        plan = self.plan_campaign(product)
        product_id = self.bank.add_product(product, category=niches[0] if niches else None)
        results = []

        # Optional GPU integration.
        video_enabled = bool(product_image)
        video_composer = None
        if video_enabled:
            try:
                from ugc_ai_overpower.gpu.video_composer import VideoComposer
                video_composer = VideoComposer()
            except ImportError as exc:
                log.warning("VideoComposer unavailable – skipping video generation (%s)", exc)

        for influencer in self.influencer_mgr.select_for_campaign(product):
            content = self.generate_content_batch(product, influencer)
            content_id = self.bank.add_content(
                influencer_id=0,
                product_id=product_id,
                platform=content["platform"],
                hook=content["hook"],
                script=content["script"],
                hashtags=content["hashtags"],
            )

            # ---- GPU: auto‑generate video if product image is available ----
            if video_composer and product_image:
                try:
                    import asyncio
                    video_path = asyncio.run(
                        video_composer.create_ugc_video(
                            script=content["script"],
                            influencer=influencer["name"],
                            product_image=product_image,
                        )
                    )
                    if video_path:
                        content["video_path"] = video_path
                        try:
                            from ugc_ai_overpower.browser.content_queue import ContentQueue
                            q = ContentQueue()
                            q.enqueue(content_id, content["platform"])
                        except Exception as qe:
                            log.warning("Could not enqueue video: %s", qe)
                except Exception as ve:
                    log.warning("Video generation failed for %s: %s", influencer["name"], ve)

            results.append(content)
            self.bank.update_content_status(content_id, "ready")

        # ── Notion sync (non‑blocking) ─────────────────────────────
        notion_synced = False
        try:
            import subprocess, json as _json
            # Search for existing campaign in Notion
            search_cmd = ["notion", "search", product, "--output", "json", "--quiet"]
            search_result = subprocess.run(search_cmd, capture_output=True, text=True, timeout=15)
            if search_result.returncode == 0 and search_result.stdout.strip():
                pages = _json.loads(search_result.stdout)
                existing_ids = [p["id"] for p in pages.get("data", []) if p.get("type") == "page"]
                if existing_ids:
                    log.info("Notion: found existing campaign %s -> %s", product, existing_ids[0])
                    notion_synced = True
                else:
                    log.info("Notion: no existing campaign found for '%s', skip sync", product)
            else:
                log.info("Notion: search returned no results for '%s'", product)
        except Exception as ne:
            log.warning("Notion search error: %s", ne)

        # ── Auto-enqueue videos to ContentQueue ────────────────────
        queued = []
        try:
            from ugc_ai_overpower.browser.content_queue import ContentQueue
            q = ContentQueue()
            for c in results:
                if c.get("video_path"):
                    qid = q.enqueue(content_id=0, platform=c.get("platform", "tiktok"))
                    queued.append(qid)
                    log.info("Enqueued content to queue id=%d", qid)
        except Exception as qe:
            log.warning("Queue enqueue error: %s", qe)

        return {
            "campaign_id": campaign_id,
            "product": product,
            "plan": plan,
            "contents": results,
            "total": len(results),
            "video_generated": video_enabled,
            "queued": len(queued),
            "notion_synced": notion_synced,
        }

    # ------------------------------------------------------------------
    # New queue‑related methods (Phase 2)
    # ------------------------------------------------------------------
    def schedule_content(self, content_id: int, platform: str, scheduled_at: str = None) -> int:
        """Add a content item to the posting queue.

        Returns the queue row id.
        """
        from ugc_ai_overpower.browser.content_queue import ContentQueue

        q = ContentQueue()
        return q.enqueue(content_id, platform, scheduled_at)

    def process_queue(self, platform: str = None) -> dict:
        """Process next pending item via QueueProcessor."""
        from ugc_ai_overpower.browser.queue_processor import QueueProcessor
        return QueueProcessor().process_one(platform)

    def process_all_pending(self, platform: str = None) -> dict:
        """Process ALL pending items via QueueProcessor."""
        from ugc_ai_overpower.browser.queue_processor import QueueProcessor
        return QueueProcessor().process_all(platform)

    def auto_campaign(self, product: str, product_image: str = None, platforms: list = None) -> dict:
        """Full auto campaign: generate → video → queue → auto-post."""
        platforms = platforms or ["tiktok"]
        
        # Step 1: Run campaign (generates scripts + videos)
        logger.info("Step 1: Generating content for %s...", product)
        campaign_result = self.run_campaign(product, product_image=product_image)
        
        # Step 2: Auto-process queue
        logger.info("Step 2: Processing queue...")
        for platform in platforms:
            stats = self.process_all_pending(platform)
            logger.info("Platform %s: %s", platform, stats)
        
        return {
            "product": product,
            "campaign": campaign_result,
            "posted_to": platforms,
            "total_content": campaign_result["total"],
            "total_queued": campaign_result.get("queued", 0),
        }

    # ═══════════════════════════════════════════════════════════════
    # OVERKILL MODE — parallel × farm × series × optimizer × everything
    # ═══════════════════════════════════════════════════════════════

    def overkill_mode(
        self,
        product: str,
        count: int = 50,
        platforms: list = None,
        product_image: str = "",
        use_farm: bool = True,
        use_series: bool = True,
        use_recycle: bool = True,
        use_optimizer: bool = True,
    ) -> dict:
        """Supercharged campaign using ALL overkill features."""
        platforms = platforms or ["tiktok", "instagram"]
        start_time = __import__("time").time()
        results = {}

        # 1. Batch generate massive content
        logger.info("🔥 OVERKILL MODE: %s — generating %d pieces...", product, count)
        from ugc_ai_overpower.core.parallel import ParallelBatch
        from ugc_ai_overpower.mcp_server.tools.influencer_tools import InfluencerManager

        im = InfluencerManager()
        influencers = im.select_for_campaign(product)
        batch = ParallelBatch(max_workers=min(count, 20))
        contents = batch.generate_batch(
            self.ai, product, influencers,
            platforms=platforms, count=count
        )
        results["generated"] = len(contents)
        logger.info("✅ Generated %d scripts", len(contents))

        # 2. Generate videos in parallel if image provided
        if product_image:
            logger.info("🎬 Generating videos in parallel...")
            try:
                from ugc_ai_overpower.gpu.video_composer import VideoComposer
                vc = VideoComposer()
                video_contents = batch.generate_videos_batch(vc, contents, product_image, max_workers=min(4, count))
                for c in video_contents:
                    if c.get("video_path"):
                        try:
                            from ugc_ai_overpower.browser.content_queue import ContentQueue
                            q = ContentQueue()
                            q.enqueue(0, c.get("platform", "tiktok"))
                        except Exception:
                            pass
                results["videos"] = sum(1 for c in video_contents if c.get("video_path"))
            except Exception as ve:
                logger.warning("Video batch failed: %s", ve)
                video_contents = contents
        else:
            video_contents = contents

        # 3. Save to content bank
        from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
        bank_v2 = ContentBankV2()
        product_id = bank_v2.add_product(product)
        for c in video_contents:
            bank_v2.add_content(
                hook=c.get("hook", ""),
                script=c.get("script", ""),
                platform=c.get("platform", "tiktok"),
                hashtags=c.get("hashtags", []),
                product_id=product_id,
                status="ready",
                tags=["overkill", product.lower().replace(" ", "_")],
            )
        results["saved"] = len(video_contents)

        # 4. Series plan
        if use_series:
            try:
                from ugc_ai_overpower.core.series import SeriesEngine
                se = SeriesEngine(bank_v2)
                plan = se.create_series_plan(product, "general", platforms[0],
                                              total_episodes=min(count, 10))
                results["series_id"] = plan.get("series_id")
                logger.info("📺 Series created: %d episodes", plan["total_episodes"])
            except Exception as e:
                logger.warning("Series plan failed: %s", e)

        # 5. Recycle old content
        if use_recycle:
            try:
                from ugc_ai_overpower.core.recycler import ContentRecycler
                rc = ContentRecycler(bank_v2)
                recycled = rc.auto_recycle(self.ai, platforms[0], variations_per=2)
                results["recycled"] = len(recycled)
                logger.info("♻️ Recycled %d old content pieces", len(recycled))
            except Exception as e:
                logger.warning("Recycle failed: %s", e)

        # 6. Account farm rotation
        farm = None
        if use_farm:
            try:
                from ugc_ai_overpower.browser.farm import AccountFarm
                farm = AccountFarm()
                results["farm_stats"] = farm.get_stats()
                logger.info("👥 Farm: %d profiles available", farm.get_stats().get("healthy", 0))
            except Exception as e:
                logger.warning("Farm check failed: %s", e)

        # 7. Auto-post with farm rotation
        posted = 0
        if farm:
            from ugc_ai_overpower.browser.posters import get_poster
            for c in video_contents[:10]:  # Post first 10
                prof = farm.rotate(c.get("platform", "tiktok"))
                if not prof:
                    continue
                try:
                    poster = get_poster(c.get("platform", "tiktok"))
                    poster.set_cookie_profile(prof.name)
                    payload = {
                        "script": c.get("script", ""),
                        "video_path": c.get("video_path", ""),
                        "hashtags": c.get("hashtags", []),
                    }
                    post_result = poster.post(payload)
                    success = post_result.get("success", False)
                    farm.record_result(prof.platform, prof.name, success)
                    if success:
                        posted += 1
                    poster.cleanup()
                except Exception as e:
                    logger.warning("Post failed for %s: %s", prof.name, e)

        results["posted"] = posted
        results["elapsed_seconds"] = round(__import__("time").time() - start_time, 1)
        logger.info("🏁 OVERKILL DONE: %d generated, %d posted in %.1fs",
                    len(contents), posted, results["elapsed_seconds"])
        return results

    def run_batch(self, product: str, platforms=["tiktok", "instagram"]):
        """Generate content for *product* on each platform and enqueue it.

        This is a convenience wrapper used by the CLI command ``run_batch``.
        """
        # Generate a content batch for each platform.
        for platform in platforms:
            # Create a dummy influencer dict – in a real scenario we would pick
            # an influencer that matches the platform. Here we use the first
            # influencer from the manager.
            influencer = self.influencer_mgr.select_for_campaign(product)[0]
            batch = self.generate_content_batch(product, influencer)
            # Store the content in the DB.
            content_id = self.bank.add_content(
                influencer_id=0,
                product_id=self.bank.add_product(product),
                platform=platform,
                hook=batch["hook"],
                script=batch["script"],
                hashtags=batch["hashtags"],
            )
            # Enqueue for posting.
            self.schedule_content(content_id, platform)

    # ═══════════════════════════════════════════════════════════════
    # ENTERPRISE FEATURES — TTS, thumbnails, images, engage, trends
    # ═══════════════════════════════════════════════════════════════

    def tts_voiceover(self, script: str, gender: str = "male", output_path: str = None) -> str:
        """Generate AI voiceover for a script."""
        from ugc_ai_overpower.gpu.tts_engine import TTSEngine
        return TTSEngine().synthesize_sync(script, gender, output_path)

    def generate_thumbnail(self, hook: str, product: str = "", platform: str = "tiktok",
                           theme: str = "default", product_image: str = None) -> str:
        """Generate a branded thumbnail."""
        from ugc_ai_overpower.gpu.thumbnail import ThumbnailGenerator
        tg = ThumbnailGenerator(theme=theme)
        return tg.generate(hook, product, platform, product_image)

    def scrape_product_images(self, url: str, max_images: int = 3) -> list[str]:
        """Download product images from e-commerce URL."""
        from ugc_ai_overpower.core.product_images import ProductImageScraper
        return ProductImageScraper().scrape(url, max_images)

    def auto_engage(self, niche: str, platform: str = "tiktok",
                    likes: int = 20, follows: int = 5, comments: int = 3) -> dict:
        """Auto like/comment/follow in a niche."""
        from ugc_ai_overpower.browser.bu_engage import BUEngageAgent
        import asyncio
        agent = BUEngageAgent()
        return asyncio.run(agent.batch_engage(niche, platform, likes, follows, comments))

    def scrape_trends(self, niche: str, platform: str = "tiktok") -> dict:
        """Scrape trending hashtags and viral posts."""
        from ugc_ai_overpower.browser.bu_scraper import BUScraperAgent
        import asyncio
        agent = BUScraperAgent()
        hashtags = asyncio.run(agent.trending_hashtags(niche, 20))
        if not hashtags.success:
            return {"hashtags": [], "viral": ""}
        viral = asyncio.run(agent.viral_posts(niche, platform, 5))
        return {
            "hashtags": hashtags.output.split(", ") if hashtags.output else [],
            "viral_insights": viral.output,
        }

    def register_farm_account(self, platform: str, profile_name: str) -> dict:
        """Auto-create platform account via temp mail + browser-use."""
        from ugc_ai_overpower.browser.farm_registrar import BUFarmRegistrar
        import asyncio
        agent = BUFarmRegistrar()
        if platform == "tiktok":
            result = asyncio.run(agent.register_tiktok(profile_name))
        elif platform == "instagram":
            result = asyncio.run(agent.register_instagram(profile_name))
        else:
            return {"success": False, "error": f"Unsupported platform: {platform}"}
        return {"success": result.success, "profile": profile_name, "platform": platform,
                "output": result.output, "error": result.error}

    def render_video(self, script: str, product_image: str = None, face_image: str = None,
                      gender: str = "male", niche: str = "lifestyle", theme: str = "default",
                      watermark: str = "") -> Optional[str]:
        """Render multi-scene UGC video using UGCVideoEditor.

        Uses the new 5-scene editor by default (hook → problem → solution → testimonial → cta).
        Falls back to basic VideoComposer if editor fails.
        """
        try:
            from ugc_ai_overpower.gpu.video_editor import UGCVideoEditor
            editor = UGCVideoEditor(theme=theme, watermark=watermark)
            return editor.render(script=script, product_image=product_image,
                                 face_image=face_image, gender=gender, niche=niche)
        except Exception as e:
            log.warning("VideoEditor failed, falling back to composer: %s", e)
            from ugc_ai_overpower.gpu.video_composer import VideoComposer
            vc = VideoComposer(watermark_text=watermark)
            return vc.create_ugc_video(script=script, influencer="creator",
                                       product_image=product_image, niche=niche, gender=gender)

    def affiliate_search(self, query: str, limit: int = 10) -> list:
        """Search affiliate products from e-commerce platforms."""
        from ugc_ai_overpower.core.affiliator import Affiliator
        return Affiliator().search_products(query, limit)

    def affiliate_match(self, scripts: list, niche: str) -> list:
        """Match scripts to affiliate products and inject links."""
        from ugc_ai_overpower.core.affiliator import Affiliator
        return Affiliator().run_pipeline(scripts, niche, self.ai)

    def affiliate_catalog(self, query: str = "", limit: int = 20) -> list:
        """Search local affiliate product catalog."""
        from ugc_ai_overpower.core.affiliator import Affiliator
        return Affiliator().search_catalog(query, limit)

    def generate_avatar(self, face_image: str, script: str = None, audio_path: str = None,
                         gender: str = "male") -> Optional[str]:
        """Generate talking-head avatar video.

        Args:
            face_image: Path to face/portrait image.
            script: Text script (if no audio_path).
            audio_path: Pre-generated audio path (if no script).
            gender: Voice gender for TTS.

        Returns:
            Path to avatar MP4, or None on failure.
        """
        if not audio_path and script:
            audio_path = self.tts_voiceover(script, gender)
        if not audio_path or not os.path.exists(audio_path):
            log.error("No audio available for avatar")
            return None
        from ugc_ai_overpower.gpu.avatar_engine import AvatarEngine
        engine = AvatarEngine()
        return engine.generate_avatar(face_image, audio_path)

    def modal_deploy(self) -> dict:
        """Deploy SoulX-FlashHead to Modal GPU cloud."""
        from ugc_ai_overpower.gpu.modal_pipeline import ModalPipeline
        return ModalPipeline().deploy()

    def modal_status(self) -> dict:
        """Check Modal connection and quota."""
        from ugc_ai_overpower.gpu.modal_pipeline import ModalPipeline
        mp = ModalPipeline()
        return {
            "available": mp.is_available(),
            "quota": mp.get_quota(),
            "accounts": mp.list_accounts(),
        }

    def alert(self, message: str, severity: str = "info", source: str = ""):
        """Send alert via configured channels."""
        from ugc_ai_overpower.core.alerter import alerter
        alerter.send(message, severity, source)
