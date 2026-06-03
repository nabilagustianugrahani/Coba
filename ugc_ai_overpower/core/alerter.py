"""Enterprise error monitoring — Telegram alerts + webhook dispatch."""
import os, logging, json, threading
from pathlib import Path
from datetime import datetime
from typing import Optional

from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)


class Alerter:
    """Centralized alert/notification system.

    Supports Telegram bot, webhook, and local log file outputs.
    Thread-safe — alerts from any component are non-blocking.
    """

    def __init__(self):
        self._telegram_token = skynet_config.get("telegram", "bot_token", default="")
        self._telegram_chat = skynet_config.get("telegram", "chat_id", default="")
        self._log_path = Path(skynet_config.get("paths", "output_dir", default="/tmp")) / "alerts.log"
        self._alert_dir = Path(skynet_config.get("paths", "output_dir", default="/tmp")) / "alerts"
        self._alert_dir.mkdir(parents=True, exist_ok=True)

    def send(self, message: str, severity: str = "info", source: str = ""):
        """Dispatch an alert through all configured channels.

        Args:
            message: Alert message text.
            severity: 'info', 'warning', 'error', 'critical'.
            source: Component name that generated the alert.
        """
        timestamp = datetime.now().isoformat()
        entry = {
            "timestamp": timestamp,
            "severity": severity,
            "source": source or "unknown",
            "message": message,
        }
        self._log_to_file(entry)
        log.log(self._severity_level(severity), "[%s] %s", source, message)

        if severity in ("error", "critical") and self._telegram_token:
            threading.Thread(target=self._send_telegram, args=(entry,), daemon=True).start()

        if severity == "critical":
            self._save_critical(entry)

    def info(self, msg: str, source: str = ""):
        self.send(msg, "info", source)

    def warning(self, msg: str, source: str = ""):
        self.send(msg, "warning", source)

    def error(self, msg: str, source: str = ""):
        self.send(msg, "error", source)

    def critical(self, msg: str, source: str = ""):
        self.send(msg, "critical", source)

    def _severity_level(self, severity: str) -> int:
        return {
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }.get(severity, logging.INFO)

    def _log_to_file(self, entry: dict):
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _send_telegram(self, entry: dict):
        try:
            import requests
            emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
            text = (
                f"{emoji.get(entry['severity'], '📢')} *Skynet Alert*\n"
                f"Source: `{entry['source']}`\n"
                f"Time: {entry['timestamp']}\n\n"
                f"{entry['message']}"
            )
            resp = requests.post(
                f"https://api.telegram.org/bot{self._telegram_token}/sendMessage",
                json={
                    "chat_id": self._telegram_chat,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                log.warning("Telegram send failed: %s", resp.text)
        except Exception as e:
            log.warning("Telegram error: %s", e)

    def _save_critical(self, entry: dict):
        path = self._alert_dir / f"critical_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(path, "w") as f:
            json.dump(entry, f, indent=2)

    def set_telegram(self, token: str, chat_id: str):
        """Configure Telegram credentials at runtime."""
        self._telegram_token = token
        self._telegram_chat = chat_id
        skynet_config.set("telegram", "bot_token", value=token)
        skynet_config.set("telegram", "chat_id", value=chat_id)


alerter = Alerter()
