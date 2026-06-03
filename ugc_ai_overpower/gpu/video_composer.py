"""UGC Video Composer — ffmpeg + Pillow + edge-tts (zero moviepy dependency)."""
import os, random, subprocess, json, asyncio, datetime, logging, shutil, tempfile, uuid, concurrent.futures
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

import edge_tts

log = logging.getLogger(__name__)

# Color themes for brand consistency
THEMES = {
    "default":  {"bg": (30, 30, 40), "text": "white", "stroke": "black", "accent": "#7b2ff7"},
    "dark":     {"bg": (10, 10, 15), "text": "#e0e0e0", "stroke": "black", "accent": "#00d4ff"},
    "warm":     {"bg": (40, 25, 20), "text": "#fff5e6", "stroke": "#3a1a0a", "accent": "#ff6b35"},
    "fresh":    {"bg": (20, 35, 25), "text": "#e6ffe6", "stroke": "#0a3a1a", "accent": "#4ade80"},
    "luxury":   {"bg": (25, 20, 30), "text": "#f0e6ff", "stroke": "#1a0a2e", "accent": "#a855f7"},
    "bright":   {"bg": (50, 50, 60), "text": "white", "stroke": "#1a1a2e", "accent": "#facc15"},
}

# Background stock queries per niche
BG_QUERIES = {
    "lifestyle":   ["lifestyle", "daily routine", "morning routine", "coffee", "work from home"],
    "skincare":    ["skincare", "beauty", "face", "glowing skin", "spa"],
    "fashion":     ["fashion", "outfit", "style", "shopping", "wardrobe"],
    "food":        ["food", "cooking", "kitchen", "delicious", "restaurant"],
    "tech":        ["technology", "office", "digital", "laptop", "workspace"],
    "fitness":     ["fitness", "workout", "gym", "running", "yoga"],
    "muslim":      ["ramadan", "prayer", "mosque", "hijab fashion", "modest fashion"],
}

# Voice options per gender/niche
VOICES = {
    "male":   ["id-ID-ArdiNeural", "id-ID-DimasNeural"],
    "female": ["id-ID-GadisNeural", "id-ID-AyuNeural"],
}

TEMPLATE_INTROS = [
    "Hai semuanya! Kembali lagi sama gue!",
    "Halo guys! Gue mau share sesuatu nih!",
    "Welcome back! Kali ini gue bakal bahas...",
    "Eh guys, lo pada tau gak sih...",
]

TEMPLATE_OUTROS = [
    "Gitu aja! Jangan lupa like dan subscribe!",
    "Semoga bermanfaat! Share ke temen lo ya!",
    "Makasih udah nonton! Sampai jumpa!",
    "Komen di bawah ya! Gue bales satu-satu!",
]


