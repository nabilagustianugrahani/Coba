"""Auto Pipeline Daemon — runs full UGC pipeline on schedule."""

import os
import sys
import time
import signal
import logging
import atexit
from datetime import datetime
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ugc_ai_overpower.core.pipeline_engine import PipelineEngine
from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
from ugc_ai_overpower.core.notion_sync import NotionDashboard

log = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[BackgroundScheduler] = None
pipeline_engine: Optional[PipelineEngine] = None
content_bank: Optional[ContentBankV2] = None

# PID file location
PID_FILE = Path("/tmp/ugc_autopipeline.pid")
LOG_FILE = Path("/tmp/ugc_autopipeline.log")


def setup_logging():
    """Setup logging to file and console."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )


def write_pid_file():
    """Write current process ID to PID file."""
    PID_FILE.write_text(str(os.getpid()))
    log.info(f"PID file written: {PID_FILE}")


def remove_pid_file():
    """Remove PID file on exit."""
    if PID_FILE.exists():
        PID_FILE.unlink()
        log.info(f"PID file removed: {PID_FILE}")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    log.info(f"Received signal {signum}, shutting down...")
    stop_scheduler()
    sys.exit(0)


def initialize_components():
    """Initialize pipeline engine and content bank."""
    global pipeline_engine, content_bank
    
    try:
        # Initialize content bank
        content_bank = ContentBankV2()
        log.info("Content bank initialized")
        
        # Initialize pipeline engine (will use default AI router from environment)
        pipeline_engine = PipelineEngine()
        log.info("Pipeline engine initialized")
        
        return True
    except Exception as e:
        log.error(f"Failed to initialize components: {e}")
        return False


def run_pipeline_for_all_products():
    """Run the full pipeline for all active products."""
    if not pipeline_engine or not content_bank:
        log.error("Components not initialized")
        return {"status": "error", "message": "Components not initialized"}

    run_timestamp = datetime.now().isoformat()

    try:
        log.info("Starting auto-pipeline run for all products")
        start_time = time.time()

        products = content_bank.get_all_products(limit=1000)
        if not products:
            log.warning("No products found in content bank")
            return {"status": "skipped", "reason": "no_products", "products_processed": 0}

        log.info(f"Found {len(products)} products to process")

        result = pipeline_engine.run_full_pipeline()

        elapsed_time = time.time() - start_time
        log.info(f"Auto-pipeline completed in {elapsed_time:.2f}s: {result}")

        products_processed = result.get("products_processed", 0)
        details = result.get("details", [])
        scripts_generated = sum(
            d.get("scripts_generated", 0) for d in details
        ) if details else products_processed * 3

        run_result = {
            "status": "completed",
            "products_processed": products_processed,
            "scripts_generated": scripts_generated,
            "elapsed_seconds": round(elapsed_time, 2),
            "run_timestamp": run_timestamp,
            "details": details,
        }

        try:
            notion_dashboard = NotionDashboard()
            report_id = notion_dashboard.create_daily_report()
            if report_id:
                run_result["notion_status"] = "success"
                run_result["notion_report_id"] = report_id
                log.info(f"Notion daily report created: {report_id}")
            else:
                run_result["notion_status"] = "fail"
                log.warning("Notion daily report creation returned no ID")
        except Exception as ne:
            run_result["notion_status"] = "fail"
            log.error(f"Notion sync failed (non-fatal): {ne}", exc_info=True)

        log.info(
            f"Run summary: timestamp={run_timestamp} "
            f"products={products_processed} scripts={scripts_generated} "
            f"duration={elapsed_time:.2f}s notion={run_result.get('notion_status', 'skipped')}"
        )

        return run_result

    except Exception as e:
        log.error(f"Error running pipeline: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "run_timestamp": run_timestamp}


def start_scheduler(interval_hours: int = 6):
    """Start the background scheduler."""
    global scheduler
    
    if scheduler and scheduler.running:
        log.warning("Scheduler is already running")
        return False
    
    try:
        scheduler = BackgroundScheduler()
        
        # Add job to run pipeline every N hours
        scheduler.add_job(
            func=run_pipeline_for_all_products,
            trigger=IntervalTrigger(hours=interval_hours),
            id='full_pipeline_job',
            name='Run full UGC pipeline',
            replace_existing=True,
            max_instances=1,  # Prevent overlapping runs
            coalesce=True,    # Combine missed runs
        )
        
        scheduler.start()
        log.info(f"Scheduler started - pipeline will run every {interval_hours} hours")
        
        # Run immediately on startup
        log.info("Running initial pipeline...")
        run_pipeline_for_all_products()
        
        return True
        
    except Exception as e:
        log.error(f"Failed to start scheduler: {e}")
        return False


def stop_scheduler():
    """Stop the background scheduler."""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        scheduler = None
        log.info("Scheduler stopped")
    else:
        log.info("Scheduler is not running")


def status_scheduler():
    """Check if scheduler is running and get status."""
    global scheduler
    
    if scheduler and scheduler.running:
        jobs = scheduler.get_jobs()
        job_info = []
        for job in jobs:
            job_info.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return {
            "running": True,
            "jobs": job_info
        }
    else:
        return {
            "running": False,
            "jobs": []
        }


def main():
    """Main entry point for the auto-pipeline daemon."""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(remove_pid_file)
    
    # Setup logging
    setup_logging()
    
    log.info("=" * 50)
    log.info("UGC AUTO PIPELINE DAEMON")
    log.info("=" * 50)
    
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python auto_pipeline.py <command>")
        print("Commands:")
        print("  start          - Start the daemon")
        print("  stop           - Stop the daemon")
        print("  status         - Show daemon status")
        print("  run-once       - Run pipeline once and exit")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "start":
        # Write PID file
        write_pid_file()
        
        # Initialize components
        if not initialize_components():
            log.error("Failed to initialize components")
            sys.exit(1)
        
        # Start scheduler
        if not start_scheduler(interval_hours=6):  # Default 6 hours
            log.error("Failed to start scheduler")
            sys.exit(1)
        
        log.info("Auto-pipeline daemon started successfully")
        log.info("Press Ctrl+C to stop")
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(60)  # Sleep for 1 minute intervals
        except KeyboardInterrupt:
            log.info("Received keyboard interrupt")
        
    elif command == "stop":
        # Remove PID file
        remove_pid_file()
        
        # Stop scheduler
        stop_scheduler()
        log.info("Auto-pipeline daemon stopped")
        
    elif command == "status":
        # Check if PID file exists
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            try:
                # Check if process is still running
                os.kill(int(pid), 0)
                pid_status = f"running (PID: {pid})"
            except (OSError, ValueError):
                pid_status = f"stale PID file (PID: {pid})"
        else:
            pid_status = "not running (no PID file)"
        
        # Get scheduler status
        scheduler_status = status_scheduler()
        
        print("Auto Pipeline Daemon Status:")
        print(f"  Process: {pid_status}")
        print(f"  Scheduler: {'running' if scheduler_status['running'] else 'stopped'}")
        
        if scheduler_status['jobs']:
            print("  Jobs:")
            for job in scheduler_status['jobs']:
                print(f"    - {job['name']} (ID: {job['id']})")
                print(f"      Next run: {job['next_run'] or 'Not scheduled'}")
                print(f"      Trigger: {job['trigger']}")
        else:
            print("  Jobs: None")
        
    elif command == "run-once":
        # Initialize components
        if not initialize_components():
            log.error("Failed to initialize components")
            sys.exit(1)
        
        # Run pipeline once
        log.info("Running pipeline once...")
        result = run_pipeline_for_all_products()
        
        if result.get("status") == "completed":
            log.info(f"Pipeline completed successfully: {result.get('products_processed', 0)} products processed")
        else:
            log.error(f"Pipeline failed: {result}")
            sys.exit(1)
        
    else:
        log.error(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()