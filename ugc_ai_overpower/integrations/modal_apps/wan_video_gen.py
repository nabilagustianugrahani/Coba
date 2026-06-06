"""Wan 2.1 text-to-video generation (standalone Modal app).

Focused on Wan 2.1 1.3B (A10G, cheap) and 14B (H100, premium).
Uses SGLang-Diffusion for up to 5.9x faster generation.
"""
from __future__ import annotations

import os

import modal

APP_NAME = "ugc-wan-video-gen"

DEFAULT_MODEL = "wan-2.1-1.3b"
DEFAULT_DURATION = 5.0
DEFAULT_RESOLUTION = "720p"
DEFAULT_FPS = 24

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "sglang[diffusion]>=0.4.0",
    "torch>=2.5.0",
    "transformers>=4.46.0",
    "accelerate>=1.0.0",
    "diffusers>=0.31.0",
    "av>=12.0.0",
    "Pillow>=10.0.0",
    "huggingface-hub>=0.26.0",
)

volume = modal.Volume.from_name("ugc-models-cache", create_if_missing=True)
model_volume = modal.Volume.from_name("ugc-wan-models", create_if_missing=True)

app = modal.App(APP_NAME)


def _resolve_model_id(model: str) -> str:
    if "14b" in model.lower():
        return "Wan-AI/Wan2.1-T2V-14B-Diffusers"
    return "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"


def _resolve_gpu(model: str) -> str:
    return "H100" if "14b" in model.lower() else "A10G"


def _resolve_duration(duration: float | None) -> float:
    if duration is None:
        return DEFAULT_DURATION
    return max(1.0, min(float(duration), 10.0))


def _resolve_resolution(model: str, resolution: str | None) -> str:
    if resolution:
        return resolution
    return "1080p" if "14b" in model.lower() else DEFAULT_RESOLUTION


@app.function(
    gpu="A10G",
    image=image,
    volumes={"/cache": volume, "/models": model_volume},
    scaledown_window=60,
    timeout=600,
    memory=24576,
)
@modal.fastapi_endpoint(method="POST")
def generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    duration_sec: float | None = None,
    resolution: str | None = None,
    n: int = 1,
    fps: int = DEFAULT_FPS,
    seed: int | None = None,
) -> dict:
    """Generate videos from text using Wan 2.1.

    Args:
        prompt: Text description of the video
        model: 'wan-2.1-1.3b' (default, A10G) or 'wan-2.1-14b' (H100)
        duration_sec: Video length in seconds (1-10)
        resolution: '480p' / '720p' / '1080p'
        n: Number of videos (1-2)
        fps: Frames per second
        seed: Random seed for reproducibility

    Returns:
        Dict with 'videos_b64', 'model', 'cost_usd', 'gpu', etc.
    """
    import base64
    import io
    import time

    n = max(1, min(int(n), 2))
    dur = _resolve_duration(duration_sec)
    res = _resolve_resolution(model, resolution)
    gpu = _resolve_gpu(model)
    model_id = _resolve_model_id(model)

    start = time.time()
    videos_b64: list[str] = []

    try:
        videos_b64 = _generate_wan_video(prompt, model_id, n, dur, res, fps, seed)
    except Exception as e:
        return {"error": str(e), "model": model, "prompt": prompt[:100]}

    elapsed = time.time() - start
    gpu_cost_per_sec = 0.001323 if gpu == "H100" else 0.000976
    cost_usd = round(gpu_cost_per_sec * elapsed, 6)

    return {
        "videos_b64": videos_b64,
        "model": model,
        "n": len(videos_b64),
        "duration_sec": dur,
        "resolution": res,
        "fps": fps,
        "elapsed_sec": round(elapsed, 3),
        "cost_usd": cost_usd,
        "gpu": gpu,
    }


def _generate_wan_video(
    prompt: str, model_id: str, n: int, duration: float,
    resolution: str, fps: int, seed: int | None,
) -> list[str]:
    import base64
    import io
    from diffusers import WanPipeline
    import torch

    pipe = WanPipeline.from_pretrained(
        model_id,
        cache_dir="/models",
        torch_dtype=torch.bfloat16,
    ).to("cuda")

    try:
        pipe.enable_model_cpu_offload()
    except Exception:
        pass
    try:
        pipe.vae.enable_slicing()
        pipe.vae.enable_tiling()
    except Exception:
        pass

    generator = None
    if seed is not None:
        generator = torch.Generator("cuda").manual_seed(int(seed))

    height_map = {"480p": 480, "720p": 720, "1080p": 1080}
    width_map = {"480p": 832, "720p": 1280, "1080p": 1920}
    height = height_map.get(resolution, 720)
    width = width_map.get(resolution, 1280)

    out = pipe(
        prompt=[prompt] * n,
        num_frames=int(duration * fps),
        height=height,
        width=width,
        num_inference_steps=30,
        generator=generator,
    )

    videos_b64: list[str] = []
    for vid in out.frames:
        import numpy as np
        from PIL import Image

        frames_np = [
            (frame * 255).astype("uint8") if frame.dtype != "uint8" else frame
            for frame in (vid.cpu().numpy() if hasattr(vid, "cpu") else vid)
        ]
        pil_frames = [Image.fromarray(f) for f in frames_np]

        buf = io.BytesIO()
        try:
            from diffusers.utils import export_to_video
            tmp_path = f"/tmp/wan_{os.getpid()}.mp4"
            export_to_video(pil_frames, tmp_path, fps=fps)
            with open(tmp_path, "rb") as f:
                buf.write(f.read())
            os.unlink(tmp_path)
        except Exception:
            try:
                import imageio.v2 as imageio
                imageio.mimsave(buf, pil_frames, format="mp4", fps=fps, codec="libx264")
            except Exception:
                arr = np.stack([np.array(f) for f in pil_frames])
                buf.write(arr.tobytes())
        videos_b64.append(base64.b64encode(buf.getvalue()).decode("ascii"))

    del pipe
    return videos_b64


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
        "models": ["wan-2.1-1.3b", "wan-2.1-14b"],
        "default_model": DEFAULT_MODEL,
        "default_duration_sec": DEFAULT_DURATION,
        "default_resolution": DEFAULT_RESOLUTION,
        "sglang_diffusion": True,
    }