class VideoComposer:
    def __init__(self, output_dir="output/videos", default_theme="default", watermark_text="", use_avatar=False):
        self.output_dir = output_dir
        self.default_theme = THEMES.get(default_theme, THEMES["default"])
        self.watermark_text = watermark_text
        self.use_avatar = use_avatar
        self._avatar_engine = None
        os.makedirs(output_dir, exist_ok=True)
        self._cache_dir = os.path.join(output_dir, ".cache")
        os.makedirs(self._cache_dir, exist_ok=True)

    def set_theme(self, theme_name: str):
        if theme_name in THEMES:
            self.default_theme = THEMES[theme_name]

    def set_watermark(self, text: str):
        self.watermark_text = text

    def _download_stock_video(self, queries: list, duration=10):
        """Download free stock video from Pexels as background."""
        query = random.choice(queries)
        safe_name = query.replace(" ", "_").lower()
        cached = os.path.join(self._cache_dir, f"{safe_name}.mp4")
        if os.path.exists(cached):
            return cached

        try:
            import requests
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                params={"query": query, "per_page": 5, "orientation": "portrait"},
                headers={"Authorization": os.getenv("PEXELS_API_KEY", "")},
                timeout=10,
            )
            videos = resp.json().get("videos", [])
            if videos:
                chosen = random.choice(videos)
                files = chosen.get("video_files", [])
                best = max(files, key=lambda f: f.get("width", 0) or 0)
                r = requests.get(best["link"], timeout=30)
                with open(cached, "wb") as f:
                    f.write(r.content)
                return cached
        except Exception as e:
            log.warning("Stock download failed: %s", e)
        return None

    async def _generate_voiceover(self, text, output_path, voice="id-ID-ArdiNeural"):
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return output_path

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "csv=p=0", audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())

    def _generate_frame(self, text: str, size=(720, 1280), theme=None, product_image=None, watermark=None) -> Image.Image:
        """Generate a single frame with background, text, product image, watermark."""
        theme = theme or self.default_theme
        width, height = size
        
        # Create background gradient
        img = Image.new("RGB", size, theme["bg"])
        draw = ImageDraw.Draw(img)
        
        # Add vertical gradient overlay
        for y in range(height):
            ratio = y / height
            r = int(theme["bg"][0] * (1 - ratio) + int(theme["accent"][1:3], 16) * ratio * 0.3)
            g = int(theme["bg"][1] * (1 - ratio) + int(theme["accent"][3:5], 16) * ratio * 0.3)
            b = int(theme["bg"][2] * (1 - ratio) + int(theme["accent"][5:7], 16) * ratio * 0.3)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # Add product image if provided
        if product_image and os.path.exists(product_image):
            try:
                prod_img = Image.open(product_image).convert("RGBA")
                max_size = (width // 3, height // 4)
                prod_img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Center product image
                px = (width - prod_img.width) // 2
                py = height // 6
                img.paste(prod_img, (px, py), prod_img)
            except Exception as e:
                log.warning("Product image failed: %s", e)
        
        # Add text with font
        try:
            font_path = self._find_font()
            font = ImageFont.truetype(font_path, 42)
        except:
            font = ImageFont.load_default()

        # Wrap text and draw
        lines = self._wrap_text(text, font, width - 40)
        line_height = 50
        start_y = height // 3 if product_image else height // 4
        
        for i, line in enumerate(lines[:4]):
            y_pos = start_y + i * line_height
            # Draw outline
            for dx, dy in [(-2,-2), (-2,0), (-2,2), (0,-2), (0,2), (2,-2), (2,0), (2,2)]:
                draw.text((width//2 + dx, y_pos + dy), line, fill=theme["stroke"], font=font, anchor="mt")
            # Draw main text
            draw.text((width//2, y_pos), line, fill=theme["text"], font=font, anchor="mt")

        # Add watermark
        if watermark:
            try:
                watermark_font = ImageFont.truetype(font_path, 20) if font_path else ImageFont.load_default()
                bbox = draw.textbbox((0, 0), watermark, font=watermark_font)
                text_width = bbox[2] - bbox[0]
                pos_x = width - text_width - 20
                pos_y = height - 40
                draw.text((pos_x, pos_y), watermark, fill="white", font=watermark_font)
            except:
                pass
        
        return img

    def _wrap_text(self, text: str, font, max_width: int) -> list:
        """Wrap text to fit within max_width."""
        import textwrap
        lines = textwrap.wrap(text, width=30)
        return lines

    def _find_font(self) -> str:
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

    def _render_video_from_frame(self, frame_path: str, audio_path: str, output_path: str, 
                                 duration: float = None, zoom_effect: bool = True):
        """Render video from single frame + audio using ffmpeg."""
        if duration is None:
            duration = self._get_audio_duration(audio_path)
        
        # Calculate zoom factor based on duration
        zoom_factor = f"min(zoom+0.001,1.1)" if zoom_effect else "zoom"
        zoom_duration = int(duration * 25)  # 25fps * seconds
        
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", frame_path,
            "-i", audio_path,
            "-vf", f"zoompan=z='{zoom_factor}':d={zoom_duration}:fps=25,scale=720:1280:flags=lanczos",
            "-c:v", "libx264", "-c:a", "aac", "-shortest",
            "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")

    def create_ugc_video(
        self,
        script,
        influencer,
        product_image=None,
        niche="lifestyle",
        gender="male",
        add_intro=False,
        add_outro=False,
        theme_override=None,
        face_image=None,
    ) -> str:
        theme = THEMES.get(theme_override, self.default_theme) if theme_override else self.default_theme
        voice = random.choice(VOICES.get(gender, VOICES["male"]))
        bg_queries = BG_QUERIES.get(niche, BG_QUERIES["lifestyle"])

        # Build full script with intro/outro
        full_text = script
        if add_intro:
            full_text = random.choice(TEMPLATE_INTROS) + " " + full_text
        if add_outro:
            full_text = full_text + " " + random.choice(TEMPLATE_OUTROS)

        # Generate voiceover
        voiceover_path = os.path.join(self.output_dir, f"vo_{influencer}_{random.randint(1000,9999)}.mp3")
        asyncio.run(self._generate_voiceover(full_text, voiceover_path, voice))

        output = os.path.join(
            self.output_dir,
            f"ugc_{influencer}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}.mp4"
        )

        if self.use_avatar and face_image and os.path.exists(face_image):
            avatar_path = self._render_avatar(face_image, voiceover_path, influencer)
            if avatar_path:
                log.info("UGC video created (avatar): %s", output)
                return avatar_path

        # Generate frame
        frame_path = os.path.join(self.output_dir, f"frame_{influencer}_{uuid.uuid4().hex[:8]}.png")
        frame = self._generate_frame(full_text, (720, 1280), theme, product_image, self.watermark_text)
        frame.save(frame_path)

        self._render_video_from_frame(frame_path, voiceover_path, output)

        try:
            os.remove(frame_path)
            os.remove(voiceover_path)
        except OSError:
            pass

        log.info("UGC video created: %s", output)
        return output

    def _render_avatar(self, face_image: str, audio_path: str, influencer: str) -> Optional[str]:
        if self._avatar_engine is None:
            from ugc_ai_overpower.gpu.avatar_engine import AvatarEngine
            self._avatar_engine = AvatarEngine(output_dir=self.output_dir)
        output = os.path.join(
            self.output_dir,
            f"avatar_{influencer}_{uuid.uuid4().hex[:8]}.mp4"
        )
        return self._avatar_engine.generate_avatar(face_image, audio_path, output)

    def create_batch_videos(self, scripts: list, product_image: str = "", niche: str = "lifestyle",
                            max_workers: int = 4, face_image: str = None) -> list:
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            fut_map = {}
            for i, item in enumerate(scripts):
                fut = pool.submit(
                    self.create_ugc_video,
                    script=item.get("script", ""),
                    influencer=item.get("influencer", "creator"),
                    product_image=product_image,
                    niche=niche,
                    gender=item.get("gender", "male"),
                    add_intro=item.get("add_intro", True),
                    add_outro=item.get("add_outro", True),
                    theme_override=item.get("theme"),
                    face_image=face_image or item.get("face_image"),
                )
                fut_map[fut] = i
            for fut in concurrent.futures.as_completed(fut_map):
                idx = fut_map[fut]
                try:
                    path = fut.result()
                    results.append({"index": idx, "path": path})
                except Exception as e:
                    log.warning("Video %d failed: %s", idx, e)
        results.sort(key=lambda r: r["index"])
        return results
