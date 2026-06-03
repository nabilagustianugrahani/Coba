"""Affiliator Agent — matches scripts to affiliate products, injects links."""
import logging, random

from swarm.base_agent import BaseAgent
from ugc_ai_overpower.core.affiliator import Affiliator

log = logging.getLogger(__name__)


class AffiliatorAgent(BaseAgent):
    name = "affiliator"

    def __init__(self):
        super().__init__(poll_interval=1.0, max_concurrent=2)
        self._affiliator = Affiliator()

    def handle_match_products(self, msg: dict) -> dict:
        payload = msg["payload"]
        campaign_id = payload.get("campaign_id", "")
        scripts = payload.get("scripts", [])
        niche = payload.get("niche", "general")

        log.info("[AFF] Searching products for niche: %s (%d scripts)", niche, len(scripts))
        products = self._affiliator.search_products(niche, limit=10)

        if products:
            self._affiliator.save_catalog(products)
            log.info("[AFF] Found %d products, matching to scripts...", len(products))
            matches = self._affiliator.match_to_scripts(scripts, products)
            for m in matches:
                if m.injected_script:
                    scripts[m.script_index]["script"] = m.injected_script
                    scripts[m.script_index]["affiliate_link"] = m.affiliate_link
                    scripts[m.script_index]["affiliate_product"] = m.product.name
        else:
            log.info("[AFF] No products found, skipping affiliate injection")

        self.send("orchestrator", "affiliate_done", {
            "campaign_id": campaign_id,
            "scripts": scripts,
        })
        return {"campaign_id": campaign_id, "matched": len(products)}
