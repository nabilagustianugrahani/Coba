from __future__ import annotations
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
    logger.info(f"Router: {router_url}")

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
        logger.info("  campaign <product>     — Running full campaign")
        logger.info("  auto-campaign <product> [image] [platforms] — Auto: script → video → post")
        logger.info("  overkill <product>     — OVERKILL MODE: parallel × series × recycle × farm × post")
        logger.info("  mass-produce           — UGC mass production: 1 cmd → 100+ videos")
        logger.info("  analyze <product>      — Analyze product market")
        logger.info("  search <keyword>       — Search affiliate products")
        logger.info("  list-influencers       — Show all influencer personas")
        logger.info("  search-content <q>     — Full-text search in content bank")
        logger.info("  top-content [platform] — Top performing content")
        logger.info("  ab-test <product>      — Generate A/B test hooks")
        logger.info("  analyze-times          — Find optimal posting times")
        logger.info("  series-plan <product>  — Create structured content series")
        logger.info("  server                 — Start MCP server")
        logger.info("  generate-personas      — Generate 15 default personas")
        logger.info("  queue-status           — Show content queue stats")
        logger.info("  process-queue [platf]  — Process next pending item")
        logger.info("  post <id> <platform>   — Queue a content item for posting")
        logger.info("  scheduler              — Run content scheduler daemon")
        logger.info("  schedule-campaign <product> <interval_min> [max_runs] — Schedule recurring campaign")
        logger.info("  unschedule <job_id>    — Stop a scheduled campaign")
        logger.info("  list-jobs              — Show active scheduled jobs")
        logger.info("  analytics              — Show analytics dashboard")
        logger.info("  api                    — Start FastAPI server")
        logger.info("  generate-video <script> [img] — Generate UGC video from script")
        logger.info("  post-video <path> <platform>  — Post video to platform")
        logger.info("  cookie-save <platform> [profile] — Save cookies to profile")
        logger.info("  cookie-list            — List saved cookie profiles")
        logger.info("  set-affiliate <platform> <id> [track] — Set affiliate link ID")
        logger.info("  list-affiliates        — Show affiliate platform configs")
        logger.info("  daily-schedule [product] — Schedule/set daily campaign schedule")
        logger.info("  start-daemon           — Start scheduler daemon with daily campaigns")
        logger.info('  generate-avatar <face_img> <script> — Generate talking-head avatar')
        logger.info('  render-video <script>   — Render multi-scene UGC video (5-scene editor)')
        logger.info('  affiliate-search <q>    — Search affiliate products from Shopee/Tokopedia')
        logger.info('  affiliate-catalog [q]   — Browse local affiliate product catalog')
        logger.info("  notion-dbs              — Create all Notion databases (7 databases)")
        logger.info("  notion-sync-all          — Sync ALL data to Notion (gallery, inbox, brands, approvals)")
        logger.info("  notion-sync-products     — Sync affiliate products to Notion")
        logger.info("  list-products            — List affiliate products from catalog")
        logger.info("  swarm                  — Start multi-agent swarm")
        logger.info('  swarm-campaign <product> — Dispatch campaign via swarm')
        logger.info("  swarm-status           — Show swarm health & campaigns")
        logger.info("  pipeline <product>     — DAG pipeline: 6 hunters → critic → 3 narrators → judge")
        logger.info("  notion-list campaigns|content  — List Notion campaigns or content")
        logger.info("  notion-find <query>         — Search across Notion databases")
        logger.info("  notion-analytics [product]   — View or update analytics")
        logger.info("  run-pipeline           — Full pipeline: all products → content → Notion sync")
        logger.info("  codespace-pool status|dispatch|list — Multi-codespace parallel execution")
        logger.info("  auto-pipeline          — Auto-pipeline daemon management")
        logger.info("  telegram               — Start Telegram Commander (control from phone)")
        logger.info("  trends [niche]         — AI-powered trend analysis for niche")
        logger.info("  modal-status           — Check Modal GPU connection & quota")
        logger.info("  modal-deploy           — Deploy SoulX-FlashHead to Modal")
        logger.info("  list-modal-accounts    — Show all configured Modal accounts")
        logger.info("  analytics-collect      — Collect engagement from bank, push to Notion")
        logger.info("  scrape-engagement      — Scrape/simulate engagement metrics for content items")
        logger.info("  health-check           — Run daemon health check, alert Notion Inbox on failure")
        logger.info("  autoheal               — Run auto-heal cycle (run|dry-run|stats|incidents)")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "campaign":
        product = " ".join(sys.argv[2:]) or input("Product name: ")
        logger.info(f"Starting campaign for: {product}")
        result = orch.run_campaign(product)
        logger.info(json.dumps(result, indent=2, default=str))
        logger.info(f"✅ Campaign created! Content: {result['total']} pieces")

    elif cmd == "auto-campaign":
        if len(sys.argv) < 3:
            logger.error("Usage: auto-campaign <product> [image_path] [platforms]")
            sys.exit(1)
        product = sys.argv[2]
        image_path = sys.argv[3] if len(sys.argv) > 3 else None
        platforms = sys.argv[4].split(",") if len(sys.argv) > 4 else ["tiktok"]
        logger.info(f"Starting AUTO campaign for: {product}")
        result = orch.auto_campaign(product, product_image=image_path, platforms=platforms)
        logger.info(json.dumps(result, indent=2, default=str))
        logger.info(f"✅ Auto campaign done! Posted to: {result['posted_to']}")

    elif cmd == "overkill":
        product = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else input("Product: ")
        count = int(input("How many content pieces? ") or "50")
        img = input("Product image path (or Enter to skip): ") or ""
        platforms = (input("Platforms (comma-separated, default: tiktok,instagram): ") or "tiktok,instagram").split(",")
        logger.info(f"🔥 OVERKILL MODE: {product} × {count} pieces!")
        result = orch.overkill_mode(
            product=product, count=count, platforms=platforms,
            product_image=img, use_farm=False
        )
        logger.info(json.dumps(result, indent=2, default=str))
        logger.info(f"✅ Overkill done: {result['generated']} generated, {result.get('posted', 0)} posted in {result.get('elapsed_seconds', 0)}s")

    elif cmd == "pipeline":
        product = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else input("Product: ")
        niche = input("Niche [general]: ") or "general"
        logger.info(f"🚀 Running DAG pipeline for {product} ({niche})...")
        from ugc_ai_overpower.core.pipeline_engine import UGCPipelineFactory
        factory = UGCPipelineFactory(ai_router=ai)
        result = factory.run_campaign(product, niche)
        winner = result.get("context", {}).get("judge", {}).get("winner_script", {})
        print(json.dumps(result, indent=2, default=str))
        if winner:
            print(f"\n🎯 Winning hook: {winner.get('hook', 'N/A')}")
        print(f"✅ Pipeline done in {result.get('duration_seconds', 0)}s")

    elif cmd == "telegram":
        logger.info("Starting Telegram Commander...")
        from ugc_ai_overpower.browser.telegram_commander import TelegramCommander
        from ugc_ai_overpower.core.gallery import Gallery
        from ugc_ai_overpower.browser.social_inbox import SocialInbox
        from ugc_ai_overpower.core.brand_profile import BrandProfile
        from ugc_ai_overpower.core.approval_workflow import ApprovalWorkflow
        from ugc_ai_overpower.core.pipeline_engine import UGCPipelineFactory
        tc = TelegramCommander(
            gallery=Gallery(),
            inbox=SocialInbox(ai_router=ai),
            brand_profile=BrandProfile(),
            approval_workflow=ApprovalWorkflow(),
            pipeline_factory=UGCPipelineFactory(ai_router=ai),
        )
        tc.start()
        logger.info("Telegram Commander running. Press Ctrl+C to stop.")
        try:
            import time
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            tc.stop()

    elif cmd == "trends":
        niche = sys.argv[2] if len(sys.argv) > 2 else "general"
        logger.info(f"Scanning trends for '{niche}'...")
        from ugc_ai_overpower.browser.trend_scout import TrendScout
        ts = TrendScout(ai_router=ai)
        hooks = ts.analyze_with_ai(niche=niche)
        print(f"\n  📈 Trending Hooks for '{niche}':")
        for i, h in enumerate(hooks, 1):
            print(f"  {i}. {h['hook'][:60]}")
            print(f"     Format: {h['format']} | Score: {h['score']}/10")
            print(f"     Why: {h.get('reasoning','')[:80]}")
            print()

    elif cmd == "mass-produce":
        product = sys.argv[2] if len(sys.argv) > 2 else input("Product: ")
        niche = input("Niche (skincare/fashion/food/tech/general) [general]: ") or "general"
        count = int(input("How many UGC videos? [50]: ") or "50")
        platforms = (input("Platforms [tiktok,instagram]: ") or "tiktok,instagram").split(",")
        image = input("Product image path (or Enter to skip): ") or ""
        generate_video = input("Generate videos? (y/N): ").lower() == "y"
        theme = input("Theme (default/dark/warm/fresh/luxury/bright) [default]: ") or "default"
        watermark = input("Watermark text (or Enter to skip): ") or ""

        logger.info(f"🔥 MASS PRODUCTION: {count} UGC videos for {product}")
        from ugc_ai_overpower.core.mass_production import UGCMassProduction
        factory = UGCMassProduction()
        result = factory.run(
            ai_router=ai, product=product, niche=niche,
            count=count, platforms=platforms,
            product_image=image, generate_video=generate_video,
            auto_post=False, theme=theme, watermark=watermark,
        )
        print(json.dumps(result, indent=2, default=str))
        print(f"✅ {result['scripts_generated']} scripts, {result['videos_generated']} videos in {result['elapsed_seconds']}s")

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

    elif cmd == "search-content":
        query = " ".join(sys.argv[2:]) or input("Search: ")
        from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
        results = ContentBankV2().search_content(query)
        for r in results[:10]:
            print(f"  #{r['id']} {r['hook'][:50]:50s} score={r.get('engagement_score', 0)}")

    elif cmd == "top-content":
        plat = sys.argv[2] if len(sys.argv) > 2 else ""
        from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
        for c in ContentBankV2().get_top_performing(platform=plat, limit=10):
            print(f"  #{c['id']} {c['hook'][:45]:45s} eng={c.get('engagement_score', 0):.1f}% views={c.get('views', 0)}")

    elif cmd == "ab-test":
        product = " ".join(sys.argv[2:]) or input("Product: ")
        from ugc_ai_overpower.core.optimizer import AnalyticsOptimizer
        from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
        opt = AnalyticsOptimizer(ContentBankV2())
        test = opt.setup_ab_test(ai, product)
        print("  A/B Test untuk:", product)
        print(f"  Group A (Hook): {test['group_a']['hook']}")
        print(f"  Group B (Hook): {test['group_b']['hook']}")

    elif cmd == "analyze-times":
        from ugc_ai_overpower.core.optimizer import AnalyticsOptimizer
        from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
        opt = AnalyticsOptimizer(ContentBankV2())
        analysis = opt.analyze_posting_times()
        print("  Best posting times:")
        for plat, times in analysis.get("platform_recommendations", {}).items():
            print(f"    {plat:12s}: {', '.join(times[:3])}")

    elif cmd == "series-plan":
        product = " ".join(sys.argv[2:]) or input("Product: ")
        niche = input("Niche (e.g. skincare, fashion, food): ") or "general"
        ep = int(input("Total episodes: ") or "10")
        from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
        from ugc_ai_overpower.core.series import SeriesEngine
        se = SeriesEngine(ContentBankV2())
        plan = se.create_series_plan(product, niche, total_episodes=ep)
        print(json.dumps(plan, indent=2, default=str))
        print(f"✅ Series #{plan['series_id']} created with {plan['total_episodes']} episodes")

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

    # ------------------------------------------------------------------
    # New Phase 2 commands
    # ------------------------------------------------------------------
    elif cmd == "queue-status":
        _cmd_queue_status()

    elif cmd == "process-queue":
        platform = sys.argv[2] if len(sys.argv) > 2 else None
        _cmd_process_queue(orch, platform)

    elif cmd == "post":
        if len(sys.argv) < 4:
            logger.error("Usage: post <content_id> <platform>")
            sys.exit(1)
        content_id = int(sys.argv[2])
        platform = sys.argv[3]
        _cmd_post(bank, orch, content_id, platform)

    elif cmd == "scheduler":
        _cmd_scheduler()

    elif cmd == "analytics":
        _cmd_analytics()

    # ── Affiliate commands ──────────────────────────────────────────
    elif cmd == "set-affiliate":
        if len(sys.argv) < 4:
            logger.error("Usage: set-affiliate <platform> <af_id> [track_id]")
            sys.exit(1)
        platform = sys.argv[2]
        af_id = sys.argv[3]
        track_id = sys.argv[4] if len(sys.argv) > 4 else ""
        from ugc_ai_overpower.core.affiliate import AffiliateManager
        am = AffiliateManager()
        am.set_affiliate_id(platform, af_id, track_id)
        print(f"✅ {platform} affiliate ID set: {af_id}")

    elif cmd == "list-affiliates":
        from ugc_ai_overpower.core.affiliate import AffiliateManager
        am = AffiliateManager()
        configs = am.get_all_configs()
        print("  Affiliate configs:")
        for plat, cfg in configs.items():
            print(f"    {plat:12s} → {cfg.get('af_id', '(not set)')}")

    # ── Daily schedule commands ─────────────────────────────────────
    elif cmd == "daily-schedule":
        from ugc_ai_overpower.scheduler.engine import SkynetScheduler
        sched = SkynetScheduler()
        if len(sys.argv) >= 3:
            product = " ".join(sys.argv[2:])
            job_id = sched.schedule_campaign_daily(product, hour=8, minute=0)
            print(f"✅ Daily campaign scheduled: {product} at 08:00 WIB (job: {job_id})")
        else:
            for j in sched.list_jobs():
                print(f"  {j['id']:35s} {j['name']:25s} next: {j['next_run'] or 'N/A'}")

    elif cmd == "start-daemon":
        logger.info("Starting scheduler daemon with daily campaigns...")
        _cmd_scheduler()

    elif cmd == "generate-video":
        if len(sys.argv) < 3:
            logger.error("Usage: generate-video <script> [product_image]")
            sys.exit(1)
        script = sys.argv[2]
        img = sys.argv[3] if len(sys.argv) > 3 else None
        _cmd_generate_video(script, img)

    elif cmd == "post-video":
        if len(sys.argv) < 4:
            logger.error("Usage: post-video <video_path> <platform>")
            sys.exit(1)
        _cmd_post_video(sys.argv[2], sys.argv[3])

    elif cmd == "schedule-campaign":
        if len(sys.argv) < 3:
            logger.error("Usage: schedule-campaign <product> <interval_min> [max_runs]")
            sys.exit(1)
        product = sys.argv[2]
        interval = int(sys.argv[3]) if len(sys.argv) > 3 else 1440
        max_runs = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        _cmd_schedule_campaign(orch, product, interval, max_runs)

    elif cmd == "unschedule":
        if len(sys.argv) < 3:
            logger.error("Usage: unschedule <job_id>")
            sys.exit(1)
        _cmd_unschedule(sys.argv[2])

    elif cmd == "list-jobs":
        _cmd_list_jobs()

    elif cmd == "cookie-save":
        if len(sys.argv) < 3:
            logger.error("Usage: cookie-save <platform> [profile]")
            sys.exit(1)
        platform = sys.argv[2]
        profile = sys.argv[3] if len(sys.argv) > 3 else "default"
        _cmd_cookie_save(platform, profile)

    elif cmd == "cookie-list":
        _cmd_cookie_list()

    elif cmd == "api":
        _cmd_api()

    # ── Swarm commands ─────────────────────────────────────────────
    elif cmd == "swarm":
        logger.info("🐝 Starting swarm agents...")
        from ugc_ai_overpower.swarm.main import start_swarm
        start_swarm(ai_router=ai)

    elif cmd == "swarm-campaign":
        if len(sys.argv) < 3:
            logger.error("Usage: swarm-campaign <product> [niche] [count]")
            sys.exit(1)
        product = sys.argv[2]
        niche = sys.argv[3] if len(sys.argv) > 3 else "general"
        count = int(sys.argv[4]) if len(sys.argv) > 4 else 50
        logger.info(f"🐝 Dispatching swarm campaign: {product} ({niche}, {count}videos)")
        from ugc_ai_overpower.swarm.main import run_campaign
        run_campaign(ai, product, niche, count)

    elif cmd == "swarm-status":
        from ugc_ai_overpower.swarm.message_bus import MessageBus
        bus = MessageBus()
        health = bus.health()
        print(f"\n  Swarm Bus Health:")
        print(f"    Pending   : {health['pending']}")
        print(f"    Processing: {health['processing']}")
        print(f"    Done      : {health['done']}")
        print(f"    Failed    : {health['failed']}")
        print(f"\n  Run 'python main.py swarm' to start agents.")

    # ── Avatar / Modal commands ────────────────────────────────────
    elif cmd == "generate-avatar":
        if len(sys.argv) < 4:
            logger.error("Usage: generate-avatar <face_image> <script>")
            sys.exit(1)
        face_image = sys.argv[2]
        script = " ".join(sys.argv[3:])
        logger.info(f"Generating avatar for: {os.path.basename(face_image)}")
        path = orch.generate_avatar(face_image, script=script)
        if path:
            print(f"✅ Avatar video: {path}")
        else:
            print("❌ Avatar generation failed")

    elif cmd == "render-video":
        if len(sys.argv) < 3:
            logger.error("Usage: render-video <script> [product_image] [face_image]")
            sys.exit(1)
        script = sys.argv[2]
        product_image = sys.argv[3] if len(sys.argv) > 3 else None
        face_image = sys.argv[4] if len(sys.argv) > 4 else None
        logger.info("Rendering multi-scene UGC video...")
        path = orch.render_video(script, product_image=product_image, face_image=face_image)
        if path:
            print(f"✅ Video: {path}")
        else:
            print("❌ Render failed")

    elif cmd == "affiliate-search":
        query = " ".join(sys.argv[2:]) or input("Search product: ")
        products = orch.affiliate_search(query, limit=10)
        print(f"\n  Top affiliate products for '{query}':")
        print(f"  {'Platform':12s} {'Price':>10s} {'Komisi':>10s} {'Nama'}")
        print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*40}")
        for p in products:
            print(f"  {p.platform:12s} Rp{p.price:>8,.0f} Rp{p.estimated_commission:>7,.0f} {p.name[:50]}")

    elif cmd == "affiliate-catalog":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        products = orch.affiliate_catalog(query)
        if not products:
            print("  No products in catalog. Run 'affiliate-search' first.")
        else:
            print(f"\n  {'ID':>4} {'Platform':12s} {'Price':>10s} {'Komisi':>8s} {'Nama'}")
            print(f"  {'-'*4} {'-'*12} {'-'*10} {'-'*8} {'-'*50}")
            for p in products[:15]:
                print(f"  {p.get('id',0):>4} {p.get('platform',''):12s} Rp{p.get('price',0):>8,.0f} Rp{p.get('commission',0):>6,.0f} {p.get('name','')[:50]}")

    elif cmd == "modal-status":
        status = orch.modal_status()
        print(json.dumps(status, indent=2, default=str))

    elif cmd == "modal-deploy":
        logger.info("Deploying SoulX-FlashHead to Modal...")
        result = orch.modal_deploy()
        print(json.dumps(result, indent=2, default=str))

    elif cmd == "list-modal-accounts":
        from ugc_ai_overpower.gpu.modal_pipeline import ModalPipeline
        accounts = ModalPipeline().list_accounts()
        if not accounts:
            print("  No Modal accounts configured.")
        for acc in accounts:
            print(f"  [{acc['index']}] {acc['status']}")

    elif cmd == "analytics-collect":
        _cmd_analytics_collect()

    elif cmd == "scrape-engagement":
        from ugc_ai_overpower.core.engagement_scraper import EngagementScraper
        scraper = EngagementScraper()
        mode = sys.argv[2] if len(sys.argv) > 2 else "simulate"
        if mode == "simulate":
            result = scraper.simulate_all(posted_only=True)
            print(f"\n  Engagement simulation complete: {result['simulated']} items updated")
            for item in result["items"][:5]:
                print(f"    #{item['id']:>4}  views={item['views']:>6}  likes={item['likes']:>4}  comments={item['comments']:>3}  shares={item['shares']:>3}  score={item['engagement_score']:.2f}%")
        elif mode == "scrape":
            logger.info("Real platform scraping — limited by anti-bot. Use simulate for now.")
            result = scraper.simulate_all(posted_only=True)
            print(f"  Simulated: {result['simulated']} items (real scrape needs API keys)")
        else:
            logger.error(f"Unknown scrape-engagement mode: {mode}")
            logger.error("Usage: scrape-engagement [simulate|scrape]")

    elif cmd == "health-check":
        from ugc_ai_overpower.core.health_monitor import HealthMonitor
        monitor = HealthMonitor()
        result = monitor.run_health_check(alert=True)
        if result["healthy"]:
            print("  ✅ Pipeline healthy")
            sys.exit(0)
        else:
            print(f"  ❌ Pipeline unhealthy: {result}")
            sys.exit(1)

    elif cmd == "autoheal":
        from ugc_ai_overpower.core.autoheal import AutoHealOrchestrator
        orch = AutoHealOrchestrator()
        orch.reload()
        sub = sys.argv[2] if len(sys.argv) > 2 else "run"
        if sub == "run":
            result = orch.run_heal_cycle(auto_apply=True)
            print(json.dumps(result, indent=2, default=str))
        elif sub == "dry-run":
            result = orch.run_heal_cycle(auto_apply=False)
            print(json.dumps(result, indent=2, default=str))
        elif sub == "stats":
            print(json.dumps(orch.get_stats(), indent=2))
        elif sub == "incidents":
            for inc in orch.recent_incidents(limit=20):
                print(json.dumps(inc, default=str))
        else:
            logger.error("Usage: autoheal [run|dry-run|stats|incidents]")

    # ── Notion commands ────────────────────────────────────────────
    elif cmd == "notion-init":
        _cmd_notion_init()

    elif cmd == "notion-status":
        _cmd_notion_status()

    elif cmd == "notion-campaigns":
        _cmd_notion_campaigns()

    elif cmd == "notion-daily-report":
        date_str = sys.argv[2] if len(sys.argv) > 2 else None
        _cmd_notion_daily_report(date_str)

    elif cmd == "notion-sync":
        product = " ".join(sys.argv[2:])
        if not product:
            logger.error("Usage: notion-sync <product>")
            sys.exit(1)
        _cmd_notion_sync(orch, product)

    elif cmd == "notion-sync-all":
        _cmd_notion_sync_all()

    elif cmd == "notion-dbs":
        _cmd_notion_create_all_dbs()

    elif cmd == "notion-sync-products":
        _cmd_notion_sync_products()

    elif cmd == "notion-list":
        nd = _get_notion()
        if not nd:
            return
        if len(sys.argv) < 3:
            logger.error("Usage: notion-list campaigns | content <campaign_id>")
            sys.exit(1)
        sub = sys.argv[2]
        if sub == "campaigns":
            campaigns = nd.get_all_campaigns()
            print(f"\n  {'Name':30s} {'Status':12s} {'Content':>8} {'Posts':>6} {'Product'}")
            print(f"  {'-'*30} {'-'*12} {'-'*8} {'-'*6} {'-'*30}")
            for c in campaigns:
                print(f"  {c['name'][:30]:30s} {c['status']:12s} {c['content_generated']:>8} {c['posts_published']:>6} {c['product'][:30]}")
            print(f"  Total: {len(campaigns)} campaigns")
        elif sub == "content":
            if len(sys.argv) < 4:
                logger.error("Usage: notion-list content <campaign_id>")
                sys.exit(1)
            items = nd.get_content_for_campaign(sys.argv[3])
            print(f"\n  {'Hook':50s} {'Platform':12s} {'Status':12s}")
            print(f"  {'-'*50} {'-'*12} {'-'*12}")
            for i in items:
                print(f"  {i['hook'][:50]:50s} {i['platform']:12s} {i['status']:12s}")
            print(f"  Total: {len(items)} items")
        else:
            logger.error(f"Unknown notion-list subcommand: {sub}")

    elif cmd == "notion-find":
        nd = _get_notion()
        if not nd:
            return
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else input("Search: ")
        print(f"\n  Searching for '{query}' across all databases...")
        dbs = [
            ("Campaigns", nd.campaign_db),
            ("Content", nd.content_db),
            ("Products", nd.products_db),
        ]
        found = 0
        for name, db_id in dbs:
            if db_id:
                results = nd.find_in_database(db_id, query)
                if results:
                    print(f"\n  📁 {name}:")
                    for r in results:
                        print(f"     - {r['name'][:80]} ({r['id'][:12]}...)")
                        found += 1
        if not found:
            print("  No results found.")

    elif cmd == "notion-analytics":
        nd = _get_notion()
        if not nd:
            return
        product = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        if product:
            logger.info(f"Updating analytics for {product}...")
            from ugc_ai_overpower.core.orchestrator import Orchestrator
            orch = Orchestrator(None, None)
            result = orch.update_analytics(product)
            print(json.dumps(result, indent=2, default=str))
        else:
            _cmd_analytics()

    elif cmd == "run-pipeline":
        from ugc_ai_overpower.core.pipeline_engine import PipelineEngine
        engine = PipelineEngine(ai_router=ai)
        logger.info("Running full pipeline (products -> content -> notion)...")
        result = engine.run_full_pipeline()
        print(json.dumps(result, indent=2, default=str))
        print(f"Pipeline complete: {result['products_processed']} products processed")

    elif cmd == "auto-pipeline":
        if len(sys.argv) < 3:
            logger.error("Usage: auto-pipeline <start|stop|status|run-once>")
            sys.exit(1)
        # Import and run the auto-pipeline daemon
        from ugc_ai_overpower.core.auto_pipeline import main as auto_pipeline_main
        # Replace sys.argv with the auto-pipeline arguments
        sys.argv = [sys.argv[0]] + sys.argv[2:]  # Remove 'main.py' and 'auto-pipeline'
        auto_pipeline_main()

    elif cmd == "list-products":
        _cmd_list_products()

    elif cmd == "codespace-pool":
        sub = sys.argv[2] if len(sys.argv) > 2 else "status"
        _cmd_codespace_pool(sub, sys.argv[3:])

    else:
        logger.warning(f"Unknown command: {cmd}")


