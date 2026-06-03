"""Orchestrator — Queen Agent: dispatches campaigns, monitors swarm health.

Responsibilities:
  - Accept user commands
  - Decompose into subtasks → dispatch to agents
  - Track progress across all agents
  - Recover failed tasks (retry × 3)
  - Report campaign status
"""
import json, logging, time, threading
from datetime import datetime
from typing import Optional

from swarm.message_bus import MessageBus
from swarm.base_agent import BaseAgent

log = logging.getLogger(__name__)

MAX_RETRIES = 3
CAMPAIGNS = {}


class OrchestratorAgent(BaseAgent):
    name = "orchestrator"

    def __init__(self, ai_router=None):
        super().__init__(poll_interval=0.5, max_concurrent=10)
        self.ai_router = ai_router
        self._campaigns = {}
        self._agent_registry = {}

    def tick(self):
        self._check_campaigns()
        self._retry_failed()

    def handle_campaign(self, msg: dict) -> dict:
        """Start a full campaign — decompose and dispatch to agents."""
        payload = msg["payload"]
        product = payload.get("product", "")
        niche = payload.get("niche", "general")
        count = payload.get("count", 50)
        platforms = payload.get("platforms", ["tiktok"])
        generate_video = payload.get("generate_video", True)
        use_affiliate = payload.get("use_affiliate", True)

        campaign_id = f"campaign_{product.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        CAMPAIGNS[campaign_id] = {
            "id": campaign_id,
            "product": product,
            "niche": niche,
            "count": count,
            "platforms": platforms,
            "status": "running",
            "steps": {},
            "created_at": datetime.now().isoformat(),
        }

        log.info("[ORCH] Campaign %s — dispatching", campaign_id)

        # Step 1: Generate scripts
        script_task = self.send("script_writer", "generate_scripts", {
            "campaign_id": campaign_id,
            "product": product,
            "niche": niche,
            "count": count,
            "platforms": platforms,
        })

        return {"campaign_id": campaign_id, "status": "dispatched", "steps": ["generate_scripts"]}

    def handle_scripts_ready(self, msg: dict) -> dict:
        """Scripts generated — proceed to affiliate matching."""
        payload = msg["payload"]
        campaign_id = payload.get("campaign_id", "")
        scripts = payload.get("scripts", [])

        if campaign_id not in CAMPAIGNS:
            return {"error": "unknown campaign"}
        CAMPAIGNS[campaign_id]["steps"]["scripts_ready"] = len(scripts)

        if payload.get("use_affiliate", True):
            self.send("affiliator", "match_products", {
                "campaign_id": campaign_id,
                "scripts": scripts,
                "niche": CAMPAIGNS[campaign_id].get("niche", "general"),
            })
            return {"campaign_id": campaign_id, "status": "affiliate_matching"}
        else:
            self.send("video_producer", "render_videos", {
                "campaign_id": campaign_id,
                "scripts": scripts,
            })
            return {"campaign_id": campaign_id, "status": "rendering"}

    def handle_affiliate_done(self, msg: dict) -> dict:
        """Affiliate matching done — proceed to video rendering."""
        payload = msg["payload"]
        campaign_id = payload.get("campaign_id", "")
        scripts = payload.get("scripts", [])

        if campaign_id not in CAMPAIGNS:
            return {"error": "unknown campaign"}
        CAMPAIGNS[campaign_id]["steps"]["affiliate_done"] = len(scripts)

        self.send("video_producer", "render_videos", {
            "campaign_id": campaign_id,
            "scripts": scripts,
        })
        return {"campaign_id": campaign_id, "status": "rendering"}

    def handle_videos_ready(self, msg: dict) -> dict:
        """Videos generated — proceed to posting."""
        payload = msg["payload"]
        campaign_id = payload.get("campaign_id", "")
        videos = payload.get("videos", [])

        if campaign_id not in CAMPAIGNS:
            return {"error": "unknown campaign"}
        CAMPAIGNS[campaign_id]["steps"]["videos_ready"] = len(videos)

        platforms = CAMPAIGNS[campaign_id].get("platforms", ["tiktok"])
        self.send("poster", "post_videos", {
            "campaign_id": campaign_id,
            "videos": videos,
            "platforms": platforms,
        })
        return {"campaign_id": campaign_id, "status": "posting"}

    def handle_posting_done(self, msg: dict) -> dict:
        """All videos posted — campaign complete."""
        payload = msg["payload"]
        campaign_id = payload.get("campaign_id", "")
        results = payload.get("results", [])

        if campaign_id in CAMPAIGNS:
            CAMPAIGNS[campaign_id]["status"] = "complete"
            CAMPAIGNS[campaign_id]["steps"]["posted"] = len(results)
            CAMPAIGNS[campaign_id]["completed_at"] = datetime.now().isoformat()

        self.broadcast("campaign_complete", {
            "campaign_id": campaign_id,
            "results": results,
        })
        return {"campaign_id": campaign_id, "status": "complete"}

    def handle_agent_hello(self, msg: dict) -> dict:
        """Register agent in registry."""
        payload = msg["payload"]
        name = payload.get("name", msg["sender"])
        self._agent_registry[name] = {
            "name": name,
            "status": payload.get("status", "online"),
            "last_seen": datetime.now().isoformat(),
        }
        return {"status": "registered"}

    def handle_agent_status(self, msg: dict) -> dict:
        """Update agent status."""
        payload = msg["payload"]
        name = msg["sender"]
        if name in self._agent_registry:
            self._agent_registry[name].update(payload)
            self._agent_registry[name]["last_seen"] = datetime.now().isoformat()
        return {"status": "updated"}

    def _check_campaigns(self):
        """Check for stale campaigns and fail them."""
        for cid, c in list(CAMPAIGNS.items()):
            if c["status"] == "running":
                age = (datetime.now() - datetime.fromisoformat(c["created_at"])).total_seconds()
                if age > 86400:
                    c["status"] = "timeout"
                    log.warning("[ORCH] Campaign %s timed out after %.0fs", cid, age)

    def _retry_failed(self):
        """Retry failed messages up to MAX_RETRIES."""
        conn = self.bus._get_conn()
        rows = conn.execute(
            "SELECT id, sender, recipient, msg_type, payload, created_at FROM messages "
            "WHERE status = 'failed' AND msg_type != 'agent_hello'",
        ).fetchall()
        for row in rows:
            msg_id, sender, recipient, msg_type, payload_raw, created_at = row
            payload = json.loads(payload_raw or "{}")
            retries = payload.get("retries", 0)
            if retries < MAX_RETRIES:
                payload["retries"] = retries + 1
                self.bus.send(sender, recipient, msg_type, payload)
                conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
                conn.commit()
                log.info("[ORCH] Retrying msg %d (%s) attempt %d", msg_id, msg_type, retries + 1)

    def handle_list_agents(self, msg: dict) -> dict:
        return {"agents": self._agent_registry, "campaigns": len(CAMPAIGNS)}

    def handle_list_campaigns(self, msg: dict) -> dict:
        return {"campaigns": list(CAMPAIGNS.values())}
