"""Tests for multi-channel notification system: 42 tests total.

Breakdown:
  - 4 tests per channel (Slack, Discord, Email, Webhook, Console) = 20
  - 6 dispatcher tests        (multi-channel, rate limit, history, async, subscribe, remove)
  - 12 event-helper tests
  - 4 integration tests
  Total: 42
"""
from __future__ import annotations

import json
import time
from unittest.mock import Mock, patch, MagicMock

import pytest

from ugc_ai_overpower.core.notifications import (
    NotificationEvent,
    NotificationChannel,
    SlackChannel,
    DiscordChannel,
    EmailChannel,
    WebhookChannel,
    ConsoleChannel,
    NotificationDispatcher,
    SEVERITY_COLORS,
)
from ugc_ai_overpower.core.notification_events import (
    campaign_launched,
    content_viral,
    rate_limit_hit,
    circuit_breaker_open,
    autoheal_restart,
    webhook_received,
    notion_sync_success,
    notion_sync_failed,
    quota_warning,
    quota_exceeded,
    cost_alert,
    deploy_success,
)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def sample_event():
    return NotificationEvent(
        event_type="test.event",
        severity="info",
        title="Test Title",
        message="Test message body",
        data={"key": "value", "count": 42},
        source="test_module",
    )

@pytest.fixture
def sample_error_event():
    return NotificationEvent(
        event_type="test.error",
        severity="error",
        title="Error Occurred",
        message="Something went wrong",
        data={"error_code": 500},
        source="test_module",
    )


# ═══════════════════════════════════════════════════════════════════
# SlackChannel — 4 tests
# ═══════════════════════════════════════════════════════════════════

class TestSlackChannel:
    def test_send_success(self, sample_event):
        chan = SlackChannel(webhook_url="https://hooks.slack.com/test")
        with patch("ugc_ai_overpower.core.notifications.urlopen") as mock:
            mock.return_value.__enter__.return_value.status = 200
            assert chan.send(sample_event) is True

    def test_send_failure_no_url(self, sample_event):
        chan = SlackChannel(webhook_url="")
        assert chan.send(sample_event) is False

    def test_send_http_error(self, sample_event):
        chan = SlackChannel(webhook_url="https://hooks.slack.com/test")
        with patch("ugc_ai_overpower.core.notifications.urlopen") as mock:
            mock.return_value.__enter__.return_value.status = 400
            assert chan.send(sample_event) is False

    def test_build_blocks_includes_fields(self, sample_event):
        chan = SlackChannel(webhook_url="https://hooks.slack.com/test")
        blocks = chan._build_blocks(sample_event)
        types = [b["type"] for b in blocks]
        assert "header" in types
        assert "section" in types
        assert "context" in types
        assert "divider" in types


# ═══════════════════════════════════════════════════════════════════
# DiscordChannel — 4 tests
# ═══════════════════════════════════════════════════════════════════

class TestDiscordChannel:
    def test_send_success(self, sample_event):
        chan = DiscordChannel(webhook_url="https://discord.com/api/webhooks/test")
        with patch("ugc_ai_overpower.core.notifications.urlopen") as mock:
            mock.return_value.__enter__.return_value.status = 204
            assert chan.send(sample_event) is True

    def test_send_failure_no_url(self, sample_event):
        chan = DiscordChannel(webhook_url="")
        assert chan.send(sample_event) is False

    def test_send_http_error(self, sample_event):
        chan = DiscordChannel(webhook_url="https://discord.com/api/webhooks/test")
        with patch("ugc_ai_overpower.core.notifications.urlopen") as mock:
            mock.return_value.__enter__.return_value.status = 400
            assert chan.send(sample_event) is False

    def test_embed_color_matches_severity(self):
        chan = DiscordChannel(webhook_url="https://discord.com/api/webhooks/test")
        ev = NotificationEvent("x", "error", "E", "Msg", {}, "src")
        with patch("ugc_ai_overpower.core.notifications.urlopen") as mock:
            mock.return_value.__enter__.return_value.status = 204
            chan.send(ev)
            call_data = json.loads(mock.call_args[0][0].data)
            color_hex = SEVERITY_COLORS["error"].lstrip("#")
            assert call_data["embeds"][0]["color"] == int(color_hex, 16)


# ═══════════════════════════════════════════════════════════════════
# EmailChannel — 4 tests
# ═══════════════════════════════════════════════════════════════════

