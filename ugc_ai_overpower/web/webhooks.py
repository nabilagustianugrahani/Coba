import os
import json
import time
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Optional, Callable
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger("skynet.webhooks")

class WebhookManager:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.hooks = []
        self.max_retries = self.config.get("retry_max", 3)
        self._load_subscribers()

    def _load_subscribers(self):
        path = os.getenv("WEBHOOKS_FILE", "data/webhooks.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.hooks = json.load(f)
            except Exception as e:
                logger.error("Failed to load webhooks: %s", e)

    def _save(self):
        path = os.getenv("WEBHOOKS_FILE", "data/webhooks.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.hooks, f, indent=2)

    def register(self, url: str, events: list[str], secret: str = "") -> dict:
        hook = {
            "id": hashlib.md5(f"{url}:{time.time()}".encode()).hexdigest()[:12],
            "url": url,
            "events": events,
            "secret": secret,
            "created_at": datetime.utcnow().isoformat(),
            "active": True,
        }
        self.hooks.append(hook)
        self._save()
        return hook

    def unregister(self, hook_id: str) -> bool:
        self.hooks = [h for h in self.hooks if h["id"] != hook_id]
        self._save()
        return True

    def dispatch(self, event: str, payload: dict):
        if not self.config.get("enabled", True):
            return
        for hook in self.hooks:
            if not hook.get("active", True):
                continue
            if event not in hook.get("events", []):
                continue
            self._send(hook, event, payload)

    def _send(self, hook: dict, event: str, payload: dict):
        body = json.dumps({
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
        }).encode()

        for attempt in range(self.max_retries):
            try:
                req = Request(
                    hook["url"],
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Skynet-Event": event,
                        "X-Skynet-Signature": self._sign(body, hook.get("secret", "")),
                        "X-Skynet-Delivery": hashlib.md5(body).hexdigest()[:16],
                        "User-Agent": "Skynet-Webhook/2.0",
                    },
                    method="POST",
                )
                with urlopen(req, timeout=10) as resp:
                    if 200 <= resp.status < 300:
                        logger.info("Webhook %s delivered to %s (attempt %d)", event, hook["url"], attempt + 1)
                        return
            except URLError as e:
                logger.warning("Webhook delivery failed (attempt %d/%d): %s", attempt + 1, self.max_retries, e)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        logger.error("Webhook %s failed after %d retries to %s", event, self.max_retries, hook["url"])

    @staticmethod
    def _sign(body: bytes, secret: str) -> str:
        if not secret:
            return "unsigned"
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

webhook_manager = WebhookManager()
