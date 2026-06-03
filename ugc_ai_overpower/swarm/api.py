"""Swarm REST API — FastAPI server exposing all swarm agents over HTTP.

Endpoints:
  POST /campaign           → launch campaign
  POST /scripts/generate   → generate scripts
  POST /affiliates/match   → match affiliates
  POST /videos/render      → render videos
  POST /content/post       → post to platforms
  POST /engage             → auto-engage
  GET  /analytics          → get reports
  POST /predator/scavenge  → scavenge trends (real)
  POST /predator/zombie    → generate viral script
  POST /predator/competitor → competitor analysis
  POST /predator/mine      → mine buying signals
  POST /predator/monitor   → monitor brand
  GET  /status             → swarm health
  POST /heal               → trigger auto-heal

Usage:
  python -m swarm.api
  # or call from code: SwarmAPI().run()
"""
import json, logging, threading, uvicorn
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)

# ── Request/Response Models ────────────────────────────────────────────────

class CampaignRequest(BaseModel):
    product: str
    niche: str = "general"
    count: int = 5
    platforms: list[str] = ["tiktok"]
    generate_video: bool = True
    use_affiliate: bool = True

class ScriptRequest(BaseModel):
    product: str
    niche: str = "general"
    count: int = 10
    platform: str = "tiktok"

class AffiliateRequest(BaseModel):
    niche: str = "general"
    script_count: int = 10

class VideoRequest(BaseModel):
    campaign_id: str
    scripts: list[str]
    niche: str = "general"

class PostRequest(BaseModel):
    campaign_id: str
    video_paths: list[str]
    platforms: list[str] = ["tiktok"]

class EngageRequest(BaseModel):
    niche: str = "general"
    platform: str = "tiktok"
    likes: int = 10
    follows: int = 3
    comments: int = 2

class ScavengeRequest(BaseModel):
    niche: str = "general"
    platform: str = "tiktok"
    count: int = 20

class ZombieRequest(BaseModel):
    product: str
    niche: str = "general"

class CompetitorRequest(BaseModel):
    username: str
    platform: str = "tiktok"

class MineCommentsRequest(BaseModel):
    post_url: str
    platform: str = "tiktok"
    brand: str = ""

class MonitorBrandRequest(BaseModel):
    brand: str
    platform: str = "tiktok"