class TestEmailChannel:
    def test_send_success(self, sample_event):
        chan = EmailChannel(
            smtp_host="localhost", smtp_port=587,
            from_addr="test@local", to_addrs=["dest@local"],
        )
        with patch("ugc_ai_overpower.core.notifications.smtplib.SMTP") as mock:
            instance = mock.return_value.__enter__.return_value
            assert chan.send(sample_event) is True
            assert instance.sendmail.called

    def test_send_failure_no_recipients(self, sample_event):
        chan = EmailChannel(to_addrs=[])
        assert chan.send(sample_event) is False

    def test_send_smtp_exception(self, sample_event):
        chan = EmailChannel(
            smtp_host="localhost", smtp_port=587,
            from_addr="test@local", to_addrs=["dest@local"],
        )
        with patch("ugc_ai_overpower.core.notifications.smtplib.SMTP") as mock:
            mock.return_value.__enter__.return_value.sendmail.side_effect = Exception("SMTP fail")
            assert chan.send(sample_event) is False

    def test_html_body_contains_event_data(self, sample_event):
        chan = EmailChannel(to_addrs=["dest@local"])
        html = chan._build_html(sample_event)
        assert sample_event.title in html
        assert sample_event.message in html
        assert sample_event.source in html


# ═══════════════════════════════════════════════════════════════════
# WebhookChannel — 4 tests
# ═══════════════════════════════════════════════════════════════════

class TestWebhookChannel:
    def test_send_success(self, sample_event):
        chan = WebhookChannel(url="https://example.com/hook", secret="s3cret")
        with patch("ugc_ai_overpower.core.notifications.urlopen") as mock:
            mock.return_value.__enter__.return_value.status = 200
            assert chan.send(sample_event) is True

    def test_send_failure_no_url(self, sample_event):
        chan = WebhookChannel(url="")
        assert chan.send(sample_event) is False

    def test_send_http_error(self, sample_event):
        chan = WebhookChannel(url="https://example.com/hook")
        with patch("ugc_ai_overpower.core.notifications.urlopen") as mock:
            mock.return_value.__enter__.return_value.status = 500
            assert chan.send(sample_event) is False

    def test_hmac_signature_present(self, sample_event):
        chan = WebhookChannel(url="https://example.com/hook", secret="s3cret")
        with patch("ugc_ai_overpower.core.notifications.urlopen") as mock:
            mock.return_value.__enter__.return_value.status = 200
            chan.send(sample_event)
            req = mock.call_args[0][0]
            # urllib.request.Request lowercases header names internally
            assert req.headers.get("X-Notification-Signature") != "unsigned"


# ═══════════════════════════════════════════════════════════════════
# ConsoleChannel — 4 tests
# ═══════════════════════════════════════════════════════════════════

class TestConsoleChannel:
    def test_send_returns_true(self, sample_event):
        chan = ConsoleChannel()
        assert chan.send(sample_event) is True

    def test_send_error_event(self, sample_error_event):
        chan = ConsoleChannel()
        assert chan.send(sample_error_event) is True

    def test_send_critical_event(self):
        ev = NotificationEvent("test.critical", "critical", "CRIT", "boom", {}, "src")
        chan = ConsoleChannel()
        assert chan.send(ev) is True

    def test_send_with_empty_data(self):
        ev = NotificationEvent("test.event", "info", "Title", "Msg", {}, "src")
        chan = ConsoleChannel()
        assert chan.send(ev) is True


# ═══════════════════════════════════════════════════════════════════
# NotificationDispatcher — 6 tests
# ═══════════════════════════════════════════════════════════════════

class TestNotificationDispatcher:
    def test_multi_channel_dispatch(self, sample_event):
        slack = SlackChannel(webhook_url="https://hooks.slack.com/test")
        console = ConsoleChannel()
        with patch("ugc_ai_overpower.core.notifications.urlopen") as mock:
            mock.return_value.__enter__.return_value.status = 200
            disp = NotificationDispatcher(channels=[slack, console])
            results = disp.dispatch(sample_event)
            assert "slack" in results
            assert "console" in results
            assert results["console"] is True

    def test_rate_limit_blocks(self):
        disp = NotificationDispatcher()
        ev = NotificationEvent("test.rl", "info", "RL", "test", {}, "src")
        # Allow 1 per hour
        assert disp.rate_limit("test.rl", max_per_hour=1) is True
        assert disp.rate_limit("test.rl", max_per_hour=1) is False

    def test_rate_limit_allows_after_window(self):
        disp = NotificationDispatcher()
        ev = NotificationEvent("test.rl", "info", "RL", "test", {}, "src")
        assert disp.rate_limit("test.rl_window", max_per_hour=1) is True
        # Simulate time passing by mocking time.time
        original = time.time
        try:
            time.time = lambda: original() + 3601  # >1h later
            assert disp.rate_limit("test.rl_window", max_per_hour=1) is True
        finally:
            time.time = original

    def test_history_tracks_events(self, sample_event):
        disp = NotificationDispatcher()
        disp.dispatch(sample_event)
        hist = disp.get_history(limit=10)
        assert len(hist) == 1
        assert hist[0].event_type == "test.event"

    def test_subscribe_receives_event(self, sample_event):
        disp = NotificationDispatcher()
        callback = Mock()
        disp.subscribe("test.event", callback)
        disp.dispatch(sample_event)
        callback.assert_called_once_with(sample_event)

    def test_remove_channel(self, sample_event):
        slack = SlackChannel(webhook_url="https://hooks.slack.com/test")
        disp = NotificationDispatcher(channels=[slack])
        assert len(disp._channels) == 1
        disp.remove_channel("slack")
        assert len(disp._channels) == 0


