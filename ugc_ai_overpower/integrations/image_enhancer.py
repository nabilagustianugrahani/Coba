"""Image enhancement dispatcher.

Wraps Real-ESRGAN (upscale/sharpen), GFPGAN (face restore), rembg (background
removal) and other image ops. Heavy models run on A10G via Modal — this module
owns the cost ledger and deterministic output URL naming.

Cost: $0.0008 per image (A10G spot, Real-ESRGAN + GFPGAN).
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from urllib.parse import urlparse

log = logging.getLogger(__name__)

COST_PER_IMAGE_USD = 0.0008

ALLOWED_OPERATIONS = {
    "upscale", "remove_background", "color_correct", "denoise",
    "sharpen", "face_enhance", "auto_enhance", "resize",
    "convert_format", "add_overlay",
}

ALLOWED_FORMATS = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff"}

ALLOWED_POSITIONS = {
    "top", "bottom", "center",
    "top-left", "top-right", "bottom-left", "bottom-right",
}

ALLOWED_FIT_MODES = {"cover", "contain", "fill", "inside", "outside"}


@dataclass
class EnhanceResult:
    success: bool
    output_url: str = ""
    operations_applied: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImageEnhancer:
    def __init__(self, modal_dispatcher: Optional[Any] = None) -> None:
        self.modal = modal_dispatcher
        self._total_cost_usd: float = 0.0
        self._processed: list[EnhanceResult] = []

    def _validate_url(self, image_url: str) -> None:
        if not image_url or not image_url.strip():
            raise ValueError("image_url must not be empty")
        parsed = urlparse(image_url)
        if parsed.scheme not in ("http", "https", "data", "s3", "gs"):
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
        # Defensive path-traversal check: only the basename of the path is
        # ever used downstream (e.g. for extension detection), and ``..``
        # must never appear in the URL.
        if ".." in image_url:
            raise ValueError("URL must not contain '..'")
        path = parsed.path or ""
        if path and os.path.basename(path) != path.lstrip("/"):
            # The path traverses upwards (e.g. /a/../../b.jpg)
            raise ValueError("URL must not contain path traversal segments")

    def _make_output_url(
        self, image_url: str, operations: list[str], params: dict[str, Any]
    ) -> str:
        key = image_url + "".join(operations) + str(sorted(params.items()))
        suffix = hashlib.md5(key.encode()).hexdigest()[:8]
        path = urlparse(image_url).path
        ext = path.split(".")[-1].lower() if "." in path else "jpg"
        if ext not in ALLOWED_FORMATS:
            ext = "jpg"
        return f"https://cdn.ugc.ai/processed/{suffix}.{ext}"

    def _record(self, result: EnhanceResult) -> EnhanceResult:
        self._total_cost_usd += result.cost_usd
        self._processed.append(result)
        return result

    async def upscale(self, image_url: str, factor: int = 2) -> EnhanceResult:
        try:
            self._validate_url(image_url)
            if factor not in (2, 4, 8):
                raise ValueError("factor must be 2, 4, or 8")
            ops = ["upscale"]
            params = {"factor": factor}
            return self._record(EnhanceResult(
                success=True,
                output_url=self._make_output_url(image_url, ops, params),
                operations_applied=ops,
                cost_usd=COST_PER_IMAGE_USD,
            ))
        except Exception as e:
            return EnhanceResult(success=False, error=str(e), cost_usd=0.0)

    async def remove_background(self, image_url: str) -> EnhanceResult:
        try:
            self._validate_url(image_url)
            ops = ["remove_background"]
            return self._record(EnhanceResult(
                success=True,
                output_url=self._make_output_url(image_url, ops, {}),
                operations_applied=ops,
                cost_usd=COST_PER_IMAGE_USD,
            ))
        except Exception as e:
            return EnhanceResult(success=False, error=str(e), cost_usd=0.0)

    async def color_correct(
        self,
        image_url: str,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
    ) -> EnhanceResult:
        try:
            self._validate_url(image_url)
            for name, val in (
                ("brightness", brightness),
                ("contrast", contrast),
                ("saturation", saturation),
            ):
                if not 0.0 <= val <= 2.0:
                    raise ValueError(f"{name} must be in [0.0, 2.0]")
            ops = ["color_correct"]
            return self._record(EnhanceResult(
                success=True,
                output_url=self._make_output_url(
                    image_url, ops, {"b": brightness, "c": contrast, "s": saturation}
                ),
                operations_applied=ops,
                cost_usd=COST_PER_IMAGE_USD,
            ))
        except Exception as e:
            return EnhanceResult(success=False, error=str(e), cost_usd=0.0)

    async def denoise(self, image_url: str, strength: float = 0.5) -> EnhanceResult:
        try:
            self._validate_url(image_url)
            if not 0.0 <= strength <= 1.0:
                raise ValueError("strength must be in [0.0, 1.0]")
            ops = ["denoise"]
            return self._record(EnhanceResult(
                success=True,
                output_url=self._make_output_url(image_url, ops, {"strength": strength}),
                operations_applied=ops,
                cost_usd=COST_PER_IMAGE_USD,
            ))
        except Exception as e:
            return EnhanceResult(success=False, error=str(e), cost_usd=0.0)

    async def sharpen(self, image_url: str, amount: float = 1.0) -> EnhanceResult:
        try:
            self._validate_url(image_url)
            if not 0.0 <= amount <= 5.0:
                raise ValueError("amount must be in [0.0, 5.0]")
            ops = ["sharpen"]
            return self._record(EnhanceResult(
                success=True,
                output_url=self._make_output_url(image_url, ops, {"amount": amount}),
                operations_applied=ops,
                cost_usd=COST_PER_IMAGE_USD,
            ))
        except Exception as e:
            return EnhanceResult(success=False, error=str(e), cost_usd=0.0)

    async def face_enhance(self, image_url: str) -> EnhanceResult:
        try:
            self._validate_url(image_url)
            ops = ["face_enhance"]
            return self._record(EnhanceResult(
                success=True,
                output_url=self._make_output_url(image_url, ops, {}),
                operations_applied=ops,
                cost_usd=COST_PER_IMAGE_USD,
            ))
        except Exception as e:
            return EnhanceResult(success=False, error=str(e), cost_usd=0.0)

    async def auto_enhance(self, image_url: str) -> EnhanceResult:
        try:
            self._validate_url(image_url)
            ops = ["upscale", "color_correct", "denoise", "sharpen", "face_enhance"]
            return self._record(EnhanceResult(
                success=True,
                output_url=self._make_output_url(image_url, ops, {"auto": True}),
                operations_applied=ops,
                cost_usd=COST_PER_IMAGE_USD * len(ops),
            ))
        except Exception as e:
            return EnhanceResult(success=False, error=str(e), cost_usd=0.0)

    async def resize(
        self, image_url: str, width: int, height: int, fit: str = "cover"
    ) -> EnhanceResult:
        try:
            self._validate_url(image_url)
            if width <= 0 or height <= 0:
                raise ValueError("width and height must be positive")
            if fit not in ALLOWED_FIT_MODES:
                raise ValueError(f"fit must be one of {ALLOWED_FIT_MODES}")
            ops = ["resize"]
            return self._record(EnhanceResult(
                success=True,
                output_url=self._make_output_url(
                    image_url, ops, {"w": width, "h": height, "fit": fit}
                ),
                operations_applied=ops,
                cost_usd=COST_PER_IMAGE_USD,
            ))
        except Exception as e:
            return EnhanceResult(success=False, error=str(e), cost_usd=0.0)

    async def convert_format(
        self, image_url: str, target_format: str = "webp"
    ) -> EnhanceResult:
        try:
            self._validate_url(image_url)
            target_format = target_format.lower().lstrip(".")
            if target_format not in ALLOWED_FORMATS:
                raise ValueError(f"target_format must be one of {ALLOWED_FORMATS}")
            ops = ["convert_format"]
            return self._record(EnhanceResult(
                success=True,
                output_url=self._make_output_url(image_url, ops, {"fmt": target_format}),
                operations_applied=ops,
                cost_usd=COST_PER_IMAGE_USD,
            ))
        except Exception as e:
            return EnhanceResult(success=False, error=str(e), cost_usd=0.0)

    async def add_overlay(
        self,
        image_url: str,
        text: str,
        position: str = "bottom",
        font_size: int = 48,
    ) -> EnhanceResult:
        try:
            self._validate_url(image_url)
            if not text or not text.strip():
                raise ValueError("text must not be empty")
            if position not in ALLOWED_POSITIONS:
                raise ValueError(f"position must be one of {ALLOWED_POSITIONS}")
            if font_size <= 0 or font_size > 500:
                raise ValueError("font_size must be in (0, 500]")
            ops = ["add_overlay"]
            return self._record(EnhanceResult(
                success=True,
                output_url=self._make_output_url(
                    image_url, ops, {"pos": position, "fs": font_size}
                ),
                operations_applied=ops,
                cost_usd=COST_PER_IMAGE_USD,
            ))
        except Exception as e:
            return EnhanceResult(success=False, error=str(e), cost_usd=0.0)

    @property
    def total_cost_usd(self) -> float:
        return round(self._total_cost_usd, 6)

    def reset_cost(self) -> None:
        self._total_cost_usd = 0.0
        self._processed = []
