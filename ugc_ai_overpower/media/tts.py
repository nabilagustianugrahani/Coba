"""Text‑to‑speech utilities for voiceover generation.

This module wraps **edge‑tts** (Microsoft Edge's TTS engine) and falls back to
**gTTS** (Google Text‑to‑Speech) when the primary engine fails.

Indonesian voice options:

+------------+------------+----------+
| Name       | Voice                     |
+============+============+==========+
| Ardi       | id-ID-ArdiNeural   (male) |
+------------+------------+----------+
| Gadis      | id-ID-GadisNeural  (female)|
+------------+------------+----------+

Usage::

    from ugc_ai_overpower.media.tts import generate_voice

    generate_voice("Halo, selamat datang di review produk ini", voice="id-ID-ArdiNeural")
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Available voices
# ---------------------------------------------------------------------------

INDONESIAN_VOICES = {
    "ardi": "id-ID-ArdiNeural",
    "gadis": "id-ID-GadisNeural",
}

SUPPORTED_VOICES = {
    "id-ID-ArdiNeural": "Indonesian (male)",
    "id-ID-GadisNeural": "Indonesian (female)",
    # Additional common voices (can be extended).
    "en-US-JennyNeural": "English US (female)",
    "en-US-GuyNeural": "English US (male)",
    "en-GB-SoniaNeural": "English UK (female)",
    "en-AU-NatashaNeural": "English AU (female)",
    "ar-SA-ZariyahNeural": "Arabic (female)",
}


# ---------------------------------------------------------------------------
# Primary: edge‑tts
# ---------------------------------------------------------------------------

async def _edge_tts(text: str, voice: str, output: str) -> bool:
    """Run edge‑tts asynchronously.

    Returns ``True`` if the file was written successfully, ``False`` otherwise.
    """
    import edge_tts

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output)
        return os.path.isfile(output) and os.path.getsize(output) > 0
    except Exception as exc:
        log.warning("edge‑tts failed for voice %s: %s", voice, exc)
        return False


# ---------------------------------------------------------------------------
# Fallback: gTTS
# ---------------------------------------------------------------------------

def _gtts(text: str, output: str, lang: str = "id") -> bool:
    """Generate speech via Google TTS (synchronous).

    Returns ``True`` on success.
    """
    from gtts import gTTS

    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(output)
        return os.path.isfile(output) and os.path.getsize(output) > 0
    except Exception as exc:
        log.error("gTTS fallback also failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_voice(
    text: str,
    voice: str = "id-ID-ArdiNeural",
    output: str = "output.mp3",
) -> Optional[str]:
    """Generate a voiceover file from *text*.

    Parameters
    ----------
    text : str
        The text to be spoken.
    voice : str, optional
        The voice identifier (default is ``id-ID-ArdiNeural``).
        See :data:`SUPPORTED_VOICES` for available options or pass any
        valid edge‑tts voice name.
    output : str, optional
        Output file path (default ``output.mp3`` in the current directory).

    Returns
    -------
    str or None
        The absolute path of the generated audio file on success, or ``None``
        when both edge‑tts and the gTTS fallback fail.

    Examples
    --------
    >>> generate_voice("Halo, selamat datang")
    '/home/user/output.mp3'

    >>> generate_voice("Coba suara wanita", voice="id-ID-GadisNeural", output="wanita.mp3")
    '/home/user/wanita.mp3'
    """
    output_path = str(Path(output).resolve())
    log.info("Generating voice: voice=%s output=%s", voice, output_path)

    # Determine language for gTTS fallback based on the voice prefix.
    lang = "id" if voice.startswith("id") else voice[:2].lower()

    # Try edge-tts first.
    success = asyncio.run(_edge_tts(text, voice, output_path))
    if success:
        log.info("Voice generated successfully via edge‑tts")
        return output_path

    # Fallback to gTTS.
    log.info("Falling back to gTTS (lang=%s)…", lang)
    success = _gtts(text, output_path, lang=lang)
    if success:
        log.info("Voice generated successfully via gTTS")
        return output_path

    log.error("All TTS engines failed for text: %.60s", text)
    return None


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------

def batch_generate(
    items: list[tuple[str, str, str]],
) -> list[tuple[str, Optional[str]]]:
    """Generate multiple voice files.

    Each item is a ``(text, voice, output)`` tuple.  The function processes
    them sequentially and returns a list of ``(output_path, abs_path_or_None)``
    pairs.

    Parameters
    ----------
    items : list of (str, str, str)
        ``(text, voice, output_path)`` for each file.

    Returns
    -------
    list of (str, str or None)
    """
    results: list[tuple[str, Optional[str]]] = []
    for text, voice, output in items:
        path = generate_voice(text, voice=voice, output=output)
        results.append((output, path))
    return results
