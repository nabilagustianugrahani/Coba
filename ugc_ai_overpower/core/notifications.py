"""Multi-channel notification dispatcher.

Channels: Slack (Block Kit), Discord (embeds), Email (SMTP+HTML),
          Webhook (HMAC-SHA256), Console (colorized terminal).

All channels use stdlib only — no external dependencies.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import json
import logging
import os
import smtplib
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from threading import Lock
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

# ── Severity → color palette ───────────────────────────────────────
SEVERITY_COLORS: dict[str, str] = {
    "info": "#3B82F6",
    "warning": "#F59E0B",
    "error": "#E11D48",
    "critical": "#7C2D12",
}

SEVERITY_EMOJI: dict[str, str] = {
    "info": "\u2139\ufe0f",
    "warning": "\u26a0\ufe0f",
    "error": "\u274c",
    "critical": "\ud83d\udea8",
}


@dataclass
class NotificationEvent:
    """A single notification event dispatched through the pipeline."""
    event_type: str
    severity: str
    title: str
    message: str
    data: dict = field(default_factory=dict)
    source: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class NotificationChannel(ABC):
    """Abstract base for a notification output channel."""

    @abstractmethod
    def send(self, event: NotificationEvent) -> bool:
        """Deliver *event*. Return True on success, False on failure."""

    @property
    def channel_type(self) -> str:
        return self.__class__.__name__.replace("Channel", "").lower()


# ── Slack (Block Kit via webhook) ──────────────────────────────────

class SlackChannel(NotificationChannel):
    """Send rich Slack messages using Block Kit via incoming webhook."""

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")

    def send(self, event: NotificationEvent) -> bool:
        if not self.webhook_url:
            log.warning("SlackChannel: no webhook_url configured")
            return False
        blocks = self._build_blocks(event)
        payload = {"text": event.title, "blocks": blocks}
        return self._post(payload)

    def _build_blocks(self, event: NotificationEvent) -> list[dict]:
        color = SEVERITY_COLORS.get(event.severity, "#6B7280")
        emoji = SEVERITY_EMOJI.get(event.severity, "")
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {event.title}", "emoji": True},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": event.message},
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*Source:* {event.source}  |  *Type:* `{event.event_type}`  |  *Severity:* {color} {event.severity}"},
                ],
            },
        ]
        if event.data:
            fields = []
            for k, v in list(event.data.items())[:6]:
                fields.append({"type": "mrkdwn", "text": f"*{k}:* {v}"})
            if fields:
                blocks.append({"type": "section", "fields": fields})
        blocks.append({"type": "divider"})
        return blocks

    def _post(self, payload: dict) -> bool:
        try:
            data = json.dumps(payload).encode()
            req = Request(
                self.webhook_url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except URLError as e:
            log.error("SlackChannel POST failed: %s", e)
            return False


# ── Discord (embeds via webhook) ───────────────────────────────────

class DiscordChannel(NotificationChannel):
    """Send Discord messages with color-coded embeds via webhook."""

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL", "")

    def send(self, event: NotificationEvent) -> bool:
        if not self.webhook_url:
            log.warning("DiscordChannel: no webhook_url configured")
            return False
        color_hex = SEVERITY_COLORS.get(event.severity, "#6B7280").lstrip("#")
        color_int = int(color_hex, 16)
        embed = {
            "title": event.title,
            "description": event.message,
            "color": color_int,
            "footer": {"text": f"{event.source} | {event.event_type}"},
            "timestamp": event.timestamp or datetime.now(timezone.utc).isoformat(),
        }
        if event.data:
            fields = []
            for k, v in list(event.data.items())[:8]:
                fields.append({"name": k, "value": str(v), "inline": True})
            if fields:
                embed["fields"] = fields
        payload = {
            "content": SEVERITY_EMOJI.get(event.severity, ""),
            "embeds": [embed],
            "allowed_mentions": {"parse": []},
        }
        return self._post(payload)

    def _post(self, payload: dict) -> bool:
        try:
            data = json.dumps(payload).encode()
            req = Request(
                self.webhook_url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except URLError as e:
            log.error("DiscordChannel POST failed: %s", e)
            return False


# ── Email (SMTP + HTML) ────────────────────────────────────────────

class EmailChannel(NotificationChannel):
    """Send HTML-formatted notification emails via SMTP."""

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int = 587,
        from_addr: str | None = None,
        to_addrs: list[str] | None = None,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host or os.environ.get("SMTP_HOST", "localhost")
        self.smtp_port = smtp_port
        self.from_addr = from_addr or os.environ.get("SMTP_FROM", "notifications@ugc.local")
        self.to_addrs = to_addrs or os.environ.get("SMTP_TO", "").split(",")
        self.username = username or os.environ.get("SMTP_USERNAME", "")
        self.password = password or os.environ.get("SMTP_PASSWORD", "")
        self.use_tls = use_tls
        # Strip empties
        self.to_addrs = [a.strip() for a in self.to_addrs if a.strip()]

    def send(self, event: NotificationEvent) -> bool:
        if not self.to_addrs:
            log.warning("EmailChannel: no recipients configured")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{event.severity.upper()}] {event.title}"
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)

            text = f"{event.message}\n\nSource: {event.source}\nType: {event.event_type}"
            html_body = self._build_html(event)

            msg.attach(MIMEText(text, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            return True
        except Exception as e:
            log.error("EmailChannel send failed: %s", e)
            return False

    def _build_html(self, event: NotificationEvent) -> str:
        color = SEVERITY_COLORS.get(event.severity, "#6B7280")
        data_rows = ""
        for k, v in event.data.items():
            data_rows += f"<tr><td style='padding:4px 8px;font-weight:600'>{html.escape(str(k))}</td><td style='padding:4px 8px'>{html.escape(str(v))}</td></tr>"
        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;margin:0;padding:0;background:#f4f4f5">
<div style="max-width:600px;margin:24px auto;background:#fff;border-radius:8px;overflow:hidden;border:1px solid #e4e4e7">
<div style="padding:16px 24px;background:{color};color:#fff">
<h2 style="margin:0">{SEVERITY_EMOJI.get(event.severity, "")} {html.escape(event.title)}</h2>
</div>
<div style="padding:24px">
<p style="margin:0 0 16px;color:#3f3f46;line-height:1.6">{html.escape(event.message)}</p>
<table style="width:100%;border-collapse:collapse;margin-bottom:16px">
<tr><td style="padding:4px 8px;font-weight:600;color:#71717a">Source</td><td style="padding:4px 8px">{html.escape(event.source)}</td></tr>
<tr><td style="padding:4px 8px;font-weight:600;color:#71717a">Type</td><td style="padding:4px 8px">{html.escape(event.event_type)}</td></tr>
<tr><td style="padding:4px 8px;font-weight:600;color:#71717a">Severity</td><td style="padding:4px 8px"><span style="display:inline-block;padding:2px 8px;border-radius:4px;background:{color};color:#fff;font-size:12px">{event.severity}</span></td></tr>
</table>
{('<h3 style="color:#3f3f46;margin:16px 0 8px">Event Data</h3><table style="width:100%;border-collapse:collapse;border:1px solid #e4e4e7">'+data_rows+'</table>') if event.data else ''}
</div>
<div style="padding:8px 24px;background:#f4f4f5;font-size:12px;color:#a1a1aa;text-align:center">{event.timestamp}</div>
</div>
</body>
</html>"""


