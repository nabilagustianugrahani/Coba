"""Centralized configuration for Skynet enterprise platform."""
import os, json, logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "config.json"


class SkynetConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._loaded = True
        self._data = self._defaults()
        self._load()

    @staticmethod
    def _defaults() -> dict:
        return {
            "router": {
                "base_url": os.getenv("ROUTER_URL", "http://localhost:20128"),
                "api_key": os.getenv("ROUTER_KEY", ""),
                "model": os.getenv("ROUTER_MODEL", "gemini-2.5-flash"),
                "vision_model": os.getenv("ROUTER_VISION_MODEL", "gemini-2.5-flash"),
            },
            "browser": {
                "headless": True,
                "viewport_width": 1280,
                "viewport_height": 720,
                "timeout": 30000,
                "slow_mo": 50,
            },
            "browser_use": {
                "model": "gemini-2.5-flash",
                "max_actions_per_step": 10,
                "use_vision": True,
            },
            "tts": {
                "engine": "edge-tts",
                "voice_id": "id-ID-ArdiNeural",
                "voice_id_female": "id-ID-GadisNeural",
            },
            "farm": {
                "temp_mail_api": "https://api.smailpro.com",
                "temp_mail_key": os.getenv("TEMP_MAIL_KEY", ""),
                "daily_limit_per_account": {"tiktok": 10, "instagram": 15, "youtube": 20},
            },
            "telegram": {
                "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
                "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
            },
            "paths": {
                "farm_dir": str(Path(__file__).resolve().parents[1] / "data" / "farm"),
                "output_dir": str(Path(__file__).resolve().parents[1] / "output"),
                "assets_dir": str(Path(__file__).resolve().parents[1] / "assets"),
            },
            "platforms": {
                "tiktok": {"upload_url": "https://www.tiktok.com/upload", "login_url": "https://www.tiktok.com/login"},
                "instagram": {"create_url": "https://www.instagram.com/create", "login_url": "https://www.instagram.com/accounts/login/"},
                "youtube": {"upload_url": "https://studio.youtube.com/upload", "login_url": "https://accounts.google.com/ServiceLogin"},
            },
        }

    def _load(self):
        if _CONFIG_PATH.exists():
            try:
                with open(_CONFIG_PATH) as f:
                    user = json.load(f)
                self._deep_merge(self._data, user)
                log.info("Config loaded from %s", _CONFIG_PATH)
            except Exception as e:
                log.warning("Failed to load config: %s", e)

    def save(self):
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_PATH, "w") as f:
            json.dump(self._data, f, indent=2)
        log.info("Config saved to %s", _CONFIG_PATH)

    def get(self, *keys: str, default=None):
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
            if val is None:
                return default
        return val

    def set(self, *args, value):
        if len(args) < 1:
            return
        val = self._data
        for k in args[:-1]:
            val = val.setdefault(k, {})
        val[args[-1]] = value
        self.save()

    @staticmethod
    def _deep_merge(base, override):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                SkynetConfig._deep_merge(base[k], v)
            else:
                base[k] = v


skynet_config = SkynetConfig()
