"""Enterprise TTS engine — edge-tts with Indonesian voices."""
import asyncio, os, logging, tempfile
from pathlib import Path
from typing import Optional

from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)


class TTSEngine:
    """Text-to-speech pipeline using edge-tts (free, natural voices).

    Supports Indonesian male/female voices. Generates WAV ready for
    video compositing.
    """

    VOICE_MAP = {
        "male": "id-ID-ArdiNeural",
        "female": "id-ID-GadisNeural",
    }

    def __init__(self, voice: str = None, voice_female: str = None):
        cfg = skynet_config
        self.voice_male = voice or cfg.get("tts", "voice_id", default="id-ID-ArdiNeural")
        self.voice_female = voice_female or cfg.get("tts", "voice_id_female", default="id-ID-GadisNeural")

    async def synthesize(self, text: str, gender: str = "male", output_path: str = None) -> str:
        """Generate voiceover audio from text.

        Args:
            text: Script/transcript to speak.
            gender: 'male' or 'female'.
            output_path: Where to save the audio. Auto-generated if None.

        Returns:
            Path to the generated audio file (WAV/MP3).
        """
        output_path = output_path or self._temp_path()
        voice = self.VOICE_MAP.get(gender, self.voice_male)

        from edge_tts import Communicate
        communicate = Communicate(text, voice)
        await communicate.save(output_path)

        log.info("TTS generated: %s (%.1fs text, gender=%s)",
                 output_path, len(text) / 15, gender)
        return output_path

    def synthesize_sync(self, text: str, gender: str = "male", output_path: str = None) -> str:
        """Synchronous wrapper for synthesize()."""
        return asyncio.run(self.synthesize(text, gender, output_path))

    @staticmethod
    def _temp_path() -> str:
        d = Path(skynet_config.get("paths", "output_dir", default="/tmp")) / "tts"
        d.mkdir(parents=True, exist_ok=True)
        import uuid
        return str(d / f"voice_{uuid.uuid4().hex[:8]}.mp3")

    @staticmethod
    def list_voices():
        """Return available Indonesian voices."""
        try:
            import edge_tts
            voices = asyncio.run(
                edge_tts.list_voices()
            )
            return [
                {"name": v["ShortName"], "locale": v["Locale"], "gender": v["Gender"]}
                for v in voices if v["Locale"].startswith("id")
            ]
        except Exception as e:
            log.warning("Failed to list voices: %s", e)
            return [
                {"name": "id-ID-ArdiNeural", "locale": "id-ID", "gender": "Male"},
                {"name": "id-ID-GadisNeural", "locale": "id-ID", "gender": "Female"},
            ]