# ── Webhook (HMAC-SHA256 signed) ───────────────────────────────────

class WebhookChannel(NotificationChannel):
    """Send signed JSON payloads to an arbitrary HTTP endpoint."""

    def __init__(self, url: str | None = None, secret: str | None = None) -> None:
        self.url = url or os.environ.get("NOTIFICATION_WEBHOOK_URL", "")
        self.secret = secret or os.environ.get("NOTIFICATION_WEBHOOK_SECRET", "")

    def send(self, event: NotificationEvent) -> bool:
        if not self.url:
            log.warning("WebhookChannel: no url configured")
            return False
        payload = {
            "event_type": event.event_type,
            "severity": event.severity,
            "title": event.title,
            "message": event.message,
            "data": event.data,
            "source": event.source,
            "timestamp": event.timestamp,
        }
        body = json.dumps(payload).encode()
        signature = self._sign(body) if self.secret else "unsigned"
        try:
            req = Request(
                self.url, data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Notification-Signature": signature,
                    "X-Notification-Event": event.event_type,
                },
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except URLError as e:
            log.error("WebhookChannel POST failed: %s", e)
            return False

    def _sign(self, body: bytes) -> str:
        return hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()


# ── Console (colorized terminal) ───────────────────────────────────

class ConsoleChannel(NotificationChannel):
    """Pretty-print notifications to terminal with ANSI colors."""

    ANSI_RESET = "\033[0m"
    ANSI_COLORS: dict[str, str] = {
        "info": "\033[94m",
        "warning": "\033[93m",
        "error": "\033[91m",
        "critical": "\033[41m\033[97m",
    }

    def send(self, event: NotificationEvent) -> bool:
        color = self.ANSI_COLORS.get(event.severity, self.ANSI_RESET)
        emoji = SEVERITY_EMOJI.get(event.severity, "")
        line = "=" * 60
        print(f"{color}{line}")
        print(f"{emoji} {event.title}{self.ANSI_RESET}")
        print(f"  {event.message}")
        print(f"  {color}source={event.source}  type={event.event_type}  severity={event.severity}{self.ANSI_RESET}")
        if event.data:
            for k, v in event.data.items():
                print(f"  {k}={v}")
        print(f"{color}{line}{self.ANSI_RESET}")
        return True


