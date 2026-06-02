import os, json, logging
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger("skynet.alerts")

class AlertManager:
    def __init__(self):
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat = os.getenv("TELEGRAM_CHAT_ID", "")
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK", "")
        self.enabled = bool(self.telegram_token or self.discord_webhook)

    def send_telegram(self, message):
        if not self.telegram_token or not self.telegram_chat:
            return False
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = json.dumps({"chat_id": self.telegram_chat, "text": message, "parse_mode": "Markdown"}).encode()
            req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning("Telegram alert failed: %s", e)
            return False

    def send_discord(self, message):
        if not self.discord_webhook:
            return False
        try:
            data = json.dumps({"content": message}).encode()
            req = Request(self.discord_webhook, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=10) as resp:
                return resp.status == 204
        except Exception as e:
            logger.warning("Discord alert failed: %s", e)
            return False

    def alert(self, message, channels=None):
        if channels is None:
            channels = ["telegram", "discord"]
        results = {}
        if "telegram" in channels:
            results["telegram"] = self.send_telegram(message)
        if "discord" in channels:
            results["discord"] = self.send_discord(message)
        return results

    def on_campaign_complete(self, product, total_content):
        msg = f"✅ *Campaign Complete*\\nProduct: {product}\\nContent: {total_content} pieces"
        return self.alert(msg)

    def on_campaign_failed(self, product, error):
        msg = f"❌ *Campaign Failed*\\nProduct: {product}\\nError: {error}"
        return self.alert(msg)

_alert_instance = None
def get_alert_manager():
    global _alert_instance
    if _alert_instance is None:
        _alert_instance = AlertManager()
    return _alert_instance