# ======================================================================
# Command handlers
# ======================================================================

def _cmd_queue_status() -> None:
    """Display the current state of the posting queue."""
    from ugc_ai_overpower.browser.content_queue import ContentQueue

    q = ContentQueue()
    stats = q.get_stats()
    print()
    print("  Content Queue Status")
    print("  " + "-" * 30)
    print(f"  Pending    : {stats['pending']}")
    print(f"  Processing : {stats['processing']}")
    print(f"  Done       : {stats['done']}")
    print(f"  Failed     : {stats['failed']}")
    print(f"  Total      : {stats['total']}")
    print()

    # Also show recent items.
    items = q.list_items(limit=10)
    if items:
        print("  Recent items (most recent first):")
        print(f"  {'ID':>4}  {'Content':>9}  {'Platform':12s}  {'Status':12s}  {'Retry':>5}  Post URL")
        print(f"  {'':->4}  {'':->9}  {'':->12}  {'':->12}  {'':->5}  {'':->40}")
        for it in items:
            url = (it["post_url"][:40] + "..") if it["post_url"] and len(it["post_url"]) > 40 else (it["post_url"] or "-")
            print(f"  {it['id']:>4}  {it['content_id']:>9}  {it['platform']:12s}  {it['status']:12s}  {it['retry_count']:>5}  {url}")
        print()