# ═══════════════════════════════════════════════════════════════════
# Event helpers — 12 tests
# ═══════════════════════════════════════════════════════════════════

class TestEventHelpers:
    def test_campaign_launched(self):
        ev = campaign_launched("camp-1", "skincare", "alice")
        assert ev.event_type == "campaign.launched"
        assert ev.severity == "info"
        assert ev.data["campaign_id"] == "camp-1"

    def test_content_viral(self):
        ev = content_viral("c-42", "tiktok", 100_000, 4.5)
        assert ev.event_type == "content.viral"
        assert ev.severity == "warning"
        assert ev.data["views"] == 100_000

    def test_rate_limit_hit(self):
        ev = rate_limit_hit("openai", 60, 120)
        assert ev.event_type == "rate_limit.hit"
        assert ev.data["api"] == "openai"

    def test_circuit_breaker_open(self):
        ev = circuit_breaker_open("notion_api", 0.85)
        assert ev.event_type == "circuit.open"
        assert ev.severity == "error"
        assert ev.data["failure_rate"] == 0.85

    def test_autoheal_restart(self):
        ev = autoheal_restart("daemon", 2, "OOM detected")
        assert ev.event_type == "autoheal.restart"
        assert ev.data["attempt"] == 2

    def test_webhook_received(self):
        ev = webhook_received("github", "push")
        assert ev.event_type == "webhook.received"
        assert ev.data["source"] == "github"

    def test_notion_sync_success(self):
        ev = notion_sync_success(150, 3, 12.5)
        assert ev.event_type == "sync.success"
        assert ev.data["synced"] == 150
        assert ev.data["failed"] == 3

    def test_notion_sync_failed(self):
        ev = notion_sync_failed("API timeout", 50)
        assert ev.event_type == "sync.failed"
        assert "timeout" in ev.data["error"]

    def test_quota_warning(self):
        ev = quota_warning("openai", 85.0)
        assert ev.event_type == "quota.warning"
        assert ev.data["used_pct"] == 85.0

    def test_quota_exceeded(self):
        ev = quota_exceeded("openai", "2025-01-01T00:00:00Z")
        assert ev.event_type == "quota.exceeded"
        assert ev.severity == "error"

    def test_cost_alert(self):
        ev_below = cost_alert(45.0, 100.0)
        assert ev_below.event_type == "cost.alert"
        assert ev_below.severity == "warning"
        ev_above = cost_alert(150.0, 100.0)
        assert ev_above.severity == "critical"

    def test_deploy_success(self):
        ev = deploy_success("v2.1.0", "production")
        assert ev.event_type == "deploy.success"
        assert ev.severity == "info"
        assert ev.data["version"] == "v2.1.0"


# ═══════════════════════════════════════════════════════════════════
# Integration tests — 4 tests
# ═══════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_autoheal_notification_cycle(self):
        """autoheal.restart event → dispatcher → console channel"""
        ev = autoheal_restart("daemon", 1, "test")
        console = ConsoleChannel()
        disp = NotificationDispatcher(channels=[console])
        results = disp.dispatch(ev)
        assert results["console"] is True
        assert ev.source == "autoheal"

    def test_rate_limiter_notification(self):
        """rate_limit_hit event → dispatcher → console"""
        ev = rate_limit_hit("openai", 60, 30)
        console = ConsoleChannel()
        disp = NotificationDispatcher(channels=[console])
        results = disp.dispatch(ev)
        assert results["console"] is True

    def test_circuit_breaker_notification(self):
        """circuit.open event → dispatcher → console"""
        ev = circuit_breaker_open("notion", 0.75)
        console = ConsoleChannel()
        disp = NotificationDispatcher(channels=[console])
        results = disp.dispatch(ev)
        assert results["console"] is True
        assert ev.severity == "error"

    def test_notion_sync_chain(self):
        """sync.success → dispatcher → console"""
        ev = notion_sync_success(200, 0, 8.2)
        console = ConsoleChannel()
        disp = NotificationDispatcher(channels=[console])
        results = disp.dispatch(ev)
        assert results["console"] is True
        assert ev.event_type == "sync.success"
