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
        logger.info("  analyze <product>      — Analyze product market")
        logger.info("  search <keyword>       — Search affiliate products")
        logger.info("  list-influencers       — Show all influencer personas")
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
    logger.info("Starting content scheduler daemon...")
    # TODO: Implement scheduler daemon
    # For now, we just print a message and exit.
    logger.info("Scheduler daemon started (placeholder).")


def _cmd_analytics() -> None:
    logger.info("Showing analytics dashboard...")
    # TODO: Implement analytics dashboard
    logger.info("Analytics dashboard (placeholder).")


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
    from ugc_ai_overpower.api.routes import app
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()