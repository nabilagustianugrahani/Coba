"""AI Avatar Engine — SoulX-FlashHead via Modal GPU with CPU fallback.

Architecture:
- Uses ModalPipeline.call_avatar() for GPU inference (no code duplication)
- Falls back to static frame + zoompan when GPU unavailable
- Multi-account Modal key rotation built in
- Batch generation via ThreadPoolExecutor
"""
import os, logging, subprocess, uuid, concurrent.futures, base64
from pathlib import Path
from typing import Optional

from ugc_ai_overpower.core.config import skynet_config
from ugc_ai_overpower.gpu.tts_engine import TTSEngine
from ugc_ai_overpower.gpu.modal_pipeline import ModalPipeline

log = logging.getLogger(__name__)


class AvatarEngine:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or skynet_config.get("paths", "output_dir", default="output/avatars")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self._pipeline = ModalPipeline()

    def is_available(self) -> bool:
        return self._pipeline.is_available()

    def generate_avatar(
        self,
        face_image: str,
        audio_path: str,
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """Generate talking-head avatar video from face image + audio.

        Tries Modal GPU first, falls back to static frame + zoompan.
        """
        output_path = output_path or self._auto_path()
        if not os.path.exists(face_image):
            log.error("Face image not found: %s", face_image)
            return None
        if not os.path.exists(audio_path):
            log.error("Audio not found: %s", audio_path)
            return None

        if self._pipeline.is_available():
            try:
                return self._generate_modal(face_image, audio_path, output_path)
            except Exception as e:
                log.warning("Modal avatar failed, falling back: %s", e)

        return self._fallback(face_image, audio_path, output_path)

    def _generate_modal(self, face_image: str, audio_path: str, output_path: str) -> str:
        with open(face_image, "rb") as f:
            face_b64 = base64.b64encode(f.read()).decode()
        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()

        mp4_bytes = self._pipeline.call_avatar(face_b64, audio_b64)
        with open(output_path, "wb") as f:
            f.write(mp4_bytes)
        log.info("Avatar generated via Modal: %s", output_path)
        return output_path

    def _fallback(self, face_image: str, audio_path: str, output_path: str) -> str:
        log.info("Avatar fallback: static frame + zoompan")
        dur = self._get_audio_duration(audio_path)
        frame_path = self._resize_face(face_image)

        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", frame_path,
            "-i", audio_path,
            "-vf", f"zoompan=z='min(zoom+0.002,1.15)':d={int(dur*25)}:fps=25,scale=720:1280:flags=lanczos",
            "-c:v", "libx264", "-c:a", "aac", "-shortest",
            "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if os.path.exists(frame_path):
            os.remove(frame_path)
        log.info("Avatar fallback video: %s", output_path)
        return output_path

    def generate_avatar_sync(
        self,
        script: str,
        face_image: str,
        gender: str = "male",
        output_path: Optional[str] = None,
    ) -> str:
        """Full pipeline: TTS + Avatar in one call."""
        audio = TTSEngine().synthesize_sync(script, gender)
        return self.generate_avatar(face_image, audio, output_path)

    def batch_generate(self, items: list, max_workers: int = 2) -> list:
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            fut_map = {}
            for item in items:
                fut = pool.submit(
                    self.generate_avatar,
                    face_image=item["face_image"],
                    audio_path=item["audio_path"],
                    output_path=item.get("output_path"),
                )
                fut_map[fut] = item
            for fut in concurrent.futures.as_completed(fut_map):
                try:
                    path = fut.result()
                    if path:
                        results.append({"path": path, "item": fut_map[fut]})
                except Exception as e:
                    log.warning("Avatar batch item failed: %s", e)
        return results

    def _resize_face(self, face_image: str) -> str:
        from PIL import Image
        img = Image.open(face_image).convert("RGB")
        img = img.resize((720, 1280), Image.LANCZOS)
        out = os.path.join(self.output_dir, f"face_{uuid.uuid4().hex[:8]}.png")
        img.save(out)
        return out

    def _get_audio_duration(self, audio_path: str) -> float:
        cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
               "-of", "csv=p=0", audio_path]
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(r.stdout.strip())

    def _auto_path(self) -> str:
        return os.path.join(self.output_dir, f"avatar_{uuid.uuid4().hex[:12]}.mp4")
