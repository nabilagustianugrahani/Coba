"""Video composition engine for UGC content.

Assembles a complete TikTok‑style vertical video from:
- A TTS voiceover track
- Background footage (stock or generated)
- Text overlays (influencer name, product name, price, CTA)
- Product image inset
- Caption / subtitle strip
"""

from __future__ import annotations

import logging
import os
import random
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_SIZE = (1080, 1920)  # 9:16 vertical (TikTok format)
MAX_DURATION = 60           # seconds

FONT_DEFAULT = "assets/fonts/NotoSans-Bold.ttf"
FONT_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ---------------------------------------------------------------------------
# VideoComposer
# ---------------------------------------------------------------------------


class VideoComposer:
    """Compose a complete UGC video from script, influencer metadata and a
    product description.

    Usage::

        composer = VideoComposer()
        video_path = composer.compose_ugc(
            script="Halo guys, hari ini kita review …",
            influencer={"name": "Budi", "personality": "energik"},
            product="Smartphone X Pro Max",
        )
    """

    def __init__(self, output_dir: str = "output/videos") -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose_ugc(
        self,
        script: str,
        influencer: dict[str, Any],
        product: str,
        product_image: Optional[str] = None,
        price: str = "",
        call_to_action: str = "Klik link di bio!",
        background_clip: Optional[str] = None,
    ) -> Optional[str]:
        """Produce a TikTok‑ready UGC video.

        Parameters
        ----------
        script : str
            Voiceover script lines.
        influencer : dict
            Must contain at least ``"name"``; may also include
            ``"personality"``, ``"voice_style"``, ``"voice"`` (TTS voice id).
        product : str
            Product name.
        product_image : str or None
            Path to a product image to overlay (optional).
        price : str
            Price string displayed on screen (optional).
        call_to_action : str
            Call‑to‑action text at the end.
        background_clip : str or None
            Path to a background video.  Auto‑generated if omitted.

        Returns
        -------
        str or None
            Absolute path of the rendered MP4, or *None* on failure.
        """
        from moviepy.editor import (
            AudioFileClip,
            CompositeVideoClip,
            ImageClip,
            TextClip,
            VideoFileClip,
            concatenate_videoclips,
        )

        try:
            # 1. Generate voiceover
            voice_path = self._generate_voiceover(script, influencer)
            if not voice_path or not Path(voice_path).exists():
                log.error("Voiceover generation failed – aborting composition")
                return None

            voice_clip = AudioFileClip(voice_path)
            duration = min(voice_clip.duration, float(MAX_DURATION))

            # 2. Background footage
            bg_clip = self._load_background(
                background_clip, duration, OUTPUT_SIZE
            )

            # 3. Build overlay layers
            layers: list = [bg_clip]

            # Product image overlay (top‑right corner)
            if product_image and Path(product_image).exists():
                img_clip = (
                    ImageClip(product_image)
                    .resize(height=180)
                    .set_position(("right", 80))
                    .set_duration(duration)
                    .crossfadein(0.3)
                )
                layers.append(img_clip)

            # Influencer name bar (top)
            name_clip = self._make_text_clip(
                influencer.get("name", "Influencer"),
                fontsize=48,
                color="white",
                stroke_width=2,
                position=("center", 40),
                duration=duration,
            )
            layers.append(name_clip)

            # Product name + price (bottom third)
            product_line = product
            if price:
                product_line += f" — {price}"
            product_clip = self._make_text_clip(
                product_line,
                fontsize=38,
                color="#FFD700",
                stroke_width=1,
                position=("center", "center"),
                duration=duration,
            )
            layers.append(product_clip)

            # Caption / subtitle (lower third, above CTA)
            subtitle = self._truncate_text(script, 80)
            caption_clip = self._make_text_clip(
                subtitle,
                fontsize=30,
                color="white",
                stroke_width=1,
                position=("center", 1400),
                duration=duration,
            )
            layers.append(caption_clip)

            # Call‑to‑action overlay (bottom)
            cta_clip = self._make_text_clip(
                call_to_action,
                fontsize=42,
                color="#00FF88",
                stroke_width=2,
                position=("center", 1700),
                duration=duration,
                bg_color=(0, 0, 0, 160),
            )
            layers.append(cta_clip)

            # 4. Composite
            final = CompositeVideoClip(layers, size=OUTPUT_SIZE)
            final = final.set_audio(voice_clip)
            final = final.subclip(0, duration)

            # 5. Write
            out_name = f"ugc_{influencer.get('name', 'influencer').replace(' ', '_')}_{hash(product) & 0xFFFF}.mp4"
            out_path = str(self._output_dir / out_name)
            final.write_videofile(
                out_path,
                codec="libx264",
                audio_codec="aac",
                fps=24,
                preset="medium",
                threads=2,
                logger=None,  # suppress moviepy verbose output
            )

            log.info("UGC video composed: %s", out_path)
            return out_path

        except Exception as exc:
            log.error("Video composition failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # ---- Text clips ---------------------------------------------------

    def _make_text_clip(
        self,
        text: str,
        fontsize: int = 36,
        color: str = "white",
        stroke_width: int = 1,
        position: tuple = ("center", "center"),
        duration: float = 5.0,
        bg_color: Optional[tuple[int, int, int, int]] = None,
    ) -> "TextClip":
        """Build a styled TextClip with automatic font fallback."""
        from moviepy.editor import TextClip

        font = FONT_DEFAULT if Path(FONT_DEFAULT).exists() else FONT_FALLBACK

        kwargs: dict = {
            "txt": text,
            "fontsize": fontsize,
            "color": color,
            "stroke_color": "black",
            "stroke_width": stroke_width,
            "font": font,
            "size": (OUTPUT_SIZE[0] - 80, None),  # horizontal padding
            "method": "caption",
        }
        if bg_color:
            kwargs["bg_color"] = bg_color

        clip = TextClip(**kwargs)
        return clip.set_position(position).set_duration(duration)

    # ---- Voiceover ----------------------------------------------------

    def _generate_voiceover(
        self,
        script: str,
        influencer: dict[str, Any],
    ) -> Optional[str]:
        """Generate TTS audio for *script* using the influencer's voice
        preference.  Falls back to the default edge‑tts voice."""
        from ugc_ai_overpower.media.tts import generate_voice

        # Map influencer personality to a voice style.
        voice = influencer.get("voice", "")
        if not voice:
            personality = influencer.get("personality", "").lower()
            if "energik" in personality or "pria" in personality:
                voice = "id-ID-ArdiNeural"
            else:
                voice = "id-ID-GadisNeural"

        out_name = f"voiceover_{hash(script) & 0xFFFFFFFF}.mp3"
        out = str(self._output_dir.parent / "audio" / out_name)
        Path(out).parent.mkdir(parents=True, exist_ok=True)

        return generate_voice(script, voice=voice, output=out)

    # ---- Background ---------------------------------------------------

    def _load_background(
        self,
        clip_path: Optional[str],
        duration: float,
        size: tuple[int, int],
    ) -> "VideoClip":
        """Load or create a background video clip.

        If *clip_path* is provided and readable it is used (looped / trimmed
        to *duration*).  Otherwise a solid‑colour background is generated.
        """
        from moviepy.editor import ColorClip

        if clip_path and Path(clip_path).exists():
            try:
                from moviepy.editor import VideoFileClip, concatenate_videoclips

                clip = VideoFileClip(clip_path)
                # Loop if shorter than required duration.
                if clip.duration < duration:
                    n_loops = int(duration // clip.duration) + 1
                    clip = concatenate_videoclips([clip] * n_loops)
                clip = clip.subclip(0, duration)
                clip = clip.resize(newsize=size)
                return clip
            except Exception as exc:
                log.warning("Could not load background clip %s: %s", clip_path, exc)

        # Fallback: solid colour with a subtle gradient simulation.
        r, g, b = random.choice(
            [(20, 20, 40), (30, 20, 30), (25, 25, 50), (40, 30, 20)]
        )
        return ColorClip(size=size, color=(r, g, b)).set_duration(duration)

    # ---- Truncation ---------------------------------------------------

    @staticmethod
    def _truncate_text(text: str, max_chars: int = 80) -> str:
        """Truncate *text* to *max_chars* adding an ellipsis if needed."""
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rsplit(" ", 1)[0] + "…"
