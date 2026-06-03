"""Enterprise thumbnail generator — Pillow-based, theme-aware."""
import os, logging, random, textwrap
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)

_THEMES = {
    "default": {"bg": (15, 15, 25), "accent": (123, 47, 247), "text": (255, 255, 255)},
    "dark": {"bg": (5, 5, 10), "accent": (0, 212, 255), "text": (255, 255, 255)},
    "warm": {"bg": (40, 20, 10), "accent": (255, 165, 0), "text": (255, 240, 220)},
    "fresh": {"bg": (10, 30, 20), "accent": (74, 222, 128), "text": (220, 255, 230)},
    "luxury": {"bg": (15, 10, 20), "accent": (255, 215, 0), "text": (240, 230, 210)},
    "bright": {"bg": (240, 240, 250), "accent": (123, 47, 247), "text": (15, 15, 25)},
    "food": {"bg": (60, 20, 10), "accent": (255, 100, 50), "text": (255, 240, 220)},
    "skincare": {"bg": (20, 25, 35), "accent": (255, 150, 200), "text": (255, 240, 250)},
    "fashion": {"bg": (10, 10, 25), "accent": (200, 100, 255), "text": (240, 220, 255)},
    "tech": {"bg": (10, 15, 25), "accent": (0, 180, 255), "text": (220, 240, 255)},
}


class ThumbnailGenerator:
    """Generate UGC video thumbnails with brand themes.

    Produces 1080×1920 (Instagram Reels / TikTok portrait) or
    1280×720 (YouTube landscape) thumbnails.
    """

    def __init__(self, output_dir: str = None, theme: str = "default"):
        self.output_dir = output_dir or skynet_config.get("paths", "output_dir", default="/tmp")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.theme = theme
        self._font_path = self._find_font()

    def set_theme(self, name: str):
        if name in _THEMES:
            self.theme = name

    def generate(self, hook: str, product: str = "", platform: str = "tiktok",
                 product_image: str = None, output_path: str = None) -> str:
        """Generate a thumbnail image.

        Args:
            hook: The hook text to display.
            product: Product name.
            platform: 'tiktok', 'instagram', or 'youtube'.
            product_image: Optional product photo to overlay.
            output_path: Where to save. Auto-generated if None.

        Returns:
            Path to the generated PNG/JPG.
        """
        theme = _THEMES.get(self.theme, _THEMES["default"])
        is_youtube = platform == "youtube"

        if is_youtube:
            size = (1280, 720)
        else:
            size = (1080, 1920)

        img = Image.new("RGB", size, theme["bg"])
        draw = ImageDraw.Draw(img)

        # Gradient overlay
        for y in range(size[1]):
            ratio = y / size[1]
            r = int(theme["bg"][0] * (1 - ratio) + theme["accent"][0] * ratio * 0.3)
            g = int(theme["bg"][1] * (1 - ratio) + theme["accent"][1] * ratio * 0.3)
            b = int(theme["bg"][2] * (1 - ratio) + theme["accent"][2] * ratio * 0.3)
            draw.line([(0, y), (size[0], y)], fill=(r, g, b))

        # Product image overlay
        if product_image and os.path.exists(product_image):
            try:
                prod = Image.open(product_image).convert("RGBA")
                max_s = size[0] // 3 if is_youtube else size[0] // 2
                prod.thumbnail((max_s, max_s), Image.LANCZOS)
                px = (size[0] - prod.width) // 2
                py = size[1] // 6 if is_youtube else size[1] // 5
                img.paste(prod, (px, py), prod)
            except Exception as e:
                log.warning("Product image overlay failed: %s", e)

        # Accent bar
        if not is_youtube:
            bar_h = size[1] // 3
            for y in range(bar_h - 80, bar_h):
                alpha = int(255 * (1 - (y - (bar_h - 80)) / 80))
                overlay = Image.new("RGBA", (size[0], 1),
                                    theme["accent"] + (alpha // 4,))
                img.paste(overlay, (0, y), overlay)
        else:
            draw.rectangle([0, size[1] - 8, size[0], size[1]], fill=theme["accent"])

        # Hook text
        font_large = self._get_font(size[0] // 16)
        lines = textwrap.wrap(hook, width=25 if is_youtube else 18)
        line_h = size[1] // 22
        start_y = size[1] // 3 if not product_image else size[1] // 2
        for i, line in enumerate(lines[:4]):
            y_pos = start_y + i * line_h
            draw.text((size[0] // 2, y_pos), line.upper(),
                      fill=theme["text"], font=font_large, anchor="mt")

        # Product name badge
        if product:
            font_small = self._get_font(size[0] // 28)
            badge_y = size[1] - (size[1] // 6 if not is_youtube else size[1] // 8)
            draw.rounded_rectangle(
                [size[0] // 4, badge_y, 3 * size[0] // 4, badge_y + size[1] // 18],
                radius=size[0] // 40, fill=theme["accent"] + (200,),
            )
            draw.text(
                (size[0] // 2, badge_y + size[1] // 36),
                product.upper(),
                fill=(255, 255, 255), font=font_small, anchor="mt",
            )

        # Save
        output_path = output_path or self._auto_path(platform)
        img.save(output_path, "JPEG", quality=92)
        log.info("Thumbnail: %s (%s, %s theme)", output_path, platform, self.theme)
        return output_path

    def _get_font(self, size: int):
        try:
            return ImageFont.truetype(self._font_path, size)
        except Exception:
            return ImageFont.load_default()

    def _auto_path(self, platform: str) -> str:
        import uuid
        return os.path.join(self.output_dir, f"thumb_{platform}_{uuid.uuid4().hex[:8]}.jpg")

    @staticmethod
    def _find_font() -> str:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return ""

    @staticmethod
    def available_themes() -> list:
        return list(_THEMES.keys())
