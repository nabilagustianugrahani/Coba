"""Codespace-side runner — executes dispatched tasks.

This module runs IN THE CODESPACE. It receives JSON payloads from the VPS
dispatcher and runs the actual adapter code there.

Heavy work happens here:
  - Real API calls (TikHub, Shopee Open API, etc.)
  - Web scraping (Playwright, requests)
  - Video/image processing
  - Token refresh
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

log = logging.getLogger(__name__)


def run_task(task: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run a dispatched task and return JSON-serializable result."""
    log.info("Running task: %s with payload keys: %s", task, list(payload.keys()))
    try:
        if task == "post":
            from ugc_ai_overpower.integrations.social_dispatch import do_post
            return do_post(payload)
        if task == "engagement":
            from ugc_ai_overpower.integrations.social_dispatch import do_engagement
            return do_engagement(payload)
        if task == "account":
            from ugc_ai_overpower.integrations.social_dispatch import do_account
            return do_account(payload)
        if task == "affiliate":
            from ugc_ai_overpower.integrations.ecom_dispatch import do_affiliate
            return do_affiliate(payload)
        return {"ok": False, "error": f"unknown task: {task}"}
    except Exception as e:
        log.exception("Task %s failed", task)
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    task = sys.argv[1]
    payload = json.load(sys.stdin)
    result = run_task(task, payload)
    print("__RESULT__" + json.dumps(result, default=str))
