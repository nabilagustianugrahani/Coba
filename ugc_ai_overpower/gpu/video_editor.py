"""Multi-scene UGC Video Editor — 5-scene template with PIP, BGM, transitions.

Uses ffmpeg for all rendering (xfade, overlay, drawtext).
Zero moviepy dependency. Pillow only for frame generation.

Template: Hook → Problem → Solution → Testimonial → CTA
"""
import os, random, subprocess, json, asyncio, datetime, logging, shutil, tempfile, uuid, concurrent.futures, math
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from ugc_ai_overpower.core.config import skynet_config
from ugc_ai_overpower.gpu.tts_engine import TTSEngine
from ugc_ai_overpower.gpu.avatar_engine import AvatarEngine

log = logging.getLogger(__name__)

THEMES = {
    "default":  {"bg": (15, 15, 30), "text": "white", "accent": "#7b2ff7", "accent_rgb": (123, 47, 247)},
    "dark":     {"bg": (5, 5, 15), "text": "#e0e0e0", "accent": "#00d4ff", "accent_rgb": (0, 212, 255)},
    "warm":     {"bg": (30, 20, 15), "text": "#fff5e6", "accent": "#ff6b35", "accent_rgb": (255, 107, 53)},
    "fresh":    {"bg": (15, 30, 20), "text": "#e6ffe6", "accent": "#4ade80", "accent_rgb": (74, 222, 128)},
    "luxury":   {"bg": (20, 15, 25), "text": "#f0e6ff", "accent": "#a855f7", "accent_rgb": (168, 85, 247)},
    "bright":   {"bg": (40, 40, 55), "text": "white", "accent": "#facc15", "accent_rgb": (250, 204, 21)},
    "food":     {"bg": (45, 15, 10), "text": "#fff5e6", "accent": "#ff6b35", "accent_rgb": (255, 107, 53)},
    "skincare": {"bg": (15, 20, 30), "text": "#f0e6ff", "accent": "#f472b6", "accent_rgb": (244, 114, 182)},
    "fashion":  {"bg": (10, 10, 25), "text": "#f0e6ff", "accent": "#c084fc", "accent_rgb": (192, 132, 252)},
    "tech":     {"bg": (10, 15, 25), "text": "#e0f0ff", "accent": "#38bdf8", "accent_rgb": (56, 189, 248)},
}

VOICES = {
    "male":   ["id-ID-ArdiNeural", "id-ID-DimasNeural"],
    "female": ["id-ID-GadisNeural", "id-ID-AyuNeural"],
}

WIDTH, HEIGHT = 720, 1280
FPS = 25


class Scene:
    def __init__(self, scene_type: str, text: str, duration: float, product_image: str = None):
        self.type = scene_type
        self.text = text
        self.duration = duration
        self.product_image = product_image


