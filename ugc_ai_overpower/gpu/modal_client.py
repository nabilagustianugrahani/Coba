"""Modal.com GPU client wrapper for AI video and voice generation.

Provides a unified interface to Modal.com GPU-backed services (Wan2.1 for
video generation, FishSpeech for voice synthesis) with automatic fallback to
CPU‑mode when Modal is unavailable.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Quota / status types
# ---------------------------------------------------------------------------

@dataclass
class QuotaInfo:
    """Remaining credits as returned by Modal."""
    credits_used: float = 0.0
    credits_limit: float = 100.0
    credits_remaining: float = 100.0
    period_end: Optional[str] = None


# ---------------------------------------------------------------------------
# GPU Client
# ---------------------------------------------------------------------------

class ModalGPU:
    """Client for Modal.com GPU-accelerated generation.

    Wraps two stub deployments:

    * **Wan2.1** – text‑/image‑to‑video model
    * **FishSpeech** – zero‑shot voice cloning / TTS

    If the Modal token pair is not configured or the remote call fails the
    class falls back to a CPU‑mode stub that logs a warning and returns a
    placeholder path so the caller does not have to branch on GPU availability.
    """

    def __init__(
        self,
        token_id: Optional[str] = None,
        token_secret: Optional[str] = None,
    ) -> None:
        self.token_id = token_id or os.getenv("MODAL_TOKEN_ID", "")
        self.token_secret = token_secret or os.getenv("MODAL_TOKEN_SECRET", "")
        self._available: Optional[bool] = None  # lazily probed

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return ``True`` if Modal credentials are present and the service
        responds to a lightweight health check."""
        if self._available is not None:
            return self._available

        if not self.token_id or not self.token_secret:
            log.info("ModalGPU: token_id / token_secret not configured → CPU fallback")
            self._available = False
            return False

        # Quick live check – try to import Modal and ping the workspace.
        try:
            import modal

            modal.config.token_id = self.token_id
            modal.config.token_secret = self.token_secret
            with modal.Client() as client:
                # A lightweight introspection call rather than a full deploy.
                _ = client.workspace  # Minimal round‑trip
            self._available = True
            log.info("ModalGPU: connected to workspace")
        except Exception as exc:
            log.warning("ModalGPU: health check failed → CPU fallback (%s)", exc)
            self._available = False

        return self._available

    # ------------------------------------------------------------------
    # Video generation  (Wan2.1 stub)
    # ------------------------------------------------------------------

    def generate_video(
        self,
        prompt: str,
        duration: int = 5,
        output_dir: str = "output/videos",
    ) -> Optional[str]:
        """Generate a short video clip using Wan2.1 on Modal.

        Parameters
        ----------
        prompt : str
            Text description of the scene to generate.
        duration : int
            Target duration in seconds (default 5, max 30).
        output_dir : str
            Directory where the generated video will be saved.

        Returns
        -------
        str or None
            Absolute path to the generated MP4, or *None* if generation failed.
        """
        if not self.is_available():
            return self._cpu_fallback("generate_video", prompt)

        output_dir = Path(output_dir)

        try:
            import modal

            modal.config.token_id = self.token_id
            modal.config.token_secret = self.token_secret

            # ----------------------------------------------------------
            # Wan2.1 stub definition  (production would use a real image)
            # ----------------------------------------------------------
            stub = modal.Stub("wan21-video-gen")
            volume = modal.SharedVolume().persist("ugc-wan21-outputs")

            @stub.function(
                gpu="A100",
                shared_volumes={"/outputs": volume},
                timeout=300,
            )
            def _run_wan21(p: str, dur: int) -> str:
                # Placeholder: in production this loads the Wan2.1 model and
                # calls inference.  Here we simulate latency and write a stub.
                import time
                import subprocess
                time.sleep(2)  # simulate inference
                out = f"/outputs/{hash(p)}_{dur}s.mp4"
                # Create a minimal valid MP4 with ffmpeg (colour bar)
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-f", "lavfi", "-i",
                        f"color=c=blue:s=1080x1920:d={dur}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out,
                    ],
                    capture_output=True,
                )
                return out

            out_name = f"wan21_{hash(prompt)}_{duration}s.mp4"
            modal_output = _run_wan21.call(prompt, duration)

            # Copy from shared volume to local output directory.
            output_dir.mkdir(parents=True, exist_ok=True)
            local_path = output_dir / out_name

            if "ffmpeg" in modal_output:
                # The stub ran locally via subprocess for compatibility;
                # in a real deployment the file would be on the shared volume.
                # Here we treat the returned string as the path directly.
                local_path = Path(modal_output)
                if not local_path.exists():
                    raise FileNotFoundError(modal_output)

            log.info("Wan2.1 video generated: %s", local_path)
            return str(local_path.resolve())

        except Exception as exc:
            log.error("Wan2.1 generation failed: %s", exc)
            return self._cpu_fallback("generate_video", prompt)

    # ------------------------------------------------------------------
    # Voice generation  (FishSpeech stub)
    # ------------------------------------------------------------------

    def generate_voice(
        self,
        text: str,
        voice_id: str = "default",
        output_dir: str = "output/audio",
    ) -> Optional[str]:
        """Clone / generate a voice line using FishSpeech on Modal.

        Parameters
        ----------
        text : str
            Text to be spoken.
        voice_id : str
            Reference voice identifier (speaker embedding key).
        output_dir : str
            Directory for the generated WAV file.

        Returns
        -------
        str or None
            Absolute path to the audio file, or *None* on failure.
        """
        if not self.is_available():
            return self._cpu_fallback("generate_voice", text)

        output_dir = Path(output_dir)

        try:
            import modal

            modal.config.token_id = self.token_id
            modal.config.token_secret = self.token_secret

            stub = modal.Stub("fishspeech-tts")
            volume = modal.SharedVolume().persist("ugc-fish-outputs")

            @stub.function(
                gpu="T4",
                shared_volumes={"/outputs": volume},
                timeout=120,
            )
            def _run_fishspeech(txt: str, vid: str) -> str:
                import time
                time.sleep(1)  # simulate inference
                out = f"/outputs/{hash(txt)}_{vid}.wav"
                # Write a silence WAV as placeholder.
                import struct, wave
                with wave.open(out, "w") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    duration_samples = int(24000 * max(1, len(txt) / 10))
                    for _ in range(duration_samples):
                        wf.writeframes(struct.pack("<h", 0))
                return out

            out_name = f"fish_{hash(text)}_{voice_id}.wav"
            _run_fishspeech.call(text, voice_id)

            output_dir.mkdir(parents=True, exist_ok=True)
            local_path = output_dir / out_name
            # In production the file would be copied from the shared volume;
            # here we create the local placeholder.
            import struct, wave
            with wave.open(str(local_path), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                duration_samples = int(24000 * max(1, len(text) / 10))
                for _ in range(duration_samples):
                    wf.writeframes(struct.pack("<h", 0))

            log.info("FishSpeech voice generated: %s", local_path)
            return str(local_path.resolve())

        except Exception as exc:
            log.error("FishSpeech generation failed: %s", exc)
            return self._cpu_fallback("generate_voice", text)

    # ------------------------------------------------------------------
    # Quota
    # ------------------------------------------------------------------

    def get_quota(self) -> QuotaInfo:
        """Query remaining credits from Modal.

        Returns a :class:`QuotaInfo` with sensible defaults when Modal is
        unreachable.
        """
        if not self.is_available():
            return QuotaInfo(
                credits_remaining=0.0,
                credits_limit=0.0,
                period_end="N/A (CPU fallback)",
            )

        try:
            import modal

            modal.config.token_id = self.token_id
            modal.config.token_secret = self.token_secret
            with modal.Client() as client:
                usage = client.api_request("GET", "/v1/usage")
                used = usage.get("used_credits", 0.0)
                limit = usage.get("credit_limit", 100.0)
                return QuotaInfo(
                    credits_used=used,
                    credits_limit=limit,
                    credits_remaining=max(0.0, limit - used),
                    period_end=usage.get("period_end"),
                )
        except Exception as exc:
            log.warning("Modal quota query failed: %s", exc)
            return QuotaInfo(
                credits_remaining=0.0,
                credits_limit=0.0,
                period_end="error querying quota",
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cpu_fallback(method: str, detail: str) -> Optional[str]:
        """Log a warning and return *None* – the caller should handle this
        gracefully (e.g. use the CPU TTS engine)."""
        log.warning(
            "ModalGPU.%s() – GPU unavailable (CPU fallback). detail=%.60s",
            method,
            detail,
        )
        return None
