"""Pre-built notification event helpers for common UGC pipeline scenarios.

Each factory returns a fully-populated NotificationEvent ready for dispatch.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ugc_ai_overpower.core.notifications import NotificationEvent


def campaign_launched(campaign_id: str, niche: str, owner: str) -> NotificationEvent:
    return NotificationEvent(
        event_type="campaign.launched",
        severity="info",
        title=f"Campaign Launched: {campaign_id}",
        message=f"New {niche} campaign launched by {owner}",
        data={"campaign_id": campaign_id, "niche": niche, "owner": owner},
        source="orchestrator",
    )


def content_viral(content_id: str, platform: str, views: int, hours_to_viral: float) -> NotificationEvent:
    return NotificationEvent(
        event_type="content.viral",
        severity="warning",
        title=f"Content Going Viral on {platform}!",
        message=f"Content {content_id} hit {views:,} views in {hours_to_viral:.1f}h",
        data={"content_id": content_id, "platform": platform, "views": views, "hours_to_viral": hours_to_viral},
        source="analytics",
    )


def rate_limit_hit(api: str, limit: int, reset_seconds: int) -> NotificationEvent:
    return NotificationEvent(
        event_type="rate_limit.hit",
        severity="warning",
        title=f"Rate Limit Hit: {api}",
        message=f"{api} rate limit ({limit}/hr) reached, resets in {reset_seconds}s",
        data={"api": api, "limit": limit, "reset_seconds": reset_seconds},
        source="rate_limiter",
    )


def circuit_breaker_open(service: str, failure_rate: float) -> NotificationEvent:
    return NotificationEvent(
        event_type="circuit.open",
        severity="error",
        title=f"Circuit Breaker Open: {service}",
        message=f"Circuit breaker tripped for {service} (failure rate: {failure_rate:.1%})",
        data={"service": service, "failure_rate": failure_rate},
        source="circuit_breaker",
    )


def autoheal_restart(component: str, attempt: int, reason: str) -> NotificationEvent:
    return NotificationEvent(
        event_type="autoheal.restart",
        severity="info",
        title=f"Auto-Heal Restart: {component}",
        message=f"Attempt #{attempt} to restart {component}: {reason}",
        data={"component": component, "attempt": attempt, "reason": reason},
        source="autoheal",
    )


def webhook_received(source: str, event_type: str) -> NotificationEvent:
    return NotificationEvent(
        event_type="webhook.received",
        severity="info",
        title=f"Webhook Received from {source}",
        message=f"Incoming webhook: {event_type} from {source}",
        data={"source": source, "event_type": event_type},
        source="webhook_server",
    )


def notion_sync_success(synced: int, failed: int, duration_sec: float) -> NotificationEvent:
    return NotificationEvent(
        event_type="sync.success",
        severity="info",
        title="Notion Sync Completed",
        message=f"Synced {synced} items ({failed} failed) in {duration_sec:.1f}s",
        data={"synced": synced, "failed": failed, "duration_sec": duration_sec},
        source="notion_sync",
    )


def notion_sync_failed(error: str, batch_size: int) -> NotificationEvent:
    return NotificationEvent(
        event_type="sync.failed",
        severity="error",
        title="Notion Sync Failed",
        message=f"Batch of {batch_size} items failed: {error}",
        data={"error": error, "batch_size": batch_size},
        source="notion_sync",
    )


def quota_warning(service: str, used_pct: float) -> NotificationEvent:
    return NotificationEvent(
        event_type="quota.warning",
        severity="warning",
        title=f"Quota Warning: {service}",
        message=f"{service} at {used_pct:.1f}% of allocated quota",
        data={"service": service, "used_pct": used_pct},
        source="quotas",
    )


def quota_exceeded(service: str, reset_at: str) -> NotificationEvent:
    return NotificationEvent(
        event_type="quota.exceeded",
        severity="error",
        title=f"Quota Exceeded: {service}",
        message=f"{service} quota exhausted, resets at {reset_at}",
        data={"service": service, "reset_at": reset_at},
        source="quotas",
    )


def cost_alert(daily_cost: float, threshold: float) -> NotificationEvent:
    return NotificationEvent(
        event_type="cost.alert",
        severity="critical" if daily_cost >= threshold else "warning",
        title=f"Daily Cost Alert: ${daily_cost:.2f}",
        message=f"Daily spend ${daily_cost:.2f} exceeds threshold ${threshold:.2f}",
        data={"daily_cost": daily_cost, "threshold": threshold},
        source="billing",
    )


def deploy_success(version: str, environment: str) -> NotificationEvent:
    return NotificationEvent(
        event_type="deploy.success",
        severity="info",
        title=f"Deploy Succeeded: {version}",
        message=f"Version {version} deployed to {environment}",
        data={"version": version, "environment": environment},
        source="deployment",
    )
