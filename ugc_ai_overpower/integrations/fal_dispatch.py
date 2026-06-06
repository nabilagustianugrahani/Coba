"""fal.ai integration dispatcher.

fal.ai is a serverless GPU platform with 985+ pre-deployed models
(image, video, audio, 3D). Specializes in:
  - Wan 2.1 (T2V/I2V/Pro) — best open source video
  - Hunyuan 1.5 — Tencent cinematic
  - LTX-2.3 — fast 4K
  - Kling 3.0 — premium motion
  - Veo 3.1 — Google, with audio
  - Flux, Seedream — image gen
  - 50% market share for image APIs, 44% for video

Pricing: OUTPUT-BASED (per image / per second of video), not per-GPU-second.
This is fundamentally different from Modal which charges per GPU-second.
fal.ai includes queue time + warm-pool management in the model price.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

log = logging.getLogger(__name__)


FAL_BASE_URL = "https://fal.run"
FAL_QUEUE_URL = "https://queue.fal.run"
DEFAULT_BUDGET_USD = 5.0


FAL_MODELS: dict[str, dict[str, Any]] = {
    "wan-t2v": {
        "endpoint": "fal-ai/wan-t2v",
        "type": "video",
        "tier": 1,
        "resolution_default": "720p",
        "resolution_options": ["480p", "580p", "720p"],
        "duration_options": [5, 10],
        "ultrarealistic": True,
        "open_source": True,
        "license": "apache-2.0",
        "price_per_call_480p": 0.20,
        "price_per_call_720p": 0.40,
        "notes": "Wan 2.1 T2V — best open source video gen, 1.3B+14B variants",
    },
    "wan-pro-t2v": {
        "endpoint": "fal-ai/wan-pro/text-to-video",
        "type": "video",
        "tier": 2,
        "resolution_default": "1080p",
        "duration_options": [5, 6],
        "ultrarealistic": True,
        "open_source": True,
        "license": "apache-2.0",
        "price_per_call": 0.80,
        "notes": "Wan 2.1 Pro — 1080p@30fps premium, $0.16/sec",
    },
    "wan-i2v": {
        "endpoint": "fal-ai/wan-i2v",
        "type": "video",
        "tier": 1,
        "resolution_default": "720p",
        "resolution_options": ["480p", "720p"],
        "price_per_call_480p": 0.20,
        "price_per_call_720p": 0.40,
        "notes": "Wan 2.1 I2V — image to video",
    },
    "ltx-2.3-t2v": {
        "endpoint": "fal-ai/ltx-2.3/text-to-video",
        "type": "video",
        "tier": 1,
        "resolution_default": "1080p",
        "resolution_options": ["1080p", "1440p", "2160p"],
        "price_per_sec_1080p": 0.06,
        "price_per_sec_1440p": 0.12,
        "price_per_sec_2160p": 0.24,
        "ultrarealistic": True,
        "open_source": True,
        "license": "open-source",
        "notes": "LTX 2.3 — fast 4K capable, Pro and Fast variants",
    },
    "ltx-2.3-fast-t2v": {
        "endpoint": "fal-ai/ltx-2.3/text-to-video/fast",
        "type": "video",
        "tier": 1,
        "resolution_default": "1080p",
        "price_per_sec_1080p": 0.04,
        "price_per_sec_1440p": 0.08,
        "price_per_sec_2160p": 0.16,
        "ultrarealistic": True,
        "open_source": True,
        "notes": "LTX 2.3 Fast — 33% cheaper, same quality",
    },
    "hunyuan-video-1.5-t2v": {
        "endpoint": "fal-ai/hunyuan-video-v1.5/text-to-video",
        "type": "video",
        "tier": 2,
        "price_per_sec": 0.075,
        "ultrarealistic": True,
        "open_source": True,
        "license": "apache-2.0",
        "notes": "Hunyuan 1.5 T2V — Tencent cinematic (3.75x cheaper on WaveSpeed)",
    },
    "kling-3.0-pro": {
        "endpoint": "fal-ai/kling-video/v3/pro/text-to-video",
        "type": "video",
        "tier": 3,
        "price_per_sec": 0.09,
        "ultrarealistic": True,
        "open_source": False,
        "license": "proprietary",
        "notes": "Kling 3.0 Pro — premium motion, lip-sync",
    },
    "veo-3.1-lite": {
        "endpoint": "fal-ai/veo3.1/lite/text-to-video",
        "type": "video",
        "tier": 3,
        "price_per_sec": 0.05,
        "ultrarealistic": True,
        "open_source": False,
        "license": "proprietary",
        "notes": "Google Veo 3.1 Lite — cheapest 720p with audio",
    },
    "veo-3.1": {
        "endpoint": "fal-ai/veo3.1/text-to-video",
        "type": "video",
        "tier": 3,
        "price_per_sec": 0.20,
        "ultrarealistic": True,
        "open_source": False,
        "notes": "Google Veo 3.1 — premium with audio, $0.20/sec",
    },
    "flux-schnell": {
        "endpoint": "fal-ai/flux/schnell",
        "type": "image",
        "tier": 1,
        "price_per_image": 0.003,
        "ultrarealistic": True,
        "open_source": True,
        "license": "apache-2.0",
        "notes": "FLUX.1 Schnell — 1 step, fastest",
    },
    "flux-dev": {
        "endpoint": "fal-ai/flux/dev",
        "type": "image",
        "tier": 1,
        "price_per_image": 0.025,
        "ultrarealistic": True,
        "open_source": False,
        "notes": "FLUX.1 Dev — quality/speed balance",
    },
    "flux-pro": {
        "endpoint": "fal-ai/flux-pro",
        "type": "image",
        "tier": 2,
        "price_per_image": 0.05,
        "ultrarealistic": True,
        "open_source": False,
        "notes": "FLUX.1 Pro — premium quality",
    },
    "seedream-4": {
        "endpoint": "fal-ai/seedream/v4/text-to-image",
        "type": "image",
        "tier": 1,
        "price_per_image": 0.03,
        "ultrarealistic": True,
        "open_source": False,
        "notes": "ByteDance Seedream 4 — fast 2K",
    },
    "kokoro-tts": {
        "endpoint": "fal-ai/kokoro",
        "type": "audio",
        "tier": 1,
        "price_per_request": 0.02,
        "open_source": True,
        "notes": "Kokoro TTS — fast multilingual speech",
    },
}


@dataclass
class FalResult:
    model: str
    modality: str
    request_id: str = ""
    media_url: str = ""
    media_bytes: Optional[bytes] = None
    cost_usd: float = 0.0
    duration_sec: float = 0.0
    tier: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d.get("media_bytes") is not None:
            d["media_bytes_b64"] = "<bytes omitted>"
            d["media_bytes"] = None
        return d


class FalBudgetExceeded(Exception):
    pass


class FalDispatcher:
    def __init__(
        self,
        api_key: Optional[str] = None,
        budget_usd: Optional[float] = None,
        spend_tracker: Optional[dict[str, float]] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("FAL_KEY", "")
        self.budget_usd = budget_usd if budget_usd is not None else float(
            os.environ.get("FAL_BUDGET_USD", DEFAULT_BUDGET_USD)
        )
        self.spend_tracker = spend_tracker if spend_tracker is not None else {"spent": 0.0}

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def list_models(self, tier: Optional[int] = None,
                    modality: Optional[str] = None) -> list[str]:
        out = []
        for name, cfg in FAL_MODELS.items():
            if tier is not None and cfg.get("tier") != tier:
                continue
            if modality is not None and cfg.get("type") != modality:
                continue
            out.append(name)
        return out

    def get_model(self, name: str) -> dict[str, Any]:
        if name not in FAL_MODELS:
            raise ValueError(f"Unknown fal model: {name}. Available: {list(FAL_MODELS)}")
        return FAL_MODELS[name]

    def estimate_cost(
        self,
        model: str,
        duration_sec: float = 5.0,
        resolution: str = "",
        n: int = 1,
    ) -> float:
        if model not in FAL_MODELS:
            raise ValueError(f"Unknown fal model: {model}")
        cfg = FAL_MODELS[model]
        if cfg["type"] == "video":
            if "price_per_sec" in cfg:
                cost = cfg["price_per_sec"] * duration_sec
            elif "price_per_call" in cfg:
                cost = cfg["price_per_call"] * (duration_sec / 5.0)
            elif resolution == "480p" and "price_per_call_480p" in cfg:
                cost = cfg["price_per_call_480p"] * (duration_sec / 5.0)
            elif resolution == "720p" and "price_per_call_720p" in cfg:
                cost = cfg["price_per_call_720p"] * (duration_sec / 5.0)
            else:
                res = resolution or cfg.get("resolution_default", "720p")
                key = f"price_per_sec_{res}"
                if key in cfg:
                    cost = cfg[key] * duration_sec
                else:
                    cost = 0.40 * (duration_sec / 5.0)
        elif cfg["type"] == "image":
            cost = cfg.get("price_per_image", 0.05) * n
        elif cfg["type"] == "audio":
            cost = cfg.get("price_per_request", 0.02) * n
        else:
            cost = 0.10 * n
        return round(cost, 6)

    def check_budget(self, estimated_cost: float) -> bool:
        return (self.spend_tracker["spent"] + estimated_cost) <= self.budget_usd

    def remaining_budget(self) -> float:
        return round(self.budget_usd - self.spend_tracker["spent"], 6)

    def _record_spend(self, cost: float) -> None:
        self.spend_tracker["spent"] = round(self.spend_tracker["spent"] + cost, 6)
        log.info("fal.spend: +$%.6f (total $%.6f / $%.2f)",
                 cost, self.spend_tracker["spent"], self.budget_usd)

    async def submit(
        self,
        model: str,
        prompt: str = "",
        image_url: str = "",
        duration_sec: float = 5.0,
        resolution: str = "",
        n: int = 1,
        **kwargs: Any,
    ) -> FalResult:
        if not self.is_configured():
            raise RuntimeError("fal.ai not configured. Set FAL_KEY env var.")
        if model not in FAL_MODELS:
            raise ValueError(f"Unknown model: {model}")
        cfg = FAL_MODELS[model]
        est_cost = self.estimate_cost(model, duration_sec=duration_sec, resolution=resolution, n=n)
        if not self.check_budget(est_cost):
            raise FalBudgetExceeded(
                f"fal budget exceeded: ${est_cost:.4f} needed, "
                f"${self.remaining_budget():.4f} remaining"
            )
        try:
            import aiohttp
        except ImportError as e:
            return FalResult(model=model, modality=cfg["type"], error="aiohttp not installed")
        endpoint = f"{FAL_BASE_URL}/{cfg['endpoint']}"
        payload: dict[str, Any] = {"prompt": prompt}
        if image_url:
            payload["image_url"] = image_url
        if cfg["type"] == "video":
            payload["num_frames"] = int(duration_sec * 16)
            payload["frames_per_second"] = 16
            payload["resolution"] = resolution or cfg.get("resolution_default", "720p")
        elif cfg["type"] == "image":
            payload["num_images"] = max(1, min(int(n), 4))
        payload.update(kwargs)
        start = time.time()
        try:
            async with aiohttp.ClientSession() as http:
                async with http.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Key {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as resp:
                    body = await resp.json()
                    if resp.status not in (200, 201):
                        return FalResult(
                            model=model, modality=cfg["type"],
                            error=f"fal HTTP {resp.status}: {body}",
                        )
                    media_url = ""
                    if cfg["type"] == "video":
                        media_url = (body.get("video") or {}).get("url", "") if isinstance(body.get("video"), dict) else body.get("video_url", "")
                    elif cfg["type"] == "image":
                        images = body.get("images") or []
                        media_url = images[0].get("url", "") if images else ""
                    elif cfg["type"] == "audio":
                        media_url = (body.get("audio") or {}).get("url", "") if isinstance(body.get("audio"), dict) else body.get("audio_url", "")
                    elapsed = time.time() - start
                    self._record_spend(est_cost)
                    return FalResult(
                        model=model,
                        modality=cfg["type"],
                        request_id=body.get("request_id", ""),
                        media_url=media_url,
                        cost_usd=est_cost,
                        duration_sec=elapsed,
                        tier=cfg.get("tier", 0),
                        metadata=body,
                    )
        except Exception as e:
            log.error("fal submit failed: %s", e)
            return FalResult(model=model, modality=cfg["type"], error=str(e))

    def compare_with_modal(self, modal_cost: float, duration_sec: float = 5.0) -> dict[str, Any]:
        return {
            "modal_cost_usd": modal_cost,
            "fal_wan_t2v_720p_5s": self.estimate_cost("wan-t2v", duration_sec=duration_sec, resolution="720p"),
            "fal_wan_pro_5s": self.estimate_cost("wan-pro-t2v", duration_sec=duration_sec),
            "fal_ltx_fast_5s": self.estimate_cost("ltx-2.3-fast-t2v", duration_sec=duration_sec),
            "recommendation": "modal" if modal_cost < 0.05 else ("fal" if modal_cost > 0.30 else "either"),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "budget_usd": self.budget_usd,
            "spent_usd": self.spend_tracker["spent"],
            "remaining_usd": self.remaining_budget(),
            "models_available": len(FAL_MODELS),
            "free_credit_offer": "$20 on signup (business email)",
            "models": {
                name: {
                    "type": cfg["type"],
                    "tier": cfg.get("tier"),
                    "open_source": cfg.get("open_source", False),
                    "ultrarealistic": cfg.get("ultrarealistic", False),
                }
                for name, cfg in FAL_MODELS.items()
            },
        }


__all__ = [
    "FAL_MODELS",
    "FAL_BASE_URL",
    "FAL_QUEUE_URL",
    "DEFAULT_BUDGET_USD",
    "FalResult",
    "FalBudgetExceeded",
    "FalDispatcher",
]
