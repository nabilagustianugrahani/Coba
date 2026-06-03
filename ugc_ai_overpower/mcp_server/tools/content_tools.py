"""MCP tools for content operations — series, recycle, parallel, optimizer."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ugc_ai_overpower.core.series import SeriesEngine
from ugc_ai_overpower.core.recycler import ContentRecycler
from ugc_ai_overpower.core.parallel import ParallelBatch
from ugc_ai_overpower.core.optimizer import AnalyticsOptimizer
from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
from ugc_ai_overpower.mcp_server.tools.ai_tools import AIRouter
from ugc_ai_overpower.mcp_server.tools.influencer_tools import InfluencerManager


class ContentTools:
    def __init__(self):
        self.bank = ContentBankV2()
        self.series = SeriesEngine(self.bank)
        self.recycler = ContentRecycler(self.bank)
        self.optimizer = AnalyticsOptimizer(self.bank)
        self.batch = ParallelBatch(max_workers=10)
        self.ai = AIRouter(
            os.getenv("ROUTER_URL", "http://localhost:20128"),
            os.getenv("ROUTER_KEY", ""),
        )
        self.influencer_mgr = InfluencerManager()

    # ── Series tools ─────────────────────────────────────────────
    def plan_series(self, product: str, niche: str, platform: str = "tiktok",
                    episodes: int = 10) -> dict:
        return self.series.create_series_plan(product, niche, platform, episodes)

    def generate_episode(self, series_id: int, episode_number: int,
                          product: str, influencer_name: str, platform: str = "tiktok") -> dict:
        plan_series = self.bank.get_series(series_id)
        episodes = plan_series.get("template_json", {})
        influencers = self.influencer_mgr.get_by_name(influencer_name)

        return {
            "series_id": series_id,
            "episode": episode_number,
            "script": self.series.get_next_episode_script(
                self.ai, episodes if isinstance(episodes, list) else {},
                product, influencers[0] if influencers else {}, platform
            ),
        }

    # ── Recycle tools ────────────────────────────────────────────
    def find_recycle_candidates(self, platform: str = "", min_engagement: float = 2.0) -> list:
        return self.recycler.find_recycle_candidates(platform, min_engagement)

    def auto_recycle(self, platform: str = "") -> list:
        return self.recycler.auto_recycle(self.ai, platform)

    # ── Batch tools ──────────────────────────────────────────────
    def batch_generate(self, product: str, count: int = 20, platforms: str = "tiktok,instagram") -> list:
        influencers = self.influencer_mgr.select_for_campaign(product)
        return self.batch.generate_batch(
            self.ai, product, influencers,
            platforms=platforms.split(","), count=count
        )

    # ── Optimizer tools ──────────────────────────────────────────
    def setup_ab_test(self, product: str, platform: str = "tiktok") -> dict:
        return self.optimizer.setup_ab_test(self.ai, product, platform)

    def analyze_times(self, days: int = 30) -> dict:
        return self.optimizer.analyze_posting_times(days)

    def predict(self, hook: str, platform: str = "tiktok", hour: int = 12) -> dict:
        return self.optimizer.predict_performance(hook, platform, hour)

    # ── Search tools ─────────────────────────────────────────────
    def search(self, query: str, limit: int = 10) -> list:
        return self.bank.search_content(query, limit)

    def get_top(self, platform: str = "", limit: int = 10) -> list:
        return self.bank.get_top_performing(platform, limit=limit)

    # ── Stats ────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        from ugc_ai_overpower.browser.farm import AccountFarm
        farm = AccountFarm()
        return {
            "content_bank": self.bank.get_stats(),
            "recycle_stats": self.recycler.get_recycle_stats(),
            "farm_stats": farm.get_stats(),
            "batch_stats": self.batch.get_stats(),
        }


# Singleton
content_tools = ContentTools()
