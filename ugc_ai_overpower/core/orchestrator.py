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