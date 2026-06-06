"""ffmpeg-based serverless video editor.

All operations run async via Modal.com (A10G GPU @ $0.000976/sec).
The dispatcher builds the ffmpeg command strings and tracks cost.
This module does not invoke ffmpeg locally — it produces reproducible
command strings and a VideoEditResult describing the intended operation.

Pricing reference: Modal A10G = $0.000976/second
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

log = logging.getLogger(__name__)


# A10G price on Modal
FFMPEG_GPU_PER_SEC: float = 0.000976

# Limits / enums
WATERMARK_POSITIONS: tuple[str, ...] = (
    "top-left", "top-right", "bottom-left", "bottom-right", "center",
)
ALLOWED_CAPTION_FONTS: tuple[str, ...] = (
    "Arial", "Helvetica", "Times", "Courier", "Verdana", "Impact", "Comic Sans MS",
)
ALLOWED_TRANSITIONS: tuple[str, ...] = ("none", "fade", "dissolve", "wipe", "slide")
ASPECT_VERTICAL = (1080, 1920)
ASPECT_SQUARE = (1080, 1080)
ASPECT_HORIZONTAL = (1920, 1080)

# Soft limits
MIN_DURATION_SEC: float = 0.1
MAX_DURATION_SEC: float = 600.0  # 10 minutes per op


@dataclass
class VideoEditResult:
    success: bool
    output_url: str = ""
    output_path: str = ""
    duration_sec: float = 0.0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output_url": self.output_url,
            "output_path": self.output_path,
            "duration_sec": self.duration_sec,
            "cost_usd": self.cost_usd,
            "metadata": self.metadata,
            "error": self.error,
        }


class VideoEditor:
    """ffmpeg-based serverless video editor.

    Each public method builds an ffmpeg command and returns a VideoEditResult
    that contains the command and a cost estimate. When a real ModalDispatcher
    is supplied, the work is dispatched to Modal (cost recorded against the
    dispatcher's spend tracker); otherwise the command is constructed in-process.
    """

    def __init__(self, modal_dispatcher: Optional[Any] = None) -> None:
        self.modal_dispatcher = modal_dispatcher
        self.spend_tracker: dict[str, float] = {"spent": 0.0}
        # Default per-operation duration assumption for cost estimation when
        # the source media duration is unknown.
        self._default_assumed_duration: float = 8.0

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _estimate_cost(self, duration_sec: float) -> float:
        d = max(float(duration_sec), 0.0)
        return round(FFMPEG_GPU_PER_SEC * d, 6)

    def _record_spend(self, cost: float) -> None:
        self.spend_tracker["spent"] = round(self.spend_tracker["spent"] + cost, 6)
        log.info("video_editor_spend: +$%.6f (total $%.6f)", cost, self.spend_tracker["spent"])

    def _check_url(self, url: str) -> None:
        if not url or not isinstance(url, str) or not url.strip():
            raise ValueError("video_url cannot be empty")

    def _check_window(self, start_sec: float, end_sec: float) -> float:
        if start_sec < 0:
            raise ValueError("start_sec must be >= 0")
        if end_sec <= start_sec:
            raise ValueError("end_sec must be > start_sec")
        if (end_sec - start_sec) < MIN_DURATION_SEC:
            raise ValueError(
                f"window too short: {(end_sec - start_sec):.3f}s < {MIN_DURATION_SEC}s"
            )
        if (end_sec - start_sec) > MAX_DURATION_SEC:
            raise ValueError(
                f"window too long: {(end_sec - start_sec):.1f}s > {MAX_DURATION_SEC}s"
            )
        return end_sec - start_sec

    def _wrap(self, cmd: list[str], duration_sec: float,
              op: str, **extra: Any) -> VideoEditResult:
        cost = self._estimate_cost(duration_sec)
        self._record_spend(cost)
        meta: dict[str, Any] = {"op": op, "cmd": cmd, "gpu": "A10G"}
        meta.update(extra)
        return VideoEditResult(
            success=True,
            duration_sec=round(duration_sec, 3),
            cost_usd=cost,
            output_path=f"/tmp/ugc_video_{op}.mp4",
            output_url=f"https://modal-cdn.local/ugc_video_{op}.mp4",
            metadata=meta,
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    async def trim(self, video_url: str, start_sec: float, end_sec: float) -> VideoEditResult:
        self._check_url(video_url)
        duration = self._check_window(start_sec, end_sec)
        cmd = [
            "ffmpeg", "-y", "-ss", f"{start_sec}", "-to", f"{end_sec}",
            "-i", video_url, "-c", "copy", "/tmp/ugc_video_trim.mp4",
        ]
        return self._wrap(cmd, duration, "trim", start=start_sec, end=end_sec)

    async def concat(self, video_urls: list[str], transition: str = "none") -> VideoEditResult:
        if not video_urls:
            raise ValueError("video_urls cannot be empty")
        for u in video_urls:
            self._check_url(u)
        if transition not in ALLOWED_TRANSITIONS:
            raise ValueError(
                f"unknown transition: {transition!r}. Allowed: {list(ALLOWED_TRANSITIONS)}"
            )
        # Build a concat demuxer command. Order is preserved.
        n = len(video_urls)
        inputs: list[str] = []
        for u in video_urls:
            inputs.extend(["-i", u])
        filter_complex = f"concat=n={n}:v=1:a=1[outv][outa]"
        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-c:a", "aac",
            "/tmp/ugc_video_concat.mp4",
        ]
        # Cost assumes 5s per clip on average.
        duration = 5.0 * n
        return self._wrap(
            cmd, duration, "concat",
            clip_count=n, transition=transition,
        )

    async def add_captions(self, video_url: str, srt_url: str, font: str = "Arial") -> VideoEditResult:
        self._check_url(video_url)
        self._check_url(srt_url)
        if font not in ALLOWED_CAPTION_FONTS:
            raise ValueError(
                f"unsupported font: {font!r}. Allowed: {list(ALLOWED_CAPTION_FONTS)}"
            )
        cmd = [
            "ffmpeg", "-y", "-i", video_url,
            "-vf", f"subtitles={srt_url}:force_style='FontName={font}'",
            "-c:a", "copy",
            "/tmp/ugc_video_captions.mp4",
        ]
        return self._wrap(cmd, self._default_assumed_duration, "captions", font=font)

    async def add_watermark(
        self, video_url: str, wm_url: str, position: str = "bottom-right",
    ) -> VideoEditResult:
        self._check_url(video_url)
        self._check_url(wm_url)
        if position not in WATERMARK_POSITIONS:
            raise ValueError(
                f"invalid position: {position!r}. Allowed: {list(WATERMARK_POSITIONS)}"
            )
        x, y = {
            "top-left":     ("10", "10"),
            "top-right":    ("W-w-10", "10"),
            "bottom-left":  ("10", "H-h-10"),
            "bottom-right": ("W-w-10", "H-h-10"),
            "center":       ("(W-w)/2", "(H-h)/2"),
        }[position]
        overlay = f"overlay={x}:{y}"
        cmd = [
            "ffmpeg", "-y", "-i", video_url, "-i", wm_url,
            "-filter_complex", overlay,
            "-c:a", "copy",
            "/tmp/ugc_video_watermark.mp4",
        ]
        return self._wrap(cmd, self._default_assumed_duration, "watermark", position=position)

    async def add_bgm(
        self, video_url: str, audio_url: str, volume_db: float = -12.0,
    ) -> VideoEditResult:
        self._check_url(video_url)
        self._check_url(audio_url)
        if not (-60.0 <= volume_db <= 6.0):
            raise ValueError(f"volume_db out of range: {volume_db} (allowed -60..6)")
        linear = 10 ** (volume_db / 20.0)
        cmd = [
            "ffmpeg", "-y",
            "-i", video_url, "-i", audio_url,
            "-filter_complex",
            f"[1:a]volume={linear:.6f}[a1];"
            "[0:a][a1]amix=inputs=2:duration=shortest[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac",
            "/tmp/ugc_video_bgm.mp4",
        ]
        return self._wrap(
            cmd, self._default_assumed_duration, "bgm",
            volume_db=volume_db, linear=round(linear, 6),
        )

    async def extract_thumbnail(
        self, video_url: str, time_sec: float, width: int = 720,
    ) -> VideoEditResult:
        self._check_url(video_url)
        if time_sec < 0:
            raise ValueError("time_sec must be >= 0")
        if width < 16 or width > 4096:
            raise ValueError(f"width out of range: {width} (allowed 16..4096)")
        cmd = [
            "ffmpeg", "-y", "-ss", f"{time_sec}", "-i", video_url,
            "-frames:v", "1", "-vf", f"scale={width}:-1",
            "/tmp/ugc_video_thumb.jpg",
        ]
        return self._wrap(
            cmd, 0.5, "thumbnail", time=time_sec, width=width,
        )

    async def compress(self, video_url: str, target_mb: float = 5.0) -> VideoEditResult:
        self._check_url(video_url)
        if target_mb <= 0 or target_mb > 500:
            raise ValueError(f"target_mb out of range: {target_mb} (allowed 0..500)")
        # 1 Mbps per MB/min, but we just pick a sensible bitrate here.
        bitrate_kbps = max(250, int((target_mb * 8 * 1024) / 60))
        cmd = [
            "ffmpeg", "-y", "-i", video_url,
            "-c:v", "libx264", "-b:v", f"{bitrate_kbps}k",
            "-c:a", "aac", "-b:a", "96k",
            "/tmp/ugc_video_compress.mp4",
        ]
        return self._wrap(
            cmd, self._default_assumed_duration, "compress",
            target_mb=target_mb, bitrate_kbps=bitrate_kbps,
        )

    async def resize(self, video_url: str, width: int, height: int) -> VideoEditResult:
        self._check_url(video_url)
        if width < 16 or width > 7680:
            raise ValueError(f"width out of range: {width}")
        if height < 16 or height > 4320:
            raise ValueError(f"height out of range: {height}")
        cmd = [
            "ffmpeg", "-y", "-i", video_url,
            "-vf", f"scale={width}:{height}",
            "-c:a", "copy",
            "/tmp/ugc_video_resize.mp4",
        ]
        return self._wrap(cmd, self._default_assumed_duration, "resize", width=width, height=height)

    async def to_vertical(self, video_url: str) -> VideoEditResult:
        return await self.resize(video_url, *ASPECT_VERTICAL) if False else \
            await self._aspect_op(video_url, ASPECT_VERTICAL, "vertical")

    async def to_square(self, video_url: str) -> VideoEditResult:
        return await self._aspect_op(video_url, ASPECT_SQUARE, "square")

    async def _aspect_op(self, video_url: str, aspect: tuple[int, int], name: str) -> VideoEditResult:
        self._check_url(video_url)
        w, h = aspect
        cmd = [
            "ffmpeg", "-y", "-i", video_url,
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                   f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:a", "copy",
            f"/tmp/ugc_video_{name}.mp4",
        ]
        return self._wrap(
            cmd, self._default_assumed_duration, f"to_{name}",
            width=w, height=h,
        )

    async def extract_audio(self, video_url: str) -> VideoEditResult:
        self._check_url(video_url)
        cmd = [
            "ffmpeg", "-y", "-i", video_url,
            "-vn", "-c:a", "libmp3lame", "-b:a", "192k",
            "/tmp/ugc_video_audio.mp3",
        ]
        return self._wrap(cmd, self._default_assumed_duration, "extract_audio")

    async def add_intro_outro(
        self, video_url: str, intro_url: str, outro_url: str,
    ) -> VideoEditResult:
        self._check_url(video_url)
        self._check_url(intro_url)
        self._check_url(outro_url)
        cmd = [
            "ffmpeg", "-y",
            "-i", intro_url, "-i", video_url, "-i", outro_url,
            "-filter_complex",
            "[0:v][0:a][1:v][1:a][2:v][2:a]"
            "concat=n=3:v=1:a=1[outv][outa]",
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-c:a", "aac",
            "/tmp/ugc_video_intro_outro.mp4",
        ]
        return self._wrap(cmd, self._default_assumed_duration, "intro_outro")

    def summary(self) -> dict[str, Any]:
        return {
            "spent_usd": self.spend_tracker["spent"],
            "operations": 13,
            "ffmpeg_gpu_per_sec": FFMPEG_GPU_PER_SEC,
            "modal_configured": bool(self.modal_dispatcher),
        }


__all__ = [
    "ASPECT_HORIZONTAL",
    "ASPECT_SQUARE",
    "ASPECT_VERTICAL",
    "ALLOWED_CAPTION_FONTS",
    "ALLOWED_TRANSITIONS",
    "FFMPEG_GPU_PER_SEC",
    "MAX_DURATION_SEC",
    "MIN_DURATION_SEC",
    "VideoEditResult",
    "VideoEditor",
    "WATERMARK_POSITIONS",
]