class UGCVideoEditor:
    def __init__(self, output_dir: str = None, theme: str = "default", watermark: str = ""):
        self.output_dir = output_dir or skynet_config.get("paths", "output_dir", default="output/videos")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(self.output_dir) / ".scenes"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.theme = THEMES.get(theme, THEMES["default"])
        self.watermark = watermark
        self._avatar_engine = None
        self._tts = TTSEngine()
        self._font_path = self._find_font()
        self._bgm_path = self._find_bgm()

    def set_theme(self, name: str):
        if name in THEMES:
            self.theme = THEMES[name]

    def render(self, script: str, product_image: str = None, face_image: str = None,
               gender: str = "male", niche: str = "lifestyle", output_path: str = None) -> str:
        """Render full UGC video with 5-scene template.

        Args:
            script: Full script text.
            product_image: Product photo path.
            face_image: Face image for avatar scenes.
            gender: Voice gender.
            niche: Content niche.
            output_path: Output MP4 path. Auto-generated if None.

        Returns:
            Path to final MP4.
        """
        output_path = output_path or self._auto_path()

        segments = self._segment_script(script)
        voiceover = self._generate_voiceover(script, gender)
        duration = self._get_audio_duration(voiceover)

        scenes = self._build_scenes(segments, duration, product_image)

        scene_videos = []
        for i, scene in enumerate(scenes):
            video = self._render_scene(scene, i, face_image, voiceover)
            if video:
                scene_videos.append(video)

        if not scene_videos:
            log.error("No scenes rendered")
            return ""

        self._concat_scenes(scene_videos, voiceover, output_path)
        self._cleanup(scene_videos + [voiceover])
        log.info("Video editor output: %s", output_path)
        return output_path

    def _segment_script(self, script: str) -> list[str]:
        """Split script into 5 logical segments for each scene type."""
        sentences = [s.strip() for s in script.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        total = len(sentences)
        if total <= 1:
            return [script] * 5
        segments = []
        split_points = [
            max(1, int(total * 0.15)),
            max(1, int(total * 0.35)),
            max(1, int(total * 0.60)),
            max(1, int(total * 0.80)),
        ]
        prev = 0
        for sp in split_points:
            seg = ". ".join(sentences[prev:sp]) + "."
            segments.append(seg)
            prev = sp
        seg = ". ".join(sentences[prev:]) + "."
        segments.append(seg)
        return segments[:5]

    def _build_scenes(self, segments: list[str], total_duration: float, product_image: str = None) -> list[Scene]:
        """Build 5 scene objects with timed durations."""
        if len(segments) < 5:
            segments = segments + [segments[-1]] * (5 - len(segments))
        ratios = [0.20, 0.25, 0.25, 0.18, 0.12]
        scenes = []
        for i, seg in enumerate(segments[:5]):
            dur = max(2.0, total_duration * ratios[i])
            scenes.append(Scene(
                scene_type=["hook", "problem", "solution", "testimonial", "cta"][i],
                text=seg,
                duration=dur,
                product_image=product_image,
            ))
        return scenes

    def _render_scene(self, scene: Scene, index: int, face_image: str = None, voiceover: str = None) -> Optional[str]:
        """Render a single scene as MP4 using ffmpeg.

        Scene types:
        - hook: avatar full + hook text
        - problem: PIP avatar + product + problem text
        - solution: product/B-roll + solution text
        - testimonial: avatar full + testimonial text
        - cta: product + CTA text
        """
        out = str(self.temp_dir / f"scene_{index:02d}_{uuid.uuid4().hex[:8]}.mp4")

        base_video = self._get_base_video(scene, index, face_image)
        text_overlay = self._get_text_overlay(scene)

        text_filter = f"drawtext=text='{self._escape_ffmpeg(scene.text)}':fontfile={self._font_path}:fontsize=28:fontcolor={self.theme['text']}:x=(w-text_w)/2:y=h-200:enable='between(t,0,{scene.duration})'"

        cmd = [
            "ffmpeg", "-y",
            "-i", base_video,
            "-vf", f"drawtext=text='{self._escape_ffmpeg(scene.text)}':fontfile={self._font_path}:fontsize=30:fontcolor={self.theme['text']}:x=(w-text_w)/2:y=h*0.75-text_h:shadowcolor=black:shadowx=2:shadowy=2:enable='between(t,0,{scene.duration})'",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            out,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log.warning("Scene %d failed: %s", index, result.stderr[:200])
            return None
        return out

    def _get_base_video(self, scene: Scene, index: int, face_image: str = None) -> str:
        """Generate base video for a scene (avatar clip or static frame)."""
        if face_image and os.path.exists(face_image) and scene.type in ("hook", "testimonial"):
            avatar_path = self._render_avatar(face_image, scene.duration, index)
            if avatar_path:
                return avatar_path
        return self._render_frame_video(scene, face_image)

    def _render_avatar(self, face_image: str, duration: float, scene_idx: int) -> Optional[str]:
        if self._avatar_engine is None:
            self._avatar_engine = AvatarEngine(output_dir=str(self.temp_dir))
        silent_audio = self._generate_silence(duration)
        out = str(self.temp_dir / f"avatar_scene_{scene_idx}_{uuid.uuid4().hex[:8]}.mp4")
        try:
            return self._avatar_engine.generate_avatar(face_image, silent_audio, out)
        except Exception as e:
            log.warning("Avatar scene %d fallback: %s", scene_idx, e)
            return None

    def _render_frame_video(self, scene: Scene, face_image: str = None) -> str:
        """Render a static frame as video segment."""
        frame = self._generate_frame(scene)
        frame_path = str(self.temp_dir / f"frame_{uuid.uuid4().hex[:8]}.png")
        frame.save(frame_path)

        out = str(self.temp_dir / f"base_{uuid.uuid4().hex[:8]}.mp4")
        dur_frames = int(scene.duration * FPS)
        zoom = "min(zoom+0.003,1.1)"

        pip_filter = ""
        if scene.type == "problem" and scene.product_image and os.path.exists(scene.product_image):
            pip_path = self._get_pip_product(scene.product_image)
            if pip_path:
                pip_filter = f"[1:v]scale=iw*0.35:ih*0.35[small];[0:v][small]overlay=W-w-20:20"

        vf = f"zoompan=z='{zoom}':d={dur_frames}:fps={FPS},scale={WIDTH}:{HEIGHT}:flags=lanczos"
        if pip_filter:
            vf = pip_filter

        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", frame_path,
            "-c:v", "libx264", "-t", str(scene.duration),
            "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            "-vf", f"zoompan=z='{zoom}':d={dur_frames}:fps={FPS},scale={WIDTH}:{HEIGHT}:flags=lanczos",
            out,
        ]

        if pip_filter and scene.product_image and os.path.exists(scene.product_image):
            pip_path = self._get_pip_product(scene.product_image)
            cmd = [
                "ffmpeg", "-y", "-loop", "1", "-i", frame_path,
                "-i", pip_path,
                "-filter_complex", f"[1:v]scale=iw*0.35:ih*0.35[small];[0:v]zoompan=z='{zoom}':d={dur_frames}:fps={FPS},scale={WIDTH}:{HEIGHT}:flags=lanczos[bg];[bg][small]overlay=W-w-20:20",
                "-c:v", "libx264", "-t", str(scene.duration),
                "-pix_fmt", "yuv420p", "-preset", "ultrafast",
                out,
            ]

        subprocess.run(cmd, capture_output=True, text=True, check=True)
        os.remove(frame_path)
        return out

    def _get_pip_product(self, product_image: str) -> str:
        """Resize product image for PIP overlay."""
        img = Image.open(product_image).convert("RGBA")
        img.thumbnail((int(WIDTH * 0.35), int(HEIGHT * 0.35)), Image.LANCZOS)
        out = str(self.temp_dir / f"pip_{uuid.uuid4().hex[:8]}.png")
        img.save(out)
        return out

    def _generate_frame(self, scene: Scene) -> Image.Image:
        """Generate a themed background frame for a scene."""
        img = Image.new("RGB", (WIDTH, HEIGHT), self.theme["bg"])
        draw = ImageDraw.Draw(img)

        for y in range(HEIGHT):
            ratio = y / HEIGHT
            r = int(self.theme["bg"][0] * (1 - ratio) + self.theme["accent_rgb"][0] * ratio * 0.25)
            g = int(self.theme["bg"][1] * (1 - ratio) + self.theme["accent_rgb"][1] * ratio * 0.25)
            b = int(self.theme["bg"][2] * (1 - ratio) + self.theme["accent_rgb"][2] * ratio * 0.25)
            draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

        if scene.product_image and os.path.exists(scene.product_image) and scene.type in ("solution", "cta"):
            try:
                prod = Image.open(scene.product_image).convert("RGBA")
                max_s = WIDTH // 2
                prod.thumbnail((max_s, max_s), Image.LANCZOS)
                px = (WIDTH - prod.width) // 2
                py = HEIGHT // 4
                img.paste(prod, (px, py), prod)
            except Exception as e:
                log.warning("Product image failed: %s", e)

        if self.watermark:
            try:
                font = ImageFont.truetype(self._font_path, 20) if self._font_path else ImageFont.load_default()
                draw.text((WIDTH - 150, HEIGHT - 40), self.watermark, fill="white", font=font)
            except Exception:
                pass

        return img

    def _concat_scenes(self, scene_videos: list[str], voiceover: str, output_path: str):
        """Concat all scene videos with voiceover and optional BGM."""
        concat_file = str(self.temp_dir / "concat.txt")
        with open(concat_file, "w") as f:
            for v in scene_videos:
                f.write(f"file '{v}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
            "-i", voiceover,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest",
            output_path,
        ]

        if self._bgm_path and os.path.exists(self._bgm_path):
            bgm_out = str(self.temp_dir / "with_bgm.mp4")
            bgm_dur = self._get_audio_duration(voiceover)
            cmd_bgm = [
                "ffmpeg", "-y", "-i", output_path,
                "-i", self._bgm_path,
                "-filter_complex",
                f"[1:a]volume=0.15,atrim=duration={bgm_dur}[bgm];[0:a][bgm]amix=inputs=2:duration=first",
                "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-shortest",
                bgm_out,
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            subprocess.run(cmd_bgm, capture_output=True, text=True)
            if os.path.exists(bgm_out):
                os.replace(bgm_out, output_path)
                return

        subprocess.run(cmd, capture_output=True, text=True, check=True)

    def _generate_voiceover(self, script: str, gender: str = "male") -> str:
        out = str(self.temp_dir / f"vo_{uuid.uuid4().hex[:8]}.mp3")
        return self._tts.synthesize_sync(script, gender, out)

    def _generate_silence(self, duration: float) -> str:
        out = str(self.temp_dir / f"silence_{uuid.uuid4().hex[:8]}.wav")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"anullsrc=r=24000:cl=mono:d={duration}", out,
        ], capture_output=True, check=True)
        return out

    def _get_text_overlay(self, scene: Scene) -> str:
        """Generate ffmpeg drawtext filter for scene text."""
        text = self._escape_ffmpeg(scene.text)
        return (
            f"drawtext=text='{text}':fontfile={self._font_path}:"
            f"fontsize=30:fontcolor={self.theme['text']}:"
            f"x=(w-text_w)/2:y=h*0.75-text_h:"
            f"shadowcolor=black:shadowx=2:shadowy=2:"
            f"enable='between(t,0,{scene.duration})'"
        )

    def _find_bgm(self) -> Optional[str]:
        candidates = [
            skynet_config.get("paths", "assets_dir", default="assets") + "/bgm.mp3",
            "/home/aer/ugc/ugc_ai_overpower/assets/bgm.mp3",
            "/home/aer/ugc/ugc_ai_overpower/data/bgm.mp3",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def _find_font(self) -> str:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return ""

    def _get_audio_duration(self, audio_path: str) -> float:
        cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
               "-of", "csv=p=0", audio_path]
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(r.stdout.strip())

    @staticmethod
    def _escape_ffmpeg(text: str) -> str:
        return text.replace("'", "'\\\\''").replace(":", "\\:").replace("'", "\\'")[:200]

    def _auto_path(self) -> str:
        return os.path.join(self.output_dir, f"ugc_edit_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}.mp4")

    def _cleanup(self, paths: list[str]):
        for p in paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass

    def batch_render(self, items: list[dict], max_workers: int = 2) -> list[dict]:
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            fut_map = {}
            for item in items:
                fut = pool.submit(
                    self.render,
                    script=item.get("script", ""),
                    product_image=item.get("product_image"),
                    face_image=item.get("face_image"),
                    gender=item.get("gender", "male"),
                    niche=item.get("niche", "lifestyle"),
                    output_path=item.get("output_path"),
                )
                fut_map[fut] = item
            for fut in concurrent.futures.as_completed(fut_map):
                try:
                    path = fut.result()
                    results.append({"path": path, "item": fut_map[fut]})
                except Exception as e:
                    log.warning("Batch item failed: %s", e)
        return results
