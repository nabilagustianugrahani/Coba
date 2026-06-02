import os
import sys
import json
import logging
from ugc_ai_overpower.auth import create_access_token, verify_token, authenticate_user, get_password_hash, get_user, USERS_DB

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Skynet")

def main():
    router_url = os.getenv("ROUTER_URL", "http://localhost:20128")
    router_key = os.getenv("ROUTER_KEY", "sk-8028a980b0c7366a-4a45za-36eef5ef")

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        logger.error("MCP library not installed. Run: pip install mcp")
        sys.exit(1)

    from ugc_ai_overpower.mcp_server.tools.ai_tools import AIRouter
    from ugc_ai_overpower.core.content_bank import ContentBank
    from ugc_ai_overpower.core.orchestrator import Orchestrator

    ai = AIRouter(router_url, router_key)
    bank = ContentBank()
    orch = Orchestrator(bank, ai)

    mcp = FastMCP("Skynet-UGC")

    @mcp.auth_middleware
    def verify_jwt_token(token: str):
        payload = verify_token(token)
        if payload is None:
            raise Exception("Invalid or expired token")
        return payload


        @mcp.api_route("/login", methods=["POST"])
    def login(username: str, password: str):
        user = authenticate_user(username, password)
        if not user:
            raise Exception("Invalid credentials")
        access_token = create_access_token(data={"sub": user["username"], "roles": user["roles"]})
        return {"access_token": access_token, "token_type": "bearer"}

    @mcp.api_route("/register", methods=["POST"])
    def register(username: str, password: str):
        if get_user(username):
            raise Exception("Username already registered")

        # In Phase 1, we only allow hardcoded users. Registration is just a placeholder.
        raise Exception("Registration is not allowed in this phase.")

    @mcp.tool(auth_required=True)
    def generate_script(product: str, platform: str = "tiktok", tone: str = "casual") -> str:
        prompt = f"Buat script UGC untuk {product} di {platform}. Tone: {tone}. Bahasa Indonesia."
        return ai.chat(prompt)

    @mcp.tool(auth_required=True)
    def analyze_trend(niche: str) -> str:
        prompt = f"Apa trending topic di niche {niche} untuk konten UGC? Berikan ide konten."
        return ai.chat(prompt)

    @mcp.tool(auth_required=True)
    def generate_hashtags(niche: str, count: int = 10) -> str:
        prompt = f"Generate {count} hashtag trending Indonesia untuk niche {niche}."
        return ai.chat(prompt)

    @mcp.tool(auth_required=True)
    def plan_campaign(product: str) -> str:
        result = orch.plan_campaign(product)
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(auth_required=True)
    def run_campaign(product: str) -> str:
        result = orch.run_campaign(product)
        return json.dumps(result, indent=2, default=str)

    @mcp.tool(auth_required=True)
    def search_products(keyword: str) -> str:
        results = orch.find_products(keyword)
        return json.dumps(results, indent=2, default=str)

    @mcp.tool(auth_required=True)
    def list_influencers(niche: str = "") -> str:
        from ugc_ai_overpower.mcp_server.tools.influencer_tools import InfluencerManager
        im = InfluencerManager()
        if niche:
            infs = im.get_by_niche(niche)
        else:
            infs = im.get_all()
        return json.dumps([{
            "name": i["name"],
            "niche": i["niche"],
            "age": i["age"],
            "gender": i["gender"],
            "personality": i["personality"]
        } for i in infs], indent=2)

    @mcp.tool(auth_required=True)
    def psychology_angle(product: str) -> str:
        from ugc_ai_overpower.core.psychology import PsychologyEngine
        pe = PsychologyEngine()
        group, info = pe.get_target_group(product)
        triggers = pe.get_triggers_for_product(product)
        return json.dumps({
            "target_group": group,
            "description": info["description"],
            "platforms": info["preferred_platforms"],
            "psychology_triggers": [t["name"] for t in triggers]
        }, indent=2)

    @mcp.tool(auth_required=True)
    def affiliate_summary() -> str:
        items = bank.get_all()
        return json.dumps(items, indent=2, default=str)

    logger.info("Skynet MCP Server ready!")
    mcp.run()