def _cmd_process_queue(orch: Orchestrator, platform: str = None) -> None:
    """Dequeue and dispatch one item."""
    logger.info(f"Processing queue (platform={platform or 'all'})…")
    orch.process_queue(platform)
    logger.info("Done.")


def _cmd_post(bank: ContentBank, orch: Orchestrator, content_id: int, platform: str) -> None:
    """Queue a content item for posting on *platform*."""
    # Validate that the content exists (quick sanity check).
    # Use the bank internal query – fetch the content row.
    conn = bank._get_conn()
    try:
        row = conn.execute("SELECT id, status FROM content WHERE id = ?", (content_id,)).fetchone()
        if row is None:
            logger.error(f"Content #{content_id} not found in database.")
            return
        # Allow posting even if in draft/ready state – just queue it.
    finally:
        conn.close()

    qid = orch.schedule_content(content_id, platform)
    logger.info(f"Content #{content_id} scheduled for {platform} (queue id={qid})")


def _cmd_scheduler() -> None:
    logger.info("Starting auto-pipeline daemon...")
    from ugc_ai_overpower.core.auto_pipeline import start_scheduler, initialize_components
    if initialize_components():
        start_scheduler(interval_hours=6)
        logger.info("Auto-pipeline daemon started (runs every 6h)")
    else:
        logger.error("Failed to initialize pipeline components")


