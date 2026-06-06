"""FLUX.2-klein image generation — fast variant (standalone Modal app).

Optimized for 4-step inference on A10G (~$0.004/image).
Ultrarealistic output, Apache-2.0 license, 1024x1024 default.
"""
from __future__ import annotations

import os

import modal

APP_NAME = "ugc-flux-klein"

DEFAULT_MODEL = "flux-klein-4b"
DEFAULT_STEPS = 4
DEFAULT_RESOLUTION = "1024x1024"

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "sglang>=0.4.0",
    "torch>=2.5.0",
    "transformers>=4.46.0",
    "accelerate>=1.0.0",
    "diffusers>=0.31.0",
    "Pillow>=10.0.0",
    "huggingface-hub>=0.26.0",
)

volume = modal.Volume.from_name("ugc-models-cache", create_if_missing=True)
model_volume = modal.Volume.from_name("ugc-flux-models", create_if_missing=True)

app = modal.App(APP_NAME)


def _resolve_steps(steps: int | None) -> int:
    return DEFAULT_STEPS if steps is None else max(1, int(steps))


def _resolve_resolution(width: int | None, height: int | None) -> tuple[int, int]:
    if width and height:
        return int(width), int(height)
    return 1024, 1024


@app.function(
    gpu="A10G",
    image=image,
    volumes={"/cache": volume, "/models": model_volume},
    scaledown_window=60,
    timeout=120,
    memory=16384,
)
@modal.fastapi_endpoint(method="POST")
def generate(
    prompt: str,
    steps: int | None = None,
    width: int | None = None,
    height: int | None = None,
    n: int = 1,
    seed: int | None = None,
) -> dict:
    """Generate images using FLUX.2-klein.

    Args:
        prompt: Text description of the image
        steps: Inference steps (default 4 for speed)
        width: Image width in pixels
        height: Image height in pixels
        n: Number of images (1-4)
        seed: Random seed for reproducibility

    Returns:
        Dict with 'images_b64', 'model', 'cost_usd', 'gpu', etc.
    """
    import base64
    import io
    import time

    n = max(1, min(int(n), 4))
    steps = _resolve_steps(steps)
    width, height = _resolve_resolution(width, height)

    start = time.time()
    images_b64: list[str] = []

    try:
        images_b64 = _generate_flux_klein(prompt, n, steps, width, height, seed)
    except Exception as e:
        return {"error": str(e), "model": DEFAULT_MODEL, "prompt": prompt[:100]}

    duration = time.time() - start
    cost_usd = round(0.000976 * duration, 6)

    return {
        "images_b64": images_b64,
        "model": DEFAULT_MODEL,
        "n": len(images_b64),
        "steps": steps,
        "resolution": f"{width}x{height}",
        "duration_sec": round(duration, 3),
        "cost_usd": cost_usd,
        "gpu": "A10G",
    }


def _generate_flux_klein(
    prompt: str, n: int, steps: int, width: int, height: int, seed: int | None,
) -> list[str]:
    import base64
    import io
    from diffusers import FluxPipeline
    import torch

    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.2-klein-4b",
        cache_dir="/models",
        torch_dtype=torch.bfloat16,
    ).to("cuda")
    if pipe.vae is not None:
        try:
            pipe.vae.enable_tiling()
        except Exception:
            pass

    generator = None
    if seed is not None:
        generator = torch.Generator("cuda").manual_seed(int(seed))

    out = pipe(
        prompt=[prompt] * n,
        num_inference_steps=steps,
        height=height,
        width=width,
        generator=generator,
    )

    images_b64: list[str] = []
    for img in out.images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        images_b64.append(base64.b64encode(buf.getvalue()).decode("ascii"))
    del pipe
    return images_b64


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
        "models": ["flux-klein-4b"],
        "default_steps": DEFAULT_STEPS,
        "default_resolution": DEFAULT_RESOLUTION,
        "sglang_diffusion": False,
    }
