"""Audio-first UGC: podcast creation utilities.

Operations:
  - transcribe (Whisper / faster-whisper on Modal)
  - generate shownotes
  - find viral moments (lexicon-based sentiment + pause density)
  - clip audio, intro/outro, normalize loudness, detect silence, merge clips

All methods are async. ffmpeg commands are built but not executed locally.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

log = logging.getLogger(__name__)


# Pricing
TRANSCRIBE_GPU_PER_SEC: float = 0.000589   # T4
AUDIO_EDIT_GPU_PER_SEC: float = 0.000976  # A10G

# Loudness bounds (LUFS, broadcast standards)
LOUDNESS_MIN_LUFS: float = -24.0
LOUDNESS_MAX_LUFS: float = -14.0
LOUDNESS_DEFAULT_LUFS: float = -16.0

# Shownotes cap
SHOWNOTES_MAX_WORDS: int = 500

# Sentiment lexicons (very small, intentionally lightweight)
POSITIVE_WORDS: set[str] = {
    "amazing", "awesome", "brilliant", "incredible", "fantastic", "wonderful",
    "love", "loved", "loving", "great", "best", "win", "winning", "wow",
    "beautiful", "perfect", "happy", "joy", "excited", "exciting", "epic",
    "insane", "crazy", "wild", "fire", "goat", "legendary", "iconic",
}
NEGATIVE_WORDS: set[str] = {
    "bad", "worst", "hate", "hated", "terrible", "awful", "horrible",
    "boring", "ugly", "sad", "angry", "broken", "fail", "failed", "failing",
    "sucks", "trash", "garbage", "lame", "weak", "cringe", "mid", "flop",
}

# Common English stopwords used to filter word counts.
_STOPWORDS: set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this",
    "to", "was", "were", "will", "with", "i", "you", "we", "they", "he",
    "she", "them", "our", "your", "my", "me", "us", "but", "not", "no",
}


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: str = ""
    confidence: float = 0.0

    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def word_count(self) -> int:
        return len([w for w in re.findall(r"\b\w+\b", self.text)])


@dataclass
class TranscriptResult:
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = ""
    duration_sec: float = 0.0
    cost_usd: float = 0.0
    error: str = ""

    def full_text(self) -> str:
        return " ".join(seg.text for seg in self.segments)

    def word_count(self) -> int:
        return sum(seg.word_count() for seg in self.segments)


@dataclass
class ViralMoment:
    start: float
    end: float
    text: str
    score: float
    reason: str


@dataclass
class AudioResult:
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


class PodcastCreator:
    """Audio-first UGC engine: transcription, shownotes, viral detection, ffmpeg audio ops."""

    def __init__(
        self,
        modal_dispatcher: Optional[Any] = None,
        fal_dispatcher: Optional[Any] = None,
    ) -> None:
        self.modal_dispatcher = modal_dispatcher
        self.fal_dispatcher = fal_dispatcher
        self.spend_tracker: dict[str, float] = {"spent": 0.0}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _check_url(self, url: str) -> None:
        if not url or not isinstance(url, str) or not url.strip():
            raise ValueError("audio_url cannot be empty")

    def _record_spend(self, cost: float, gpu: str = "T4") -> None:
        self.spend_tracker["spent"] = round(self.spend_tracker["spent"] + cost, 6)
        log.info(
            "podcast_spend: +$%.6f (gpu=%s total $%.6f)",
            cost, gpu, self.spend_tracker["spent"],
        )

    def _wrap_audio(
        self, cmd: list[str], duration_sec: float, op: str, **extra: Any,
    ) -> AudioResult:
        cost = round(AUDIO_EDIT_GPU_PER_SEC * max(0.0, duration_sec), 6)
        self._record_spend(cost, "A10G")
        meta: dict[str, Any] = {"op": op, "cmd": cmd, "gpu": "A10G"}
        meta.update(extra)
        return AudioResult(
            success=True,
            duration_sec=round(duration_sec, 3),
            cost_usd=cost,
            output_path=f"/tmp/ugc_audio_{op}.mp3",
            output_url=f"https://modal-cdn.local/ugc_audio_{op}.mp3",
            metadata=meta,
        )

    @staticmethod
    def _sentiment_counts(text: str) -> tuple[int, int]:
        words = [w.lower() for w in re.findall(r"\b\w+\b", text)]
        pos = sum(1 for w in words if w in POSITIVE_WORDS)
        neg = sum(1 for w in words if w in NEGATIVE_WORDS)
        return pos, neg

    @staticmethod
    def _is_meaningful_word(w: str) -> bool:
        return len(w) > 2 and w.lower() not in _STOPWORDS

    # ------------------------------------------------------------------
    # transcription
    # ------------------------------------------------------------------
    async def transcribe(self, audio_url: str, language: str = "auto") -> TranscriptResult:
        self._check_url(audio_url)
        if language and language != "auto":
            if not re.match(r"^[a-z]{2,3}$", language):
                raise ValueError(f"invalid language code: {language!r}")
        # Cost = T4 GPU * duration (assume 60s if unknown).
        assumed = 60.0
        cost = round(TRANSCRIBE_GPU_PER_SEC * assumed, 6)
        self._record_spend(cost, "T4")
        # In a real implementation, the dispatcher's transcription job
        # would return segments. We surface the API shape here.
        meta: dict[str, Any] = {
            "model": "whisper-large-v3",
            "gpu": "T4",
            "cmd": ["whisper", audio_url, "--language", language or "auto"],
        }
        return TranscriptResult(
            language=language or "en",
            duration_sec=assumed,
            cost_usd=cost,
            segments=[],
            error="",
        ) if False else TranscriptResult(
            language=language or "en",
            duration_sec=assumed,
            cost_usd=cost,
            segments=[],
        )

    # ------------------------------------------------------------------
    # shownotes
    # ------------------------------------------------------------------
    async def generate_shownotes(self, transcript: TranscriptResult) -> str:
        if transcript is None:
            raise ValueError("transcript cannot be None")
        text = transcript.full_text().strip()
        if not text:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        # Take the most "informative" first 5 sentences (longer = more dense).
        ranked = sorted(sentences, key=lambda s: len(s), reverse=True)[:5]
        bullets = []
        for s in ranked:
            s = s.strip()
            if not s:
                continue
            if len(s) > 200:
                s = s[:197].rstrip() + "..."
            bullets.append(f"- {s}")
        header = (
            f"# Episode notes ({transcript.language or 'en'})\n"
            f"Duration: {transcript.duration_sec:.1f}s — "
            f"Words: {transcript.word_count()}\n\n"
        )
        body = "## Highlights\n" + "\n".join(bullets)
        out = header + body
        words = out.split()
        if len(words) > SHOWNOTES_MAX_WORDS:
            out = " ".join(words[:SHOWNOTES_MAX_WORDS])
        return out

    # ------------------------------------------------------------------
    # viral moment detection
    # ------------------------------------------------------------------
    async def find_viral_moments(
        self, transcript: TranscriptResult, top_k: int = 5,
    ) -> list[ViralMoment]:
        if transcript is None:
            raise ValueError("transcript cannot be None")
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if not transcript.segments:
            return []
        total = transcript.duration_sec or sum(s.duration() for s in transcript.segments) or 1.0
        scored: list[ViralMoment] = []
        for seg in transcript.segments:
            pos, neg = self._sentiment_counts(seg.text)
            wc = max(seg.word_count(), 1)
            sentiment_score = abs(pos - neg) / wc
            # Pause density: assume segments longer than 8s have a higher
            # chance of pause (this is a rough heuristic without actual audio).
            pause_density = min(seg.duration() / 8.0, 1.0)
            combined = (sentiment_score * 0.7) + (pause_density * 0.3)
            reason_parts = []
            if pos > neg:
                reason_parts.append(f"positive spike ({pos} pos)")
            elif neg > pos:
                reason_parts.append(f"negative spike ({neg} neg)")
            if pause_density > 0.5:
                reason_parts.append("slow pacing")
            reason = ", ".join(reason_parts) or "neutral"
            scored.append(ViralMoment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                score=round(combined, 4),
                reason=reason,
            ))
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # audio operations
    # ------------------------------------------------------------------
    async def clip_audio(self, audio_url: str, start: float, end: float) -> AudioResult:
        self._check_url(audio_url)
        if start < 0:
            raise ValueError("start must be >= 0")
        if end <= start:
            raise ValueError("end must be > start")
        duration = end - start
        cmd = [
            "ffmpeg", "-y", "-ss", f"{start}", "-to", f"{end}",
            "-i", audio_url, "-c", "copy",
            "/tmp/ugc_audio_clip.mp3",
        ]
        return self._wrap_audio(cmd, duration, "clip", start=start, end=end)

    async def add_intro_outro(
        self, audio_url: str, intro_url: str, outro_url: str,
    ) -> AudioResult:
        self._check_url(audio_url)
        self._check_url(intro_url)
        self._check_url(outro_url)
        cmd = [
            "ffmpeg", "-y",
            "-i", intro_url, "-i", audio_url, "-i", outro_url,
            "-filter_complex",
            "[0:a][1:a][2:a]concat=n=3:v=0:a=1[aout]",
            "-map", "[aout]", "-c:a", "libmp3lame", "-b:a", "192k",
            "/tmp/ugc_audio_intro_outro.mp3",
        ]
        return self._wrap_audio(cmd, 60.0, "intro_outro")

    async def normalize_loudness(
        self, audio_url: str, target_lufs: float = -16.0,
    ) -> AudioResult:
        self._check_url(audio_url)
        if not (LOUDNESS_MIN_LUFS <= target_lufs <= LOUDNESS_MAX_LUFS):
            raise ValueError(
                f"target_lufs {target_lufs} outside broadcast range "
                f"[{LOUDNESS_MIN_LUFS}, {LOUDNESS_MAX_LUFS}]"
            )
        cmd = [
            "ffmpeg", "-y", "-i", audio_url,
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
            "-c:a", "libmp3lame", "-b:a", "192k",
            "/tmp/ugc_audio_normalized.mp3",
        ]
        return self._wrap_audio(cmd, 60.0, "normalize", target_lufs=target_lufs)

    async def detect_silence(
        self, audio_url: str, threshold_db: float = -40.0,
    ) -> list[tuple[float, float]]:
        self._check_url(audio_url)
        if not (-80.0 <= threshold_db <= 0.0):
            raise ValueError(
                f"threshold_db {threshold_db} out of range [-80, 0]"
            )
        # Surface the ffmpeg silencedetect command. The actual detection
        # output is parsed by the dispatcher; here we return a list of
        # silent windows using the metadata pattern.
        cmd = [
            "ffmpeg", "-i", audio_url,
            "-af", f"silencedetect=noise={threshold_db}dB:d=0.5",
            "-f", "null", "-",
        ]
        cost = round(AUDIO_EDIT_GPU_PER_SEC * 30.0, 6)
        self._record_spend(cost, "A10G")
        log.info("podcast.detect_silence cmd=%s", cmd)
        # Without a parsed output, return an empty list (the dispatcher
        # is responsible for filling this in when running for real).
        return []

    async def merge_clips(
        self, audio_urls: list[str], crossfade_sec: float = 0.5,
    ) -> AudioResult:
        if not audio_urls:
            raise ValueError("audio_urls cannot be empty")
        for u in audio_urls:
            self._check_url(u)
        if crossfade_sec < 0 or crossfade_sec > 10.0:
            raise ValueError(f"crossfade_sec {crossfade_sec} out of range [0, 10]")
        n = len(audio_urls)
        inputs: list[str] = []
        for u in audio_urls:
            inputs.extend(["-i", u])
        # Simple concat (no crossfade applied — crossfade is captured in
        # metadata for the dispatcher to apply with acrossfade filter).
        filter_complex = f"concat=n={n}:v=0:a=1[aout]"
        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-c:a", "libmp3lame", "-b:a", "192k",
            "/tmp/ugc_audio_merge.mp3",
        ]
        duration = 30.0 * n
        return self._wrap_audio(
            cmd, duration, "merge",
            clip_count=n, crossfade_sec=crossfade_sec,
        )

    def summary(self) -> dict[str, Any]:
        return {
            "spent_usd": self.spend_tracker["spent"],
            "transcribe_gpu_per_sec": TRANSCRIBE_GPU_PER_SEC,
            "audio_edit_gpu_per_sec": AUDIO_EDIT_GPU_PER_SEC,
            "modal_configured": bool(self.modal_dispatcher),
            "fal_configured": bool(self.fal_dispatcher),
        }


__all__ = [
    "AUDIO_EDIT_GPU_PER_SEC",
    "AudioResult",
    "LOUDNESS_DEFAULT_LUFS",
    "LOUDNESS_MAX_LUFS",
    "LOUDNESS_MIN_LUFS",
    "NEGATIVE_WORDS",
    "POSITIVE_WORDS",
    "PodcastCreator",
    "SHOWNOTES_MAX_WORDS",
    "TRANSCRIBE_GPU_PER_SEC",
    "TranscriptResult",
    "TranscriptSegment",
    "ViralMoment",
]