def _cmd_analytics() -> None:
    logger.info("Showing analytics dashboard...")
    from ugc_ai_overpower.core.notion_sync import NotionDashboard
    nd = NotionDashboard()
    if not nd.ready:
        logger.error("Notion not configured")
        return
    print(f"\n  Notion Dashboard Analytics")
    print(f"  {'-'*40}")
    campaigns = nd.get_all_campaigns()
    total_content = sum(c.get("content_generated", 0) for c in campaigns)
    total_posts = sum(c.get("posts_published", 0) for c in campaigns)
    print(f"  Total campaigns  : {len(campaigns)}")
    print(f"  Total content    : {total_content}")
    print(f"  Total posts      : {total_posts}")
    print(f"  Active campaigns : {sum(1 for c in campaigns if c.get('status') == 'Active')}")
    print()


def _cmd_analytics_collect() -> None:
    """Run the analytics collector: aggregate bank engagement, push to Notion."""
    from ugc_ai_overpower.core.analytics_collector import AnalyticsCollector

    collector = AnalyticsCollector()
    daily = collector.daily_aggregate()
    print()
    print("  📊 Engagement Analytics Summary")
    print("  " + "-" * 40)
    print(f"  Content pieces : {daily.get('content_count', 0)}")
    print(f"  Views           : {int(daily.get('views', 0)):,}")
    print(f"  Likes           : {int(daily.get('likes', 0)):,}")
    print(f"  Comments        : {int(daily.get('comments', 0)):,}")
    print(f"  Shares          : {int(daily.get('shares', 0)):,}")
    print(f"  Clicks          : {int(daily.get('clicks', 0)):,}")
    print(f"  Engagement rate : {daily.get('engagement_rate', 0)}%")
    print(f"  Avg score       : {daily.get('avg_engagement_score') or 0}")
    print()
    print("  Pushing to Notion...")
    push_result = collector.push_to_notion()
    print(f"  Status          : {push_result.get('status')}")
    print(f"  Synced records  : {push_result.get('synced', 0)}")
    if push_result.get("campaigns_matched") is not None:
        print(f"  Campaigns hit   : {push_result.get('campaigns_matched')}")
    if push_result.get("message"):
        print(f"  Message         : {push_result.get('message')}")
    print()