# ── Dispatcher ─────────────────────────────────────────────────────

class NotificationDispatcher:
    """Routes events through registered channels with rate limiting
    and local pub/sub."""

    def __init__(self, channels: list[NotificationChannel] | None = None) -> None:
        self._channels: list[NotificationChannel] = channels or []
        self._history: deque[NotificationEvent] = deque(maxlen=1000)
        self._subscribers: dict[str, list[Callable[[NotificationEvent], None]]] = defaultdict(list)
        # rate-limit state: event_type -> deque of timestamps
        self._rate_windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=10_000))
        self._lock = Lock()

    # ── channel management ──────────────────────────────────────────

    def add_channel(self, channel: NotificationChannel) -> None:
        self._channels.append(channel)

    def remove_channel(self, channel_type: str) -> None:
        self._channels = [c for c in self._channels if c.channel_type != channel_type]

    # ── dispatch ────────────────────────────────────────────────────

    def dispatch(self, event: NotificationEvent) -> dict[str, bool]:
        """Send *event* to every registered channel. Returns per-channel results."""
        if not event.timestamp:
            event.timestamp = datetime.now(timezone.utc).isoformat()
        self._history.append(event)
        results: dict[str, bool] = {}
        for channel in self._channels:
            try:
                results[channel.channel_type] = channel.send(event)
            except Exception as e:
                log.error("dispatch %s via %s failed: %s", event.event_type, channel.channel_type, e)
                results[channel.channel_type] = False
        # local subscribers
        for cb in self._subscribers.get(event.event_type, []):
            try:
                cb(event)
            except Exception as e:
                log.error("subscriber for %s failed: %s", event.event_type, e)
        for cb in self._subscribers.get("*", []):
            try:
                cb(event)
            except Exception as e:
                log.error("wildcard subscriber failed: %s", e)
        return results

    def dispatch_async(self, event: NotificationEvent) -> None:
        """Fire-and-forget via a daemon thread."""
        import threading
        t = threading.Thread(target=self.dispatch, args=(event,), daemon=True)
        t.start()

    # ── subscribe ───────────────────────────────────────────────────

    def subscribe(self, event_type: str, callback: Callable[[NotificationEvent], None]) -> None:
        """Register a local handler for *event_type*. Use '*' for all events."""
        self._subscribers[event_type].append(callback)

    # ── history ─────────────────────────────────────────────────────

    def get_history(self, limit: int = 100) -> list[NotificationEvent]:
        return list(self._history)[-limit:]

    # ── rate limiting ───────────────────────────────────────────────

    def rate_limit(self, event_type: str, max_per_hour: int = 10) -> bool:
        """Return True if *event_type* is under its rate limit (should be sent)."""
        now = time.time()
        window = 3600  # 1 hour in seconds
        with self._lock:
            ts_deque = self._rate_windows[event_type]
            # Purge old entries
            while ts_deque and ts_deque[0] < now - window:
                ts_deque.popleft()
            if len(ts_deque) >= max_per_hour:
                return False
            ts_deque.append(now)
            return True