class SwarmAPI:
    """FastAPI-based REST API for the entire swarm."""

    def __init__(self, ai_router=None, host: str = "0.0.0.0", port: int = 9111):
        self.ai_router = ai_router
        self.host = host
        self.port = port
        self.app = FastAPI(title="Skynet Swarm API", version="2.0.0")
        self._register_routes()
        self._server: Optional[uvicorn.Server] = None

    def _register_routes(self):
        app = self.app

        @app.get("/")
        def root():
            return {
                "service": "Skynet Swarm API",
                "version": "2.0.0",
                "endpoints": [
                    "POST /campaign", "POST /scripts/generate",
                    "POST /affiliates/match", "POST /videos/render",
                    "POST /content/post", "POST /engage",
                    "GET /analytics", "GET /status",
                    "POST /predator/scavenge", "POST /predator/zombie",
                    "POST /predator/competitor", "POST /predator/mine",
                    "POST /predator/monitor", "POST /heal",
                ],
            }

        @app.post("/campaign")
        def api_campaign(req: CampaignRequest):
            from swarm.message_bus import MessageBus
            bus = MessageBus()
            msg_id = bus.send("api", "orchestrator", "campaign", req.model_dump())
            return {"status": "dispatched", "message_id": msg_id, "product": req.product}

        @app.post("/scripts/generate")
        def api_generate_scripts(req: ScriptRequest):
            from swarm.agents.script_writer_agent import ScriptWriterAgent
            agent = ScriptWriterAgent(ai_router=self.ai_router)
            result = agent.handle_generate_scripts({"payload": {
                "campaign_id": f"api_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "product": req.product, "niche": req.niche,
                "count": req.count, "platforms": [req.platform],
            }})
            return result

        @app.post("/affiliates/match")
        def api_match_affiliates(req: AffiliateRequest):
            from swarm.agents.affiliator_agent import AffiliatorAgent
            agent = AffiliatorAgent()
            result = agent.handle_match_products({"payload": {
                "campaign_id": "api", "niche": req.niche,
                "scripts": [{"script": f"s{i}"} for i in range(req.script_count)],
            }})
            return result

        @app.post("/videos/render")
        def api_render_videos(req: VideoRequest):
            from swarm.agents.video_producer_agent import VideoProducerAgent
            agent = VideoProducerAgent()
            scripts = [{"script": s, "gender": "female", "influencer": "creator",
                        "hashtags": [], "angle": "review"} for s in req.scripts]
            result = agent.handle_render_videos({"payload": {
                "campaign_id": req.campaign_id, "scripts": scripts, "niche": req.niche,
            }})
            return result

        @app.post("/content/post")
        def api_post_content(req: PostRequest):
            from swarm.agents.poster_agent import PosterAgent
            agent = PosterAgent()
            result = agent.handle_post_videos({"payload": {
                "campaign_id": req.campaign_id, "videos": req.video_paths,
                "platforms": req.platforms,
            }})
            return result

        @app.post("/engage")
        def api_engage(req: EngageRequest):
            from swarm.agents.engagement_agent import EngagementAgent
            agent = EngagementAgent()
            result = agent.handle_engage_now({"payload": {"niche": req.niche}})
            return {"niche": req.niche, "status": result.get("status")}

        @app.get("/analytics")
        def api_analytics():
            from swarm.agents.analytics_agent import AnalyticsAgent
            from swarm.message_bus import MessageBus
            bus = MessageBus()
            return {
                "bus_health": bus.health(),
                "orchestrator_campaigns": [],
            }

        @app.get("/status")
        def api_status():
            from swarm.message_bus import MessageBus
            bus = MessageBus()
            return {
                "status": "online",
                "bus": bus.health(),
                "agents": [
                    "orchestrator", "script_writer", "affiliator",
                    "video_producer", "poster", "engagement",
                    "analytics", "predator",
                ],
                "timestamp": datetime.now().isoformat(),
            }

        @app.post("/predator/scavenge")
        def api_predator_scavenge(req: ScavengeRequest):
            from swarm.agents.predator_scraper import RealTrendScraper
            scraper = RealTrendScraper(ai_router=self.ai_router)
            hooks = scraper.scavenge_viral_hooks(req.niche, req.platform, req.count)
            dna = scraper.analyze_viral_dna(req.niche, hooks)
            return {
                "niche": req.niche,
                "hooks_found": len(hooks),
                "top_hooks": [h["hook"][:100] for h in hooks[:5]],
                "dna_analysis": dna,
            }

        @app.post("/predator/zombie")
        def api_predator_zombie(req: ZombieRequest):
            from swarm.agents.predator_scraper import RealTrendScraper
            scraper = RealTrendScraper(ai_router=self.ai_router)
            hooks = scraper.scavenge_viral_hooks(req.niche, "tiktok", 10)
            dna = scraper.analyze_viral_dna(req.niche, hooks)
            script = scraper.generate_zombie_script(req.niche, req.product, dna)
            return {"niche": req.niche, "script": script}

        @app.post("/predator/competitor")
        def api_predator_competitor(req: CompetitorRequest):
            from swarm.agents.predator_scraper import RealTrendScraper
            scraper = RealTrendScraper(ai_router=self.ai_router)
            analysis = scraper.scavenge_competitor_strategy(req.username, req.platform)
            return analysis

        @app.post("/predator/mine")
        def api_predator_mine(req: MineCommentsRequest):
            from swarm.agents.predator_scraper import RealTrendScraper
            from swarm.agents.predator_agent import ViralDNALibrary, CommentMiner
            dna = ViralDNALibrary()
            miner = CommentMiner(dna, ai_router=self.ai_router)
            scraper = RealTrendScraper(ai_router=self.ai_router)
            comments = scraper.mine_comments_from_post(req.post_url, req.platform)
            results = miner.process_comments_batch(comments, req.platform, req.brand)
            return {"comments_scanned": len(comments), "buying_signals": results}

        @app.post("/predator/monitor")
        def api_predator_monitor(req: MonitorBrandRequest):
            from swarm.agents.predator_agent import PredatorAgent
            agent = PredatorAgent(ai_router=self.ai_router)
            result = agent.handle_monitor_brand({"payload": req.model_dump()})
            return result

        @app.post("/heal")
        def api_heal():
            from swarm.autoheal import DependencyHealer
            actions = DependencyHealer.check_and_heal()
            return {"actions_taken": actions}

    def run(self, **kwargs):
        """Start the API server in a thread."""
        host = kwargs.get("host", self.host)
        port = kwargs.get("port", self.port)

        config = uvicorn.Config(self.app, host=host, port=port, log_level="info")
        self._server = uvicorn.Server(config)

        t = threading.Thread(target=self._server.run, daemon=True, name="swarm-api")
        t.start()
        log.info("Swarm API running on http://%s:%d", host, port)
        return self._server

    def run_sync(self):
        """Blocking run (for CLI usage)."""
        uvicorn.run(self.app, host=self.host, port=self.port)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    api = SwarmAPI()
    api.run_sync()


if __name__ == "__main__":
    main()