def _cmd_generate_video(script: str, product_image: str = None) -> None:
    from ugc_ai_overpower.gpu.video_composer import VideoComposer
    vc = VideoComposer()
    logger.info(f"Generating video from script ({len(script)} chars)...")
    path = vc.create_ugc_video(script, "cli_user", product_image)
    logger.info(f"Video saved: {path}")

def _cmd_post_video(video_path: str, platform: str) -> None:
    from ugc_ai_overpower.browser.posters import get_poster
    logger.info(f"Posting {video_path} to {platform}...")
    poster = get_poster(platform)
    try:
        result = poster.post({"video_path": video_path, "script": "", "hashtags": []})
        if result.get("success"):
            logger.info(f"Posted! URL: {result.get('post_url')}")
        else:
            logger.error(f"Failed: {result.get('error')}")
    finally:
        poster.cleanup()

def _cmd_schedule_campaign(orch, product: str, interval_min: int, max_runs: int) -> None:
    from ugc_ai_overpower.scheduler.engine import SkynetScheduler
    sched = SkynetScheduler()
    job_id = sched.schedule_campaign(product, interval_min, max_runs)
    logger.info(f"Scheduled campaign '{product}' every {interval_min}min (job: {job_id})")
    sched.start()

def _cmd_unschedule(job_id: str) -> None:
    from ugc_ai_overpower.scheduler.engine import SkynetScheduler
    sched = SkynetScheduler()
    sched.unschedule_campaign(job_id)
    logger.info(f"Unscheduled: {job_id}")

