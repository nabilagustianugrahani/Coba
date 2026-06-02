import os
import sys
import json
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Skynet")
    load_dotenv()

def main():
    logger.info("=" * 50)
    logger.info("SKYNET V2.0 — Autonomous UGC Empire")
    logger.info("=" * 50)

    router_url = os.getenv("ROUTER_URL", "http://localhost:20128")
    router_key = os.getenv("ROUTER_KEY", "sk-8028a980b0c7366a-4a45za-36eef5ef")
    logger.info(f"9Router: {router_url}")

    from ugc_ai_overpower.mcp_server.tools.ai_tools import AIRouter
    from ugc_ai_overpower.core.content_bank import ContentBank
    from ugc_ai_overpower.core.orchestrator import Orchestrator
    from ugc_ai_overpower.mcp_server.tools.influencer_tools import InfluencerManager

    ai = AIRouter(router_url, router_key)
    bank = ContentBank()
    orch = Orchestrator(bank, ai)
    im = InfluencerManager()

    if len(sys.argv) < 2:
        logger.info("Usage: python main.py <command> [args]")
        logger.info("Commands:")
        logger.info("  campaign <product>  — Running full campaign")
        logger.info("  analyze <product>   — Analyze product market")
        logger.info("  search <keyword>    — Search affiliate products")
        logger.info("  list-influencers    — Show all influencer personas")
        logger.info("  server              — Start MCP server")
        logger.info("  generate-personas   — Generate 15 default personas")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "campaign":
        product = " ".join(sys.argv[2:]) or input("Product name: ")
        logger.info(f"Starting campaign for: {product}")
        result = orch.run_campaign(product)
        logger.info(json.dumps(result, indent=2, default=str))
        logger.info(f"✅ Campaign created! Content: {result['total']} pieces")

    elif cmd == "analyze":
        product = " ".join(sys.argv[2:]) or input("Product: ")
        analysis = ai.analyze_product(product)
        logger.info(f"Analysis for {product}:")
        print(analysis)

    elif cmd == "search":
        keyword = " ".join(sys.argv[2:]) or input("Keyword: ")
        from ugc_ai_overpower.mcp_server.tools.scraper_tools import ScraperTools
        st = ScraperTools()
        results = st.search_best_commission(keyword)
        print(json.dumps(results, indent=2, default=str))

    elif cmd == "list-influencers":
        for inf in im.get_all():
            print(f"  {inf['name']:15s} → {inf['niche']:12s} ({inf['age']}th, {inf['gender']})")

    elif cmd == "server":
        logger.info("Starting MCP server...")
        from ugc_ai_overpower.mcp_server import server
        server.main()

    elif cmd == "generate-personas":
        from ugc_ai_overpower.mcp_server.tools.ai_tools import AIRouter
        ai = AIRouter(router_url, router_key)
        from ugc_ai_overpower.mcp_server.tools.influencer_tools import InfluencerManager
        im = InfluencerManager()
        for inf in im.get_all():
            result = ai.chat_structured(
                f"Generate detail persona untuk influencer UGC:\n"
                f"Nama: {inf['name']}\nNiche: {inf['niche']}\nGender: {inf['gender']}\n"
                f"Beri backstory detail, gaya bicara, dan rekomendasi produk"
            )
            logger.info(f"{inf['name']}: {json.dumps(result, default=str)[:100]}")

    else:
        logger.warning(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()