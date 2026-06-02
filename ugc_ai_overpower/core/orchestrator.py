import json
import os

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

    def run_campaign(self, product, niches=None):
        campaign_id = self.bank.create_campaign(f"Campaign: {product}")
        plan = self.plan_campaign(product)
        product_id = self.bank.add_product(product, category=niches[0] if niches else None)
        results = []
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
            results.append(content)
            self.bank.update_content_status(content_id, "ready")
        return {
            "campaign_id": campaign_id,
            "product": product,
            "plan": plan,
            "contents": results,
            "total": len(results),
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

    def process_queue(self, platform: str = None) -> None:
        """Fetch the next pending item (optionally filtered by *platform*)
        and dispatch it to the appropriate poster implementation.
        """
        from ugc_ai_overpower.browser.content_queue import ContentQueue
        from ugc_ai_overpower.browser.posters import get_poster

        q = ContentQueue()
        item = q.dequeue(platform)
        if not item:
            return  # nothing to do
        # Load content details from the main content table.
        content_row = self.bank.get_all()  # placeholder – real method would query by id
        # For simplicity we re‑use the bank's content fetch – here we just mock.
        # In a full implementation ``ContentBank`` would expose a ``get_content``.
        # Assume the content dict contains the fields required by the poster.
        # We'll build a minimal dict for the demo.
        poster = get_poster(item["platform"])
        try:
            # Load the content record – using bank's content table directly.
            # This pseudo‑implementation just passes a static dict.
            content_data = {
                "script": "Demo script",
                "video_path": "demo.mp4",
                "hashtags": [],
            }
            result = poster.post(content_data)
            if result.get("success"):
                q.mark_done(item["id"], result.get("post_url", ""))
            else:
                q.mark_failed(item["id"], result.get("error", "unknown error"))
        finally:
            poster.cleanup()

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