def _cmd_list_jobs() -> None:
    from ugc_ai_overpower.scheduler.engine import SkynetScheduler
    sched = SkynetScheduler()
    jobs = sched.list_jobs()
    if not jobs:
        print("  No active jobs.")
        return
    for j in jobs:
        print(f"  {j['id']:30s} {j['name']:20s} next: {j['next_run'] or 'N/A'}")

def _cmd_cookie_save(platform: str, profile: str) -> None:
    from ugc_ai_overpower.browser.cookies import CookieManager
    cm = CookieManager()
    try:
        cm.save(platform, profile)
        print(f"✅ Cookies saved for {platform} profile '{profile}'")
    except Exception as e:
        print(f"❌ {e}")

def _cmd_cookie_list() -> None:
    from ugc_ai_overpower.browser.cookies import CookieManager
    cm = CookieManager()
    profiles = cm.list_profiles()
    if not profiles:
        print("  No cookie profiles found.")
        return
    print("  Cookie profiles:")
    for p in profiles:
        print(f"    - {p}")

def _cmd_api() -> None:
    logger.info("Starting FastAPI server...")
    import uvicorn
    from ugc_ai_overpower.web.dashboard import app
    uvicorn.run(app, host="0.0.0.0", port=8111, log_level="info")


# ======================================================================
# Notion handlers
# ======================================================================

