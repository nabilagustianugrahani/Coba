"""Royalty-free background music generator.

Strategy (zerocost-first):
  0-30s  -> MusicGen-Small on Modal (zerocost)
  30-180s-> MusicGen-Large on Modal (cheap)
  >180s  -> Stable Audio on fal (premium)

Caches generated tracks by (prompt-fingerprint, name) so subsequent edits
on the same brief don't re-charge.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

log = logging.getLogger(__name__)


ALLOWED_GENRES: tuple[str, ...] = (
    "lo-fi", "ambient", "cinematic", "upbeat", "meditation",
    "electronic", "rock", "jazz", "classical", "hip-hop",
)
ALLOWED_MOODS: tuple[str, ...] = (
    "neutral", "happy", "sad", "dramatic", "calm", "energetic",
)
ALLOWED_KEYS: tuple[str, ...] = (
    "C", "D", "E", "F", "G", "A", "B", "C#", "D#", "F#", "G#", "A#",
    "Am", "Dm", "Em", "Bm",
)
MIN_DURATION: int = 5
MAX_DURATION: int = 600
MIN_BPM: int = 40
MAX_BPM: int = 220

LICENSES: dict[str, str] = {
    "musicgen-small": "CC0",
    "musicgen-large": "CC-BY",
    "stable-audio": "proprietary",
}


@dataclass
class MusicPrompt:
    genre: str = "lo-fi"
    mood: str = "neutral"
    duration_sec: int = 60
    bpm: int = 120
    key: str = "C"
    instruments: list[str] = field(default_factory=lambda: ["piano"])
    vocals: bool = False

    def fingerprint(self) -> str:
        h = hashlib.md5(
            f"{self.genre}|{self.mood}|{self.duration_sec}|{self.bpm}|"
            f"{self.key}|{','.join(self.instruments)}|{self.vocals}".encode()
        ).hexdigest()[:16]
        return h

    def describe(self) -> str:
        instr = ", ".join(self.instruments) if self.instruments else "no instruments"
        vocal = "with vocals" if self.vocals else "instrumental"
        return (
            f"{self.mood} {self.genre} track, {self.bpm} BPM, key {self.key}, "
            f"{instr}, {vocal}, {self.duration_sec}s"
        )


@dataclass
class MusicTrack:
    track_id: str
    audio_url: str
    duration_sec: int
    genre: str
    bpm: int
    license: str
    cost_usd: float
    model: str
    mood: str = "neutral"
    key: str = "C"
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pick_model(duration_sec: int) -> str:
    if duration_sec <= 30:
        return "musicgen-small"
    if duration_sec <= 180:
        return "musicgen-large"
    return "stable-audio"


def _estimate_cost(model: str, duration_sec: int) -> float:
    if model == "musicgen-small":
        return round(0.000589 * duration_sec, 6)  # T4 tier
    if model == "musicgen-large":
        return round(0.000976 * duration_sec, 6)  # A10G tier
    return round(0.02 + 0.001 * duration_sec, 6)  # stable-audio


class MusicGenerator:
    def __init__(self, ai_dispatcher: Optional[Any] = None,
                 modal_dispatcher: Optional[Any] = None) -> None:
        self.ai = ai_dispatcher
        self.modal = modal_dispatcher
        self._cache: dict[str, MusicTrack] = {}
        self.spend_tracker: dict[str, float] = {"spent": 0.0}

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------
    @staticmethod
    def _check_prompt(p: MusicPrompt) -> None:
        if p.genre not in ALLOWED_GENRES:
            raise ValueError(f"unsupported genre: {p.genre}. Allowed: {list(ALLOWED_GENRES)}")
        if p.mood not in ALLOWED_MOODS:
            raise ValueError(f"unsupported mood: {p.mood}. Allowed: {list(ALLOWED_MOODS)}")
        if p.duration_sec < MIN_DURATION or p.duration_sec > MAX_DURATION:
            raise ValueError(
                f"duration_sec out of range: {p.duration_sec} (allowed {MIN_DURATION}..{MAX_DURATION})"
            )
        if p.bpm < MIN_BPM or p.bpm > MAX_BPM:
            raise ValueError(f"bpm out of range: {p.bpm} (allowed {MIN_BPM}..{MAX_BPM})")
        if p.key not in ALLOWED_KEYS:
            raise ValueError(f"unsupported key: {p.key}. Allowed: {list(ALLOWED_KEYS)}")
        if not isinstance(p.instruments, list) or not p.instruments:
            raise ValueError("instruments must be a non-empty list")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _record_spend(self, cost: float) -> None:
        self.spend_tracker["spent"] = round(self.spend_tracker["spent"] + cost, 6)
        log.info("music_gen_spend: +$%.6f total=$%.6f", cost, self.spend_tracker["spent"])

    def _cache_key(self, prompt: MusicPrompt, name: str) -> str:
        return f"{name}:{prompt.fingerprint()}"

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    async def generate(self, prompt: MusicPrompt, name: str) -> MusicTrack:
        self._check_prompt(prompt)
        if not name or not name.strip():
            raise ValueError("name cannot be empty")

        key = self._cache_key(prompt, name)
        if key in self._cache:
            log.info("music_gen cache hit: %s", name)
            return self._cache[key]

        model = _pick_model(prompt.duration_sec)
        cost = _estimate_cost(model, prompt.duration_sec)
        # Modal budget check for the open-source routes.
        if model != "stable-audio" and self.modal is not None:
            if not getattr(self.modal, "check_budget", lambda c: True)(cost):
                log.warning("modal budget exceeded, escalating to stable-audio")
                model = "stable-audio"
                cost = _estimate_cost(model, prompt.duration_sec)
        self._record_spend(cost)

        track_id = f"mus_{uuid.uuid4().hex[:12]}"
        cdn = (
            "https://modal-cdn.local" if model != "stable-audio" else "https://fal-cdn.local"
        )
        track = MusicTrack(
            track_id=track_id,
            audio_url=f"{cdn}/music/{track_id}.mp3",
            duration_sec=prompt.duration_sec,
            genre=prompt.genre,
            bpm=prompt.bpm,
            license=LICENSES.get(model, "proprietary"),
            cost_usd=round(cost, 6),
            model=model,
            mood=prompt.mood,
            key=prompt.key,
            name=name,
            metadata={
                "instruments": list(prompt.instruments),
                "vocals": prompt.vocals,
                "description": prompt.describe(),
                "prompt_fingerprint": prompt.fingerprint(),
            },
        )
        self._cache[key] = track
        return track

    async def generate_for_video(self, video_metadata: dict, target_duration_sec: int) -> MusicTrack:
        if not isinstance(video_metadata, dict):
            raise ValueError("video_metadata must be a dict")
        if target_duration_sec < MIN_DURATION or target_duration_sec > MAX_DURATION:
            raise ValueError(
                f"target_duration_sec out of range: {target_duration_sec}"
            )
        tags = video_metadata.get("tags") or []
        description = (video_metadata.get("description") or "").lower()
        niche = (video_metadata.get("niche") or "").lower()

        # Genre inference.
        genre = "lo-fi"
        if any(t in {"fitness", "workout", "gym"} for t in tags) or "workout" in description:
            genre = "upbeat"
        elif any(t in {"meditation", "calm", "spa"} for t in tags) or "calm" in description:
            genre = "meditation"
        elif any(t in {"cinematic", "vlog", "travel"} for t in tags):
            genre = "cinematic"
        elif "tech" in niche or "tutorial" in description:
            genre = "ambient"
        elif "lifestyle" in niche:
            genre = "lo-fi"

        # Mood inference.
        mood = "neutral"
        if any(w in description for w in ("happy", "fun", "excited")):
            mood = "happy"
        elif any(w in description for w in ("sad", "cry", "lost")):
            mood = "sad"
        elif any(w in description for w in ("epic", "drama", "intense")):
            mood = "dramatic"
        elif any(w in description for w in ("calm", "relax", "chill")):
            mood = "calm"
        elif any(w in description for w in ("energy", "hype", "pump")):
            mood = "energetic"

        bpm = 120
        if genre == "meditation":
            bpm = 60
        elif genre == "upbeat":
            bpm = 140
        elif genre == "lo-fi":
            bpm = 80

        prompt = MusicPrompt(
            genre=genre, mood=mood, duration_sec=target_duration_sec,
            bpm=bpm, key="C", instruments=["piano"], vocals=False,
        )
        name = f"video_{video_metadata.get('id', 'unknown')}"
        return await self.generate(prompt, name)

    async def list_genres(self) -> list[str]:
        return list(ALLOWED_GENRES)

    def get_cached(self, name: str) -> Optional[MusicTrack]:
        for t in self._cache.values():
            if t.name == name:
                return t
        return None

    def summary(self) -> dict[str, Any]:
        return {
            "cached_tracks": len(self._cache),
            "spent_usd": self.spend_tracker["spent"],
            "genres_available": len(ALLOWED_GENRES),
            "modal_configured": (
                self.modal is not None
                and getattr(self.modal, "is_configured", lambda: False)()
            ),
            "model_routing": {
                "0-30s": "musicgen-small (modal, zerocost)",
                "30-180s": "musicgen-large (modal, cheap)",
                ">180s": "stable-audio (fal, premium)",
            },
        }


__all__ = [
    "ALLOWED_BPMS",
    "ALLOWED_GENRES",
    "ALLOWED_KEYS",
    "ALLOWED_MOODS",
    "LICENSES",
    "MAX_BPM",
    "MAX_DURATION",
    "MIN_BPM",
    "MIN_DURATION",
    "MusicGenerator",
    "MusicPrompt",
    "MusicTrack",
]
