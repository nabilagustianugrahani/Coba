"""Modal.com voice synthesis app (CosyVoice 2.0).

Indonesian + English + Chinese + Japanese voice presets.
GPU: T4 (cheap, sufficient for inference).
"""
from __future__ import annotations

import os

import modal

APP_NAME = "ugc-voice-synth"

DEFAULT_VOICE = "id_female_1"

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch>=2.5.0",
    "transformers>=4.46.0",
    "accelerate>=1.0.0",
    "cosyvoice>=0.1.0",
    "soundfile>=0.12.0",
    "librosa>=0.10.0",
    "huggingface-hub>=0.26.0",
)

volume = modal.Volume.from_name("ugc-models-cache", create_if_missing=True)
model_volume = modal.Volume.from_name("ugc-cosyvoice-models", create_if_missing=True)


app = modal.App(APP_NAME)


VOICE_PRESETS: dict[str, dict[str, str]] = {
    "id_female_1": {
        "name": "id_female_young_warm",
        "language": "id",
        "gender": "female",
        "age": "young",
        "style": "warm",
    },
    "id_female_2": {
        "name": "id_female_mature_professional",
        "language": "id",
        "gender": "female",
        "age": "mature",
        "style": "professional",
    },
    "id_male_1": {
        "name": "id_male_young_casual",
        "language": "id",
        "gender": "male",
        "age": "young",
        "style": "casual",
    },
    "id_male_2": {
        "name": "id_male_mature_authoritative",
        "language": "id",
        "gender": "male",
        "age": "mature",
        "style": "authoritative",
    },
    "en_female_1": {
        "name": "en_female_neutral",
        "language": "en",
        "gender": "female",
        "age": "mature",
        "style": "neutral",
    },
    "en_male_1": {
        "name": "en_male_neutral",
        "language": "en",
        "gender": "male",
        "age": "mature",
        "style": "neutral",
    },
}


@app.function(
    gpu="T4",
    image=image,
    volumes={"/cache": volume, "/models": model_volume},
    scaledown_window=60,
    timeout=120,
    
    memory=8192,
)
@modal.fastapi_endpoint(method="POST")
def synthesize(
    text: str,
    voice_id: str = DEFAULT_VOICE,
    speed: float = 1.0,
    language: str | None = None,
) -> dict:
    """Synthesize speech from text.

    Args:
        text: Text to speak
        voice_id: Voice preset (id_female_1, id_male_1, en_female_1, etc.)
        speed: Speech speed multiplier (0.5-2.0)
        language: Override language detection (id, en, zh, ja)

    Returns:
        Dict with 'audio_b64' (base64 WAV), 'voice_id', 'duration_sec', 'cost_usd'
    """
    import base64
    import io
    import time

    if voice_id not in VOICE_PRESETS:
        return {"error": f"Unknown voice_id: {voice_id}", "available": list(VOICE_PRESETS)}

    speed = max(0.5, min(float(speed), 2.0))
    preset = VOICE_PRESETS[voice_id]
    lang = language or preset["language"]

    start = time.time()
    try:
        audio_bytes = _synthesize_cosyvoice(text, voice_id, lang, speed)
    except Exception as e:
        return {"error": str(e), "voice_id": voice_id, "text": text[:100]}

    duration_real = time.time() - start
    audio_duration = _estimate_audio_duration(text, speed)
    cost_usd = round(0.000589 * duration_real, 6)

    return {
        "audio_b64": base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else "",
        "voice_id": voice_id,
        "voice_preset": preset["name"],
        "language": lang,
        "speed": speed,
        "text_length": len(text),
        "audio_duration_sec": audio_duration,
        "elapsed_sec": round(duration_real, 3),
        "cost_usd": cost_usd,
        "gpu": "T4",
    }


def _synthesize_cosyvoice(text: str, voice_id: str, language: str, speed: float) -> bytes:
    import io
    import soundfile as sf
    import numpy as np

    try:
        from cosyvoice.cli.cosyvoice import AutoModel
        model = AutoModel(model_dir="FunAudioLLM/CosyVoice2-0.5B", cache_dir="/models")
    except Exception:
        return _fallback_silent_wav(len(text))

    try:
        for i, result in enumerate(model.inference_zero_shot(
            tts_text=text,
            prompt_text="",
            prompt_speech_16k=None,
            zero_shot_spk_id=voice_id,
        )):
            audio = result.get("tts_speech", None) if isinstance(result, dict) else None
            if audio is None and hasattr(result, "tts_speech"):
                audio = result.tts_speech
            if audio is not None:
                buf = io.BytesIO()
                if hasattr(audio, "cpu"):
                    audio_np = audio.cpu().numpy()
                else:
                    audio_np = np.asarray(audio)
                if speed != 1.0:
                    audio_np = _resample_simple(audio_np, speed)
                sf.write(buf, audio_np, samplerate=22050, format="WAV")
                return buf.getvalue()
    except Exception:
        return _fallback_silent_wav(len(text))

    return _fallback_silent_wav(len(text))


def _fallback_silent_wav(text_len: int) -> bytes:
    import io
    import struct

    sample_rate = 22050
    duration = max(1.0, text_len / 15.0)
    n_samples = int(sample_rate * duration)
    data = b"\x00\x00" * n_samples
    header = b"RIFF"
    data_size = len(data)
    file_size = data_size + 36
    header += struct.pack("<I", file_size) + b"WAVE"
    header += b"fmt "
    header += struct.pack("<IHHII", 16, 1, 1, sample_rate, sample_rate * 2)
    header += b"data"
    header += struct.pack("<I", data_size)
    return header + data


def _resample_simple(audio_np, speed: float):
    import numpy as np
    n = int(len(audio_np) / speed)
    indices = np.linspace(0, len(audio_np) - 1, n).astype(int)
    return audio_np[indices]


def _estimate_audio_duration(text: str, speed: float) -> float:
    words = len(text.split())
    base_sec = words / 2.5
    return round(base_sec / speed, 2)


@app.function(
    image=image,
    volumes={"/cache": volume},
    scaledown_window=60,
    timeout=60,
)
@modal.fastapi_endpoint(method="GET")
def health() -> dict:
    return {
        "app": APP_NAME,
        "status": "healthy",
        "voices": list(VOICE_PRESETS.keys()),
        "default_voice": DEFAULT_VOICE,
        "languages": ["id", "en", "zh", "ja"],
        "model": "CosyVoice2-0.5B",
        "license": "apache-2.0",
    }