def _get_notion():
    from ugc_ai_overpower.core.notion_sync import NotionDashboard
    nd = NotionDashboard()
    if not nd.ready:
        logger.error("Notion not configured. Set NOTION_TOKEN env var.")
        return None
    return nd


def _cmd_notion_init():
    nd = _get_notion()
    if not nd:
        return
    logger.info("Auto-creating Notion databases...")
    created = nd.auto_create_databases()
    if created:
        for name, db_id in created.items():
            print(f"  ✅ {name}: {db_id}")
        print("\n  Add these to your .env:\n"
              f"  NOTION_CAMPAIGN_DB={nd.campaign_db}\n"
              f"  NOTION_CONTENT_DB={nd.content_db}\n"
              f"  NOTION_ANALYTICS_DB={nd.analytics_db}")
    else:
        print("  ❌ No databases created. Check NOTION_PARENT_PAGE env var.")


def _cmd_notion_status():
    from ugc_ai_overpower.core.notion_sync import NotionDashboard
    nd = NotionDashboard()
    print(f"  Token configured : {'✅' if nd.token else '❌'}")
    db_fields = [
        ("Campaign DB", nd.campaign_db),
        ("Content DB", nd.content_db),
        ("Analytics DB", nd.analytics_db),
        ("Gallery DB", nd.gallery_db),
        ("Inbox DB", nd.inbox_db),
        ("Brands DB", nd.brands_db),
        ("Approvals DB", nd.approvals_db),
        ("Products DB", nd.products_db),
    ]
    for name, db_id in db_fields:
        if db_id:
            info = nd.get_database_info(db_id)
            title = info.get("title", [{}])
            title_text = ""
            if title and isinstance(title, list):
                for t in title:
                    title_text += t.get("plain_text", "")
            print(f"  {name:15s} : ✅ {title_text[:40]} ({db_id[:10]}...)")
        else:
            print(f"  {name:15s} : ❌ (not configured)")
    print(f"  Parent Page      : {os.getenv('NOTION_PARENT_PAGE', '(not set)')}")


def _cmd_notion_campaigns():
    nd = _get_notion()
    if not nd:
        return
    campaigns = nd.get_all_campaigns()
    if not campaigns:
        print("  No campaigns found.")
        return
    print(f"  {'Name':25s} {'Status':12s} {'Content':>8} {'Posts':>6} {'Created'}")
    print(f"  {'-'*25} {'-'*12} {'-'*8} {'-'*6} {'-'*12}")
    for c in campaigns:
        print(f"  {c['name'][:25]:25s} {c['status']:12s} {c['content_generated']:>8} {c['posts_published']:>6} {c['created_at'][:10]}")


