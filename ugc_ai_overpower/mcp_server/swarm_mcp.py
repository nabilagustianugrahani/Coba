"""Swarm MCP Server — exposes all swarm agents as MCP tools.

Any MCP-compatible client (Claude Desktop, Cursor, OpenClaw, any LLM with MCP)
can call our entire swarm. This mirrors what AiToEarn does with their MCP server.

Available tools:
  - launch_campaign       → orchestrator
  - generate_scripts      → script_writer
  - match_affiliates      → affiliator
  - render_videos         → video_producer
  - post_content          → poster
  - engage_automation     → engagement
  - get_report            → analytics
  - predator_scavenge     → predator (trend intelligence)
  - predator_zombie       → predator (viral script gen)
  - predator_competitor   → predator (competitive intel)
  - predator_mine_comments → predator (buying signal detection)
  - predator_monitor_brand → predator (brand monitoring)
"""
import json, logging, os, sys

log = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

from ugc_ai_overpower.mcp_server.tools.ai_tools import AIRouter
from ugc_ai_overpower.core.config import skynet_config
from ugc_ai_overpower.core.pipeline_engine import UGCPipelineFactory
from ugc_ai_overpower.core.gallery import Gallery
from ugc_ai_overpower.browser.social_inbox import SocialInbox
from ugc_ai_overpower.core.brand_profile import BrandProfile
from ugc_ai_overpower.core.approval_workflow import ApprovalWorkflow
from ugc_ai_overpower.browser.trend_scout import TrendScout

SWARM_SERVER_NAME = "Skynet-Swarm"

_gallery_store = None
_inbox_store = None
_brand_store = None
_approval_store = None
_trend_store = None

def _get_gallery():
    global _gallery_store
    if _gallery_store is None:
        _gallery_store = Gallery()
    return _gallery_store

def _get_inbox(ai_router=None):
    global _inbox_store
    if _inbox_store is None:
        _inbox_store = SocialInbox(ai_router=ai_router)
    return _inbox_store

def _get_brand():
    global _brand_store
    if _brand_store is None:
        _brand_store = BrandProfile()
    return _brand_store

def _get_approval():
    global _approval_store
    if _approval_store is None:
        _approval_store = ApprovalWorkflow()
    return _approval_store

def _get_trend(ai_router=None):
    global _trend_store
    if _trend_store is None:
        _trend_store = TrendScout(ai_router=ai_router)
    return _trend_store


class SwarmMCPServer:
    """FastMCP-based server exposing the entire swarm as MCP tools."""

    def __init__(self, ai_router: AIRouter = None):
        if FastMCP is None:
            raise ImportError("MCP library not installed. Run: pip install mcp")

        self.ai_router = ai_router or AIRouter(
            base_url=skynet_config.get("router", "base_url"),
            api_key=skynet_config.get("router", "api_key"),
        )
        self.mcp = FastMCP(SWARM_SERVER_NAME)
        self._register_tools()

    def _register_tools(self):
        mcp = self.mcp
        ai = self.ai_router

        # ─── Orchestrator ─────────────────────────────────────────────

        @mcp.tool(description="Launch a full UGC campaign from product name")
        def launch_campaign(product: str, niche: str = "general",
                            count: int = 5, platforms: list = None) -> str:
            """Launch a campaign: scripts → affiliates → videos → posting."""
            from swarm.message_bus import MessageBus
            bus = MessageBus()
            msg_id = bus.send("mcp", "orchestrator", "campaign", {
                "product": product, "niche": niche, "count": count,
                "platforms": platforms or ["tiktok"],
                "generate_video": True, "use_affiliate": True,
            })
            return json.dumps({"status": "dispatched", "message_id": msg_id,
                               "product": product, "niche": niche, "count": count})

        # ─── Script Writer ────────────────────────────────────────────

        @mcp.tool(description="Generate UGC scripts via AI")
        def generate_scripts(product: str, niche: str = "general",
                             count: int = 10, platform: str = "tiktok") -> str:
            """Generate N UGC scripts with hooks, angles, CTAs."""
            from swarm.agents.script_writer_agent import ScriptWriterAgent
            agent = ScriptWriterAgent(ai_router=ai)
            result = agent.handle_generate_scripts({"payload": {
                "product": product, "niche": niche, "count": count,
                "platforms": [platform],
            }})
            return json.dumps(result, indent=2, default=str)

        # ─── Affiliator ───────────────────────────────────────────────

        @mcp.tool(description="Match products to scripts with affiliate links")
        def match_affiliates(niche: str, script_count: int = 10) -> str:
            """Search and match affiliate products to scripts."""
            from swarm.agents.affiliator_agent import AffiliatorAgent
            agent = AffiliatorAgent()
            result = agent.handle_match_products({"payload": {
                "campaign_id": "mcp-campaign", "niche": niche,
                "scripts": [{"script": f"Script #{i}", "hashtags": []} for i in range(script_count)],
            }})
            return json.dumps(result, indent=2, default=str)

        # ─── Video Producer ───────────────────────────────────────────

        @mcp.tool(description="Render UGC videos from scripts")
        def render_videos(campaign_id: str, script_texts: list, niche: str = "general") -> str:
            """Render videos via Modal GPU or CPU fallback."""
            from swarm.agents.video_producer_agent import VideoProducerAgent
            agent = VideoProducerAgent()
            scripts = [{"script": s, "gender": "female", "influencer": "creator",
                        "hashtags": [], "angle": "review"} for s in script_texts]
            result = agent.handle_render_videos({"payload": {
                "campaign_id": campaign_id, "scripts": scripts, "niche": niche,
            }})
            return json.dumps(result, indent=2, default=str)

        # ─── Poster ───────────────────────────────────────────────────

        @mcp.tool(description="Post videos to social media platforms")
        def post_content(campaign_id: str, video_paths: list, platforms: list = None) -> str:
            """Post videos to TikTok/Instagram/YouTube with farm rotation."""
            from swarm.agents.poster_agent import PosterAgent
            agent = PosterAgent()
            result = agent.handle_post_videos({"payload": {
                "campaign_id": campaign_id, "videos": video_paths,
                "platforms": platforms or ["tiktok"],
            }})
            return json.dumps(result, indent=2, default=str)

        # ─── Engagement ───────────────────────────────────────────────

        @mcp.tool(description="Auto-engage on target niche content")
        def engage_automation(niche: str = "general", platform: str = "tiktok",
                              likes: int = 10, follows: int = 3, comments: int = 2) -> str:
            """Auto-like, comment, follow in target niche."""
            from swarm.agents.engagement_agent import EngagementAgent
            agent = EngagementAgent()
            result = agent.handle_engage_now({"payload": {"niche": niche}})
            return json.dumps({"niche": niche, "platform": platform,
                               "likes": likes, "follows": follows, "comments": comments,
                               "status": result.get("status", "done")})

        # ─── Analytics ────────────────────────────────────────────────

        @mcp.tool(description="Get campaign and swarm health analytics")
        def get_report() -> str:
            """Live analytics: campaign stats, queue depth, bus health."""
            from swarm.agents.analytics_agent import AnalyticsAgent
            agent = AnalyticsAgent()
            result = agent.handle_request_report({"payload": {}})
            return json.dumps(result, indent=2, default=str)

        # ─── Predator Agent ───────────────────────────────────────────

        @mcp.tool(description="Scavenge viral trends from social media")
        def predator_scavenge(niche: str = "general", platform: str = "tiktok",
                              count: int = 20) -> str:
            """Scrape trending content → extract viral hooks + patterns."""
            from swarm.agents.predator_scraper import RealTrendScraper
            scraper = RealTrendScraper(ai_router=ai)
            hooks = scraper.scavenge_viral_hooks(niche, platform, count)
            dna = scraper.analyze_viral_dna(niche, hooks)
            return json.dumps({
                "niche": niche, "platform": platform,
                "hooks_found": len(hooks),
                "top_hooks": [h["hook"][:100] for h in hooks[:5]],
                "dna_analysis": dna,
            }, indent=2, default=str)

        @mcp.tool(description="Generate a zombie viral script using trend DNA")
        def predator_zombie(product: str, niche: str = "general") -> str:
            """Generate high-probability viral script from scraped trends."""
            from swarm.agents.predator_scraper import RealTrendScraper
            scraper = RealTrendScraper(ai_router=ai)
            hooks = scraper.scavenge_viral_hooks(niche, "tiktok", 10)
            dna = scraper.analyze_viral_dna(niche, hooks)
            script = scraper.generate_zombie_script(niche, product, dna)
            return json.dumps({
                "product": product, "niche": niche,
                "script": script, "dna_source": dna.get("samples_analyzed", 0),
            }, indent=2, default=str)

        @mcp.tool(description="Analyze a competitor's content strategy")
        def predator_competitor(username: str, platform: str = "tiktok") -> str:
            """Reverse-engineer a competitor's content strategy."""
            from swarm.agents.predator_scraper import RealTrendScraper
            scraper = RealTrendScraper(ai_router=ai)
            analysis = scraper.scavenge_competitor_strategy(username, platform)
            return json.dumps(analysis, indent=2, default=str)

        @mcp.tool(description="Mine comments for buying signals and auto-reply")
        def predator_mine_comments(post_url: str, platform: str = "tiktok",
                                   brand: str = "") -> str:
            """Scan comment sections for buying signals, auto-reply with CTA."""
            from swarm.agents.predator_scraper import RealTrendScraper
            from swarm.agents.predator_agent import ViralDNALibrary, CommentMiner

            dna = ViralDNALibrary()
            miner = CommentMiner(dna, ai_router=ai)
            scraper = RealTrendScraper(ai_router=ai)

            comments = scraper.mine_comments_from_post(post_url, platform)
            results = miner.process_comments_batch(comments, platform, brand)

            return json.dumps({
                "post_url": post_url, "platform": platform,
                "comments_scanned": len(comments),
                "buying_signals": results,
            }, indent=2, default=str)

        @mcp.tool(description="Monitor brand mentions across social platforms")
        def predator_monitor_brand(brand: str, platform: str = "tiktok") -> str:
            """Start or check brand monitoring."""
            from swarm.agents.predator_agent import PredatorAgent
            agent = PredatorAgent(ai_router=ai)
            result = agent.handle_monitor_brand({"payload": {"brand": brand, "platform": platform}})
            return json.dumps(result, indent=2, default=str)

        @mcp.tool(description="Get the current viral DNA library stats")
        def predator_dna_stats(niche: str = "") -> str:
            """Top viral patterns, winning hooks, and DNA library size."""
            from swarm.agents.predator_agent import ViralDNALibrary
            dna = ViralDNALibrary()
            patterns = dna.top_patterns(niche, limit=10)
            hooks = dna.winning_hooks(niche, limit=5)
            return json.dumps({
                "niche": niche or "all",
                "total_patterns": len(patterns),
                "winning_hooks": hooks,
                "top_patterns": patterns[:5],
            }, indent=2, default=str)

        # ─── Status ───────────────────────────────────────────────────

        @mcp.tool(description="List all registered swarm agents and their status")
        def swarm_status() -> str:
            """Health check for all swarm agents."""
            from swarm.message_bus import MessageBus
            bus = MessageBus()
            health = bus.health()
            return json.dumps({
                "server": SWARM_SERVER_NAME,
                "bus_health": health,
                "agents_available": [
                    "orchestrator", "script_writer", "affiliator",
                    "video_producer", "poster", "engagement",
                    "analytics", "predator",
                ],
            }, indent=2, default=str)

        @mcp.tool(description="Run a full campaign end-to-end")
        def predator_full_campaign(product: str, niche: str = "general",
                                   count: int = 5, with_video: bool = True) -> str:
            """End-to-end: predator trend analysis → scripts → affiliates → video → post."""
            from swarm.agents.predator_scraper import RealTrendScraper

            scraper = RealTrendScraper(ai_router=ai)
            hooks = scraper.scavenge_viral_hooks(niche, "tiktok", 10)
            dna = scraper.analyze_viral_dna(niche, hooks)
            zombie = scraper.generate_zombie_script(niche, product, dna)

            from swarm.message_bus import MessageBus
            bus = MessageBus()
            msg_id = bus.send("mcp", "orchestrator", "campaign", {
                "product": product, "niche": niche,
                "count": count, "platforms": ["tiktok"],
                "generate_video": with_video, "use_affiliate": True,
            })

            return json.dumps({
                "status": "campaign_dispatched",
                "product": product, "niche": niche,
                "message_id": msg_id,
                "viral_dna": {
                    "hooks_found": len(hooks),
                    "winning_hook_types": dna.get("hook_types", []),
                    "avg_engagement": dna.get("avg_engagement_rate", 0),
                },
                "zombie_script": zombie,
            }, indent=2, default=str)

        # ═══════════════════════════════════════════════════════════
        # DAG Pipeline
        # ═══════════════════════════════════════════════════════════

        @mcp.tool(description="Run DAG pipeline campaign with parallel reasoners")
        def dag_campaign(product: str, niche: str = "general") -> str:
            """6 parallel hunters → critic → 3 narrators → judge. Returns best script."""
            factory = UGCPipelineFactory(ai_router=ai)
            result = factory.run_campaign(product, niche)
            winner = result.get("context", {}).get("judge", {}).get("winner_script", {})
            return json.dumps({
                "product": product,
                "niche": niche,
                "duration_sec": result.get("duration_seconds"),
                "nodes_completed": result.get("completed"),
                "nodes_failed": result.get("failed"),
                "winner_script": winner,
            }, indent=2, default=str)

        # ═══════════════════════════════════════════════════════════
        # Gallery
        # ═══════════════════════════════════════════════════════════

        @mcp.tool(description="Add video to UGC gallery with SEO landing page")
        def gallery_add(title: str, video_path: str, niche: str = "general",
                        platform: str = "tiktok", tags: str = "",
                        description: str = "") -> str:
            g = _get_gallery()
            vid = g.add_video(title=title, video_path=video_path, niche=niche,
                              platform=platform, tags=tags, description=description)
            v = g.get_video(vid)
            return json.dumps({"id": vid, "slug": v["slug"] if v else "", "status": "created"})

        @mcp.tool(description="List UGC gallery videos with stats")
        def gallery_list(niche: str = "", limit: int = 20) -> str:
            g = _get_gallery()
            videos = g.list_videos(niche=niche, limit=limit)
            stats = g.get_stats()
            return json.dumps({"videos": videos, "stats": stats}, indent=2, default=str)

        # ═══════════════════════════════════════════════════════════
        # Social Inbox
        # ═══════════════════════════════════════════════════════════

        @mcp.tool(description="List latest unread inbox messages")
        def inbox_list(platform: str = "", limit: int = 10) -> str:
            ib = _get_inbox(ai_router=ai)
            msgs = ib.list_messages(platform=platform, status="unread", limit=limit)
            stats = ib.get_stats()
            return json.dumps({"messages": msgs, "stats": stats}, indent=2, default=str)

        @mcp.tool(description="Reply to an inbox message")
        def inbox_reply(message_id: int, reply_text: str) -> str:
            ib = _get_inbox()
            ok = ib.send_reply(message_id, reply_text)
            ib.mark_read(message_id)
            return json.dumps({"status": "ok" if ok else "error", "message_id": message_id})

        @mcp.tool(description="Run auto-reply on all unreplied messages")
        def inbox_auto_reply(limit: int = 20) -> str:
            ib = _get_inbox()
            result = ib.bulk_auto_reply(limit=limit)
            return json.dumps(result)

        # ═══════════════════════════════════════════════════════════
        # Brand Profiles
        # ═══════════════════════════════════════════════════════════

        @mcp.tool(description="List all brand profiles")
        def brand_list() -> str:
            bp = _get_brand()
            brands = bp.list_all()
            return json.dumps({"brands": brands}, indent=2, default=str)

        @mcp.tool(description="Create a new brand profile")
        def brand_create(name: str, tone: str = "casual", voice: str = "friendly",
                         language: str = "en") -> str:
            bp = _get_brand()
            bid = bp.create({"name": name, "tone": tone, "voice": voice, "language": language})
            return json.dumps({"id": bid, "status": "created"})

        @mcp.tool(description="Activate a brand profile by ID")
        def brand_activate(brand_id: int) -> str:
            bp = _get_brand()
            ok = bp.set_active(brand_id)
            return json.dumps({"status": "ok" if ok else "error"})

        # ═══════════════════════════════════════════════════════════
        # Approval Workflow
        # ═══════════════════════════════════════════════════════════

        @mcp.tool(description="List pending content approvals")
        def approval_list(limit: int = 20) -> str:
            aw = _get_approval()
            items = aw.list_pending(limit=limit)
            stats = aw.get_stats()
            return json.dumps({"items": items, "stats": stats}, indent=2, default=str)

        @mcp.tool(description="Approve pending content")
        def approval_approve(approval_id: int, note: str = "") -> str:
            aw = _get_approval()
            ok = aw.approve(approval_id, reviewer="mcp", note=note)
            return json.dumps({"status": "ok" if ok else "error"})

        @mcp.tool(description="Reject pending content")
        def approval_reject(approval_id: int, note: str = "") -> str:
            aw = _get_approval()
            ok = aw.reject(approval_id, reviewer="mcp", note=note)
            return json.dumps({"status": "ok" if ok else "error"})

        # ═══════════════════════════════════════════════════════════
        # Trend Scout
        # ═══════════════════════════════════════════════════════════

        @mcp.tool(description="Get trending hooks for a niche with AI analysis")
        def trend_hooks(niche: str = "general", platform: str = "tiktok", limit: int = 10) -> str:
            ts = _get_trend(ai_router=ai)
            hooks = ts.get_trending(niche=niche, platform=platform, limit=limit)
            if not hooks:
                hooks = ts.analyze_with_ai(niche=niche, platform=platform)
            stats = ts.get_stats()
            return json.dumps({"hooks": hooks, "stats": stats}, indent=2, default=str)

        @mcp.tool(description="Get winning content patterns by niche")
        def trend_patterns(niche: str = "", pattern_type: str = "") -> str:
            ts = _get_trend()
            patterns = ts.get_winning_patterns(niche=niche, pattern_type=pattern_type)
            return json.dumps({"patterns": patterns}, indent=2, default=str)

        @mcp.tool(description="Analyze trends with AI for a niche")
        def trend_analyze(niche: str = "general", platform: str = "tiktok") -> str:
            ts = _get_trend(ai_router=ai)
            hooks = ts.analyze_with_ai(niche=niche, platform=platform)
            return json.dumps({"niche": niche, "platform": platform, "hooks": hooks}, indent=2, default=str)

    def run(self, transport: str = "stdio"):
        """Start the MCP server.

        Args:
            transport: 'stdio' for Claude/Cursor/CLI, 'sse' for HTTP
        """
        log.info("Swarm MCP Server starting (transport=%s)", transport)
        self.mcp.run(transport=transport)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)16s] %(message)s",
    )
    server = SwarmMCPServer()
    server.run()


if __name__ == "__main__":
    main()
