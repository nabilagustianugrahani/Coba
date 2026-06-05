"""Modal.com apps package.

Three serverless GPU apps for UGC content generation:
  - text_to_image: FLUX.2-klein-4B (default) + FLUX.1.1 Pro Ultra (premium)
  - text_to_video: Wan 2.1 1.3B/14B + HunyuanVideo
  - voice_synth:   CosyVoice 2.0 with Indonesian + English voices

Deployment:
    modal deploy integrations/modal_apps/text_to_image.py
    modal deploy integrations/modal_apps/text_to_video.py
    modal deploy integrations/modal_apps/voice_synth.py

All apps use SGLang-Diffusion where possible (1.2x-5.9x faster than
raw diffusers, 10x cheaper than Replicate).
"""
from __future__ import annotations

__all__ = [
    "APP_NAMES",
    "DEFAULT_GPU_MAP",
    "COST_PER_SECOND",
]

APP_NAMES: list[str] = [
    "ugc-text-to-image",
    "ugc-text-to-video",
    "ugc-voice-synth",
]

DEFAULT_GPU_MAP: dict[str, str] = {
    "ugc-text-to-image": "A10G",
    "ugc-text-to-video": "A10G",
    "ugc-voice-synth": "T4",
}

COST_PER_SECOND: dict[str, float] = {
    "T4": 0.000589,
    "A10G": 0.000976,
    "H100": 0.001323,
}