def _cmd_notion_daily_report(date_str: str = None):
    nd = _get_notion()
    if not nd:
        return
    rid = nd.create_daily_report(date_str)
    if rid:
        print(f"  ✅ Daily report created: {rid}")
    else:
        print("  ❌ Failed to create daily report")


def _cmd_notion_sync(orch, product: str):
    nd = _get_notion()
    if not nd:
        return
    logger.info(f"Syncing campaign '{product}' to Notion...")
    result = orch.run_campaign(product)
    print(f"  ✅ Synced! Campaign ID: {result.get('notion_synced', '?')}")
    print(f"     Total content: {result['total']} pieces")


def _cmd_notion_sync_all():
    nd = _get_notion()
    if not nd:
        return
    from ugc_ai_overpower.core.gallery import Gallery
    from ugc_ai_overpower.browser.social_inbox import SocialInbox
    from ugc_ai_overpower.core.brand_profile import BrandProfile
    from ugc_ai_overpower.core.approval_workflow import ApprovalWorkflow
    from ugc_ai_overpower.mcp_server.tools.ai_tools import AIRouter
    ai = AIRouter(
        base_url=os.getenv("ROUTER_URL", "http://localhost:20128"),
        api_key=os.getenv("ROUTER_KEY", ""),
    )
    logger.info("Syncing ALL data to Notion...")
    results = nd.sync_all(
        gallery=Gallery(),
        inbox=SocialInbox(ai_router=ai),
        brand_profile=BrandProfile(),
        approval_workflow=ApprovalWorkflow(),
    )
    for key, items in results.items():
        print(f"  ✅ {key}: {len(items)} items synced")
    print("  ✅ All synced!")


def _cmd_notion_create_all_dbs():
    nd = _get_notion()
    if not nd:
        return
    logger.info("Creating all Notion databases...")
    created = nd.auto_create_databases()
    if created:
        for name, db_id in created.items():
            print(f"  ✅ {name}: {db_id}")
        print("\n  Add these to your .env:")
        for name, db_id in created.items():
            env_key = f"NOTION_{name.upper()}_DB"
            print(f"  {env_key}={db_id}")
    else:
        print("  ❌ No databases created. Check NOTION_PARENT_PAGE env var.")


def _cmd_notion_sync_products():
    nd = _get_notion()
    if not nd:
        return
    from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
    bank = ContentBankV2()
    products = bank.get_all_products(limit=500)
    if not products:
        print("  No products found in catalog.")
        return
    logger.info(f"Syncing {len(products)} affiliate products to Notion...")
    synced = nd.sync_products(products)
    print(f"  ✅ {len(synced)} products synced to Notion")


def _cmd_list_products():
    from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
    bank = ContentBankV2()
    products = bank.get_all_products(limit=100)
    if not products:
        print("  No products in catalog.")
        return
    print(f"\n  {'Name':45s} {'Platform':12s} {'Price':>10s} {'Comm%':>7s} {'Affiliate Link'}")
    print(f"  {'-'*45} {'-'*12} {'-'*10} {'-'*7} {'-'*50}")
    for p in products:
        aff = (p.get('affiliate_link') or '')[:50]
        name = (p.get('name') or '')[:45]
        print(f"  {name:45s} {p.get('platform',''):12s} Rp{p.get('price',0):>8,.0f} {p.get('commission_rate',0):>6.1f}% {aff}")


def _cmd_codespace_pool(sub: str, args: list) -> None:
    """codespace-pool CLI handler: status | dispatch | list."""
    try:
        from ugc_ai_overpower.core.codespace_pool import CodespacePool
    except Exception as exc:
        logger.error(f"Failed to import CodespacePool: {exc}")
        sys.exit(1)
    try:
        pool = CodespacePool()
    except FileNotFoundError as exc:
        logger.error(str(exc))
        logger.error("Hint: create .opencode/codespace_pool.json at repo root")
        sys.exit(1)
    except ValueError as exc:
        logger.error(f"Invalid pool config: {exc}")
        sys.exit(1)

    if sub == "list":
        for m in pool.pool:
            print(f"  {m['name']:18s} model={m.get('model',''):40s} region={m.get('region','-'):10s} machine={m.get('machine','-')}")
        print(f"  Total: {len(pool.pool)} codespaces")
    elif sub == "status":
        rows = pool.pool_status()
        print(f"\n  {'Status':8s} {'Name':18s} {'State':12s} {'Model':40s} {'Error'}")
        print(f"  {'-'*8} {'-'*18} {'-'*12} {'-'*40} {'-'*30}")
        healthy = 0
        for s in rows:
            flag = "OK" if s["healthy"] else "DOWN"
            err = (s.get("error") or "")[:30]
            print(f"  {flag:8s} {s['name']:18s} {s['state']:12s} {s['model']:40s} {err}")
            if s["healthy"]:
                healthy += 1
        print(f"  Healthy: {healthy}/{len(rows)}")
    elif sub == "dispatch":
        if not args:
            logger.error("Usage: codespace-pool dispatch <task description>")
            sys.exit(1)
        task = " ".join(args)
        result = pool.dispatch_task(task)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(result.get("returncode", 1) or 0)
    else:
        logger.error(f"Unknown codespace-pool subcommand: {sub}")
        logger.error("Usage: codespace-pool status | dispatch <task> | list")
        sys.exit(1)


if __name__ == "__main__":
    main()