"""Dispatcher — routes heavy adapter work to codespace.

VPS calls dispatcher methods, which:
  1. Serialize the request
  2. Dispatch to codespace via `gh codespace ssh` 
  3. Codespace runs the actual adapter code
  4. Returns JSON result

VPS never blocks >5s. If codespace is unavailable, return graceful error.
"""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict
from typing import Any, Optional

from ugc_ai_overpower.integrations.base import (
    AccountInfo,
    AffiliateLink,
    EngagementMetrics,
    PlatformAdapter,
    PostResult,
)
from ugc_ai_overpower.integrations.registry import get_adapter, list_platforms

log = logging.getLogger(__name__)

DEFAULT_CODESPACE = "symmetrical-palm-tree-5gpr979vgv6jhvqr"
DEFAULT_TIMEOUT = 60


class DispatchError(Exception):
    pass


def _is_gh_available() -> bool:
    import shutil
    return shutil.which("gh") is not None


def _dispatch_to_codespace(task: str, payload: dict[str, Any],
                           codespace: str = DEFAULT_CODESPACE,
                           timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Run a Python expression in codespace and return JSON result."""
    if not _is_gh_available():
        raise DispatchError("gh CLI not available on VPS")
    payload_b64 = _to_base64(json.dumps(payload))
    remote_cmd = (
        f"echo '{payload_b64}' | base64 -d > /tmp/dispatch_payload.json && "
        f"cd /workspaces/Coba 2>/dev/null || cd ~; "
        f"PYTHONPATH=$(pwd) python3 -c \""
        f"import json, sys; "
        f"from ugc_ai_overpower.integrations.runner import run_task; "
        f"payload = json.load(open('/tmp/dispatch_payload.json')); "
        f"result = run_task('{task}', payload); "
        f"print('__RESULT__' + json.dumps(result))"
        f"\""
    )
    cmd = ["gh", "codespace", "ssh", "-c", codespace, "--", "bash", "-lc", remote_cmd]
    log.info("Dispatching %s to codespace %s", task, codespace)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout
        if "__RESULT__" in output:
            json_str = output.split("__RESULT__", 1)[1].strip()
            for line in json_str.split("\n"):
                line = line.strip()
                if line.startswith("{"):
                    return json.loads(line)
        return {
            "ok": False,
            "error": "no result returned",
            "stdout": result.stdout[-500:],
            "stderr": result.stderr[-500:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _to_base64(s: str) -> str:
    import base64
    return base64.b64encode(s.encode()).decode()


def dispatch_post(platform: str, content: str, media_urls: list[str] = None,
                  metadata: dict[str, Any] = None) -> PostResult:
    """Dispatch a post request to codespace."""
    payload = {
        "platform": platform,
        "content": content,
        "media_urls": media_urls or [],
        "metadata": metadata or {},
    }
    result = _dispatch_to_codespace("post", payload)
    return PostResult(
        platform=platform,
        status=result.get("status", "error"),
        post_id=result.get("post_id", ""),
        post_url=result.get("post_url", ""),
        error=result.get("error"),
        raw=result,
    )


def dispatch_engagement(platform: str, post_url: str) -> EngagementMetrics:
    """Dispatch engagement fetch to codespace."""
    payload = {"platform": platform, "post_url": post_url}
    result = _dispatch_to_codespace("engagement", payload)
    return EngagementMetrics(
        views=result.get("views", 0),
        likes=result.get("likes", 0),
        comments=result.get("comments", 0),
        shares=result.get("shares", 0),
        saves=result.get("saves", 0),
        clicks=result.get("clicks", 0),
        engagement_score=result.get("engagement_score", 0.0),
        fetched_at=result.get("fetched_at", ""),
    )


def dispatch_account(platform: str, username: str) -> AccountInfo:
    """Dispatch account info fetch to codespace."""
    payload = {"platform": platform, "username": username}
    result = _dispatch_to_codespace("account", payload)
    return AccountInfo(
        platform=platform,
        username=result.get("username", username),
        display_name=result.get("display_name", ""),
        followers=result.get("followers", 0),
        following=result.get("following", 0),
        posts=result.get("posts", 0),
        verified=result.get("verified", False),
        profile_url=result.get("profile_url", ""),
    )


def dispatch_affiliate_link(platform: str, product_url: str,
                            sub_ids: list[str] = None) -> AffiliateLink:
    """Dispatch affiliate link generation to codespace."""
    payload = {
        "platform": platform,
        "product_url": product_url,
        "sub_ids": sub_ids or [],
    }
    result = _dispatch_to_codespace("affiliate", payload)
    return AffiliateLink(
        platform=platform,
        product_id=result.get("product_id", ""),
        original_url=product_url,
        affiliate_url=result.get("affiliate_url", ""),
        commission_rate=result.get("commission_rate", 0.0),
        short_url=result.get("short_url", ""),
    )


def list_available_platforms() -> list[str]:
    """List platforms the local registry knows about (instant, no dispatch)."""
    return list_platforms()


def platform_health(platform: str) -> dict[str, Any]:
    """Lightweight health check that runs on VPS (no dispatch)."""
    adapter = get_adapter(platform)
    if adapter is None:
        return {"platform": platform, "ok": False, "error": "unknown platform"}
    return {"platform": platform, "ok": True, "configured": adapter.is_configured()}
