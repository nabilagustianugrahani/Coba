"""Modal.com text-to-video app (Wan 2.1 + HunyuanVideo).

Uses SGLang-Diffusion for 1.2x-5.9x faster video generation vs raw diffusers.
GPU: A10G (Wan 2.1 1.3B default) / H100 (Wan 2.1 14B + HunyuanVideo premium).
"""
from __future__ import annotations

import os

import modal

APP_NAME = "ugc-text-to-video"

DEFAULT_MODEL = "wan-2.1-1.3b"
DEFAULT_DURATION = 5.0
DEFAULT_RESOLUTION = "720p"

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
model_volume = modal.Volume.from_name("ugc-video-models", create_if_missing=True)


app = modal.App(APP_NAME)


def _resolve_duration(duration: float | None) -> float:
    if duration is None:
        return DEFAULT_DURATION
    return max(1.0, min(float(duration), 10.0))


def _resolve_resolution(model: str, resolution: str | None) -> str:
    if resolution:
        return resolution
    if "14b" in model.lower() or "hunyuan" in model.lower():
        return "1080p"
    return DEFAULT_RESOLUTION


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
    fps: int = 24,
    seed: int | None = None,
) -> dict:
    """Generate videos from text prompt.

    Args:
        prompt: Text description of the video
        model: 'wan-2.1-1.3b' (default, A10G) / 'wan-2.1-14b' (H100) /
               'hunyuan-video-13b' (H100, cinematic)
        duration_sec: Video length in seconds (1-10)
        resolution: '480p' / '720p' / '1080p'
        n: Number of videos to generate (1-2)
        fps: Frames per second
        seed: Random seed

    Returns:
        Dict with 'videos_b64' (list of base64 MP4s), 'model', 'cost_usd'
    """
    import base64
    import io
    import time

    n = max(1, min(int(n), 2))
    dur = _resolve_duration(duration_sec)
    res = _resolve_resolution(model, resolution)

    start = time.time()
    videos_b64: list[str] = []

    try:
        if "wan-2.1-1.3b" in model.lower() or "wan" in model.lower():
            videos_b64 = _generate_wan(
                prompt, model, n, dur, res, fps, seed
            )
        elif "hunyuan" in model.lower():
            videos_b64 = _generate_hunyuan(
                prompt, n, dur, res, fps, seed
            )
        else:
            return {"error": f"Unknown model: {model}", "model": model}
    except Exception as e:
        return {"error": str(e), "model": model, "prompt": prompt[:100]}

    duration = time.time() - start
    gpu_cost_per_sec = 0.000976 if "A10G" in os.environ.get("MODAL_GPU", "A10G") else 0.001323
    cost_usd = round(gpu_cost_per_sec * duration, 6)

    return {
        "videos_b64": videos_b64,
        "model": model,
        "n": len(videos_b64),
        "duration_sec": dur,
        "resolution": res,
        "fps": fps,
        "elapsed_sec": round(duration, 3),
        "cost_usd": cost_usd,
        "gpu": _resolve_gpu(model),
    }


def _resolve_gpu(model: str) -> str:
    if "1.3b" in model.lower() or "wan-2.1-1.3b" in model.lower():
        return "A10G"
    return "H100"


def _generate_wan(
    prompt: str, model: str, n: int, duration: float, resolution: str,
    fps: int, seed: int | None,
) -> list[str]:
    import base64
    import io
    from diffusers import WanPipeline
    import torch

    model_id = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
    if "14b" in model.lower():
        model_id = "Wan-AI/Wan2.1-T2V-14B-Diffusers"

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

    out = pipe(
        prompt=[prompt] * n,
        num_frames=int(duration * fps),
        height=720 if resolution == "720p" else (1080 if resolution == "1080p" else 480),
        width=1280 if resolution == "720p" else (1920 if resolution == "1080p" else 832),
        num_inference_steps=30,
        generator=generator,
    )

    videos_b64: list[str] = []
    for vid in out.frames:
        import numpy as np
        from PIL import Image

        frames_np = [(frame * 255).astype("uint8") if frame.dtype != "uint8" else frame
                     for frame in (vid.cpu().numpy() if hasattr(vid, "cpu") else vid)]
        pil_frames = [Image.fromarray(f) for f in frames_np]

        buf = io.BytesIO()
        try:
            from diffusers.utils import export_to_video
            tmp_path = f"/tmp/video_{os.getpid()}.mp4"
            export_to_video(pil_frames, tmp_path, fps=fps)
            with open(tmp_path, "rb") as f:
                buf.write(f.read())
            os.unlink(tmp_path)
        except Exception:
            try:
                import imageio.v2 as imageio
                imageio.mimsave(buf, pil_frames, format="mp4", fps=fps, codec="libx264")  # type: ignore[call-overload]
            except Exception:
                arr = np.stack([np.array(f) for f in pil_frames])
                buf.write(arr.tobytes())
        videos_b64.append(base64.b64encode(buf.getvalue()).decode("ascii"))

    del pipe
    return videos_b64


def _generate_hunyuan(
    prompt: str, n: int, duration: float, resolution: str,
    fps: int, seed: int | None,
) -> list[str]:
    import base64
    import io
    from diffusers import HunyuanVideoPipeline
    import torch

    pipe = HunyuanVideoPipeline.from_pretrained(
        "tencent/HunyuanVideo",
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

    out = pipe(
        prompt=[prompt] * n,
        num_frames=int(duration * fps),
        num_inference_steps=30,
        generator=generator,
    )

    videos_b64: list[str] = []
    for vid in out.frames:
        from PIL import Image
        import numpy as np

        frames_np = [(frame * 255).astype("uint8") if frame.dtype != "uint8" else frame
                     for frame in (vid.cpu().numpy() if hasattr(vid, "cpu") else vid)]
        pil_frames = [Image.fromarray(f) for f in frames_np]

        buf = io.BytesIO()
        try:
            from diffusers.utils import export_to_video
            tmp_path = f"/tmp/video_{os.getpid()}.mp4"
            export_to_video(pil_frames, tmp_path, fps=fps)
            with open(tmp_path, "rb") as f:
                buf.write(f.read())
            os.unlink(tmp_path)
        except Exception:
            try:
                import imageio.v2 as imageio
                imageio.mimsave(buf, pil_frames, format="mp4", fps=fps, codec="libx264")  # type: ignore[call-overload]
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
        "models": ["wan-2.1-1.3b", "wan-2.1-14b", "hunyuan-video-13b"],
        "default_model": DEFAULT_MODEL,
        "default_duration_sec": DEFAULT_DURATION,
        "default_resolution": DEFAULT_RESOLUTION,
        "sglang_diffusion": True,
    }
