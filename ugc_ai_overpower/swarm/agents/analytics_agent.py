"""Analytics Agent — tracks performance, reports daily summaries."""
import logging
from datetime import datetime

from swarm.base_agent import BaseAgent

log = logging.getLogger(__name__)


class AnalyticsAgent(BaseAgent):
    name = "analytics"

    def __init__(self):
        super().__init__(poll_interval=60.0, max_concurrent=2)
        self._last_report = None

    def tick(self):
        now = datetime.now()
        if self._last_report is None or (now - self._last_report).total_seconds() >= 86400:
            self._daily_report()
            self._last_report = now

    def _daily_report(self):
        log.info("[ANL] Generating daily report...")
        campaign_stats = self._get_campaign_stats()
        queue_stats = self._get_queue_stats()
        report = {
            "date": datetime.now().isoformat()[:10],
            "campaigns": campaign_stats,
            "queue": queue_stats,
            "agents": self._get_agent_health(),
        }
        self.broadcast("daily_report", report)
        log.info("[ANL] Daily report: %s", report)

    def _get_campaign_stats(self) -> dict:
        try:
            from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
            bank = ContentBankV2()
            return {"total_content": bank.get_stats().get("total_content", 0)}
        except Exception as e:
            return {"error": str(e)}

    def _get_queue_stats(self) -> dict:
        try:
            from ugc_ai_overpower.browser.content_queue import ContentQueue
            q = ContentQueue()
            return q.get_stats()
        except Exception as e:
            return {"error": str(e)}

    def _get_agent_health(self) -> dict:
        try:
            from ugc_ai_overpower.swarm.message_bus import MessageBus
            return MessageBus().health()
        except Exception as e:
            return {"error": str(e)}

    def handle_request_report(self, msg: dict) -> dict:
        return {
            "campaign_stats": self._get_campaign_stats(),
            "queue_stats": self._get_queue_stats(),
            "bus_health": self._get_agent_health(),
        }

    def handle_daily_report(self, msg: dict) -> dict:
        log.info("[ANL] Received daily report from orchestrator")
        return {"status": "logged"}
