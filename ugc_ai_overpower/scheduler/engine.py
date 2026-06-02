import os
import json
import time
import signal
import logging
from datetime import datetime, timedelta
from pathlib import Path

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
except ImportError:
    raise ImportError("Install apscheduler: pip install apscheduler")

from ugc_ai_overpower.core.content_bank import ContentBank
from ugc_ai_overpower.mcp_server.tools.ai_tools import AIRouter
from ugc_ai_overpower.mcp_server.tools.influencer_tools import InfluencerManager
from ugc_ai_overpower.core.orchestrator import Orchestrator
from ugc_ai_overpower.core.psychology import PsychologyEngine

logger = logging.getLogger("skynet.scheduler")

class SkynetScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler({
            "apscheduler.jobstores.default": {
                "type": "sqlalchemy",
                "url": "sqlite:///data/scheduler.db",
            },
            "apscheduler.executors.default": {
                "class": "apscheduler.executors.pool:ThreadPoolExecutor",
                "max_workers": 5,
            },
            "apscheduler.job_defaults.coalesce": True,
            "apscheduler.job_defaults.max_instances": 1,
        })

        self.bank = ContentBank()
        self.ai = AIRouter(
            base_url=os.getenv("ROUTER_URL", "http://localhost:20128"),
            api_key=os.getenv("ROUTER_KEY", ""),
        )
        self.influencer_mgr = InfluencerManager()
        self.psychology = PsychologyEngine()
        self.orchestrator = Orchestrator(self.bank, self.ai)

        self._register_listeners()
        self._load_campaign_queue()

    def _register_listeners(self):
        def job_listener(event):
            if event.exception:
                logger.error("Job %s failed: %s", event.job_id, event.exception)
            else:
                logger.info("Job %s completed successfully", event.job_id)

        self.scheduler.add_listener(
            job_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
        )

    def _load_campaign_queue(self):
        path = "data/campaign_queue.json"
        if Path(path).exists():
            with open(path) as f:
                queue = json.load(f)
            for item in queue:
                self.schedule_campaign(
                    item["product"],
                    item.get("interval_minutes", 60),
                    item.get("max_runs", 0),
                )
            logger.info("Loaded %d queued campaigns", len(queue))

    def schedule_campaign(self, product: str, interval_minutes: int = 60, max_runs: int = 0):
        job_id = f"campaign_{hash(product)}_{int(time.time())}"

        def run_campaign():
            logger.info("Executing scheduled campaign: %s", product)
            try:
                result = self.orchestrator.run_campaign(product)
                logger.info("Campaign complete: %d content pieces", result.get("total", 0))

                webhook_payload = {
                    "product": product,
                    "total": result.get("total", 0),
                    "campaign_id": result.get("campaign_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                }

                from ugc_ai_overpower.web.webhooks import webhook_manager
                webhook_manager.dispatch("campaign.completed", webhook_payload)

            except Exception as e:
                logger.error("Campaign failed for %s: %s", product, e)
                from ugc_ai_overpower.web.webhooks import webhook_manager
                webhook_manager.dispatch("campaign.failed", {"product": product, "error": str(e)})

        trigger = IntervalTrigger(minutes=interval_minutes)
        self.scheduler.add_job(
            run_campaign,
            trigger=trigger,
            id=job_id,
            name=f"Campaign: {product}",
            replace_existing=True,
            max_instances=1,
        )

        if max_runs > 0:
            expiry = datetime.utcnow() + timedelta(minutes=interval_minutes * max_runs)
            self.scheduler.modify_job(job_id, next_run_time=datetime.utcnow())
            # Schedule removal after max_runs
            self.scheduler.add_job(
                lambda: self.unschedule_campaign(job_id),
                trigger="date",
                run_date=expiry,
                id=f"{job_id}_expire",
            )

        logger.info("Scheduled campaign '%s' every %d min (max runs: %s)", product, interval_minutes, max_runs or "unlimited")
        self._persist_queue()
        return job_id

    def unschedule_campaign(self, job_id: str):
        try:
            self.scheduler.remove_job(job_id)
            logger.info("Unscheduled campaign: %s", job_id)
        except Exception as e:
            logger.warning("Failed to unschedule %s: %s", job_id, e)
        self._persist_queue()

    def _persist_queue(self):
        jobs = []
        for job in self.scheduler.get_jobs():
            if job.name.startswith("Campaign:"):
                jobs.append({
                    "product": job.name.replace("Campaign: ", ""),
                    "interval_minutes": job.trigger.interval_length // 60 if hasattr(job.trigger, "interval_length") else 60,
                })
        os.makedirs("data", exist_ok=True)
        with open("data/campaign_queue.json", "w") as f:
            json.dump(jobs, f, indent=2)

    def list_jobs(self) -> list[dict]:
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in self.scheduler.get_jobs()
        ]

    def start(self):
        self.scheduler.start()
        logger.info("Skynet Scheduler started")

        # Keep alive
        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        signal.signal(signal.SIGINT, lambda *_: self.stop())

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        logger.info("Shutting down scheduler...")
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")

def serve():
    scheduler = SkynetScheduler()
    scheduler.start()
