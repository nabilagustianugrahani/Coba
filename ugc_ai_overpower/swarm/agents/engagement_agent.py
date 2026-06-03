"""Engagement Agent — auto like/comment/follow on schedules."""
import logging, random, asyncio
from datetime import datetime

from swarm.base_agent import BaseAgent

log = logging.getLogger(__name__)

NICHES = ["skincare", "fashion", "food", "tech", "lifestyle"]
COMMENTS = [
    "Mantap banget! 🔥", "Wah keren, gue juga pake ini!", "Recommended banget!",
    "Baru tau ada yang kayak gini!", "Share dong linknya kak!",
    "Ini mah udah wajib punya sih!", "Gila, review paling jujur!",
]


class EngagementAgent(BaseAgent):
    name = "engagement"

    def __init__(self, engage_hours: int = 4):
        super().__init__(poll_interval=30.0, max_concurrent=1)
        self.engage_hours = engage_hours
        self._last_engage = {}

    def tick(self):
        now = datetime.now()
        for niche in NICHES:
            last = self._last_engage.get(niche)
            if not last or (now - last).total_seconds() >= self.engage_hours * 3600:
                self._do_engage(niche)
                self._last_engage[niche] = now

    def _do_engage(self, niche: str):
        log.info("[ENG] Auto-engaging in niche: %s", niche)
        try:
            from ugc_ai_overpower.browser.bu_engage import BUEngageAgent
            agent = BUEngageAgent()
            result = asyncio.run(agent.batch_engage(niche, "tiktok", likes=10, follows=3, comments=2))
            if result.success:
                log.info("[ENG] Engaged in %s: %s", niche, result.output[:100])
            else:
                log.warning("[ENG] Engage failed for %s: %s", niche, result.error)
        except Exception as e:
            log.warning("[ENG] Engage error for %s: %s", niche, e)

    def handle_engage_now(self, msg: dict) -> dict:
        niche = msg["payload"].get("niche", random.choice(NICHES))
        self._do_engage(niche)
        return {"niche": niche, "status": "done"}

    def handle_set_interval(self, msg: dict) -> dict:
        hours = msg["payload"].get("hours", 4)
        self.engage_hours = hours
        log.info("[ENG] Engage interval set to %dh", hours)
        return {"interval_hours": hours}
