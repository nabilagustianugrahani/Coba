import os
import re
import json
import random
import logging
from typing import Optional

log = logging.getLogger(__name__)

AFFILIATE_TEMPLATES = {
    "shopee": {
        "base": "https://shopee.co.id/{product_slug}",
        "tag": "?af_device=web&af_id={af_id}",
    },
    "tokopedia": {
        "base": "https://tokopedia.link/{product_slug}",
        "tag": "?af_id={af_id}",
    },
    "lazada": {
        "base": "https://www.lazada.co.id/products/{product_slug}",
        "tag": "?spm=a2o4j.{af_id}.{track_id}",
    },
    "tiktok": {
        "base": "https://vt.tokopedia.com/{product_slug}",
        "tag": "?af_id={af_id}",
    },
    "sociolla": {
        "base": "https://sociolla.com/product/{product_slug}",
        "tag": "?af_id={af_id}",
    },
    "blibli": {
        "base": "https://www.blibli.com/p/{product_slug}",
        "tag": "?af_id={af_id}",
    },
}


class AffiliateManager:
    def __init__(self, config_path: str = ""):
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "affiliate_config.json"
        )
        self._config = self._load_config()

    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            with open(self.config_path) as f:
                return json.load(f)
        return {
            "shopee": {"af_id": "", "track_id": ""},
            "tokopedia": {"af_id": "", "track_id": ""},
            "lazada": {"af_id": "", "track_id": ""},
            "sociolla": {"af_id": "", "track_id": ""},
            "blibli": {"af_id": "", "track_id": ""},
        }

    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self._config, f, indent=2)
        log.info("Affiliate config saved to %s", self.config_path)

    def set_affiliate_id(self, platform: str, af_id: str, track_id: str = ""):
        if platform not in AFFILIATE_TEMPLATES:
            log.warning("Unknown platform: %s", platform)
            return False
        self._config.setdefault(platform, {})
        self._config[platform]["af_id"] = af_id
        if track_id:
            self._config[platform]["track_id"] = track_id
        self.save_config()
        return True

    def generate_link(self, platform: str, product_name: str, product_id: str = "") -> str:
        config = self._config.get(platform, {})
        template = AFFILIATE_TEMPLATES.get(platform)
        if not template:
            return f"https://{platform}.co.id/search?q={product_name.replace(' ', '+')}"

        slug = product_name.lower().replace(" ", "-").replace("--", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        product_slug = product_id or slug

        base_url = template["base"].format(product_slug=product_slug)
        if config.get("af_id"):
            tag = template["tag"].format(
                af_id=config["af_id"],
                track_id=config.get("track_id", ""),
            )
            base_url += tag
        return base_url

    def inject_into_script(self, script: str, platform: str, product_name: str, product_id: str = "") -> str:
        link = self.generate_link(platform, product_name, product_id)
        call_to_actions = [
            f"\n\n🔗 Link pembelian: {link}",
            f"\n\nKlik di sini: {link}",
            f"\n\nBeli sekarang: {link}",
            f"\n\n👉 {link}",
        ]

        # Inject affiliate link before hashtags if they exist
        if "#" in script:
            parts = script.rsplit("\n#", 1)
            cta = random.choice(call_to_actions)
            return parts[0] + cta + "\n\n#" + parts[1]
        else:
            return script + random.choice(call_to_actions)

    def get_all_configs(self) -> dict:
        return dict(self._config)

    def get_available_platforms(self) -> list:
        return list(AFFILIATE_TEMPLATES.keys())
