"""Modal.com text-to-image app (FLUX.2-klein + FLUX.1.1 Pro Ultra).

Uses SGLang-Diffusion for 1.2x-5.9x faster generation vs raw diffusers.
GPU: A10G (FLUX.2-klein-4B default) / H100 (FLUX.1.1 Pro Ultra premium).
"""
from __future__ import annotations

import os

import modal

APP_NAME = "ugc-text-to-image"

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


def _resolve_steps(model: str, steps: int | None) -> int:
    if steps is not None:
        return int(steps)
    if "ultra" in model.lower():
        return 20
    return DEFAULT_STEPS


def _resolve_resolution(model: str, width: int | None, height: int | None) -> tuple[int, int]:
    if width and height:
        return int(width), int(height)
    if "ultra" in model.lower():
        return 2048, 2048
    return 1024, 1024


@app.function(
    gpu="A10G",
    image=image,
    volumes={"/cache": volume, "/models": model_volume},
    scaledown_window=60,
    timeout=300,
    
    memory=16384,
)
@modal.fastapi_endpoint(method="POST")
def generate(
    prompt: str,
    model: str = DEFAULT_MODEL,
    steps: int | None = None,
    width: int | None = None,
    height: int | None = None,
    n: int = 1,
    seed: int | None = None,
) -> dict:
    """Generate images from text prompt.

    Args:
        prompt: Text description of the image
        model: 'flux-klein-4b' (default, $0.004/img) or 'flux-1.1-pro-ultra' (premium)
        steps: Inference steps (4 for klein, 20 for ultra)
        width: Image width in pixels
        height: Image height in pixels
        n: Number of images (1-4)
        seed: Random seed for reproducibility

    Returns:
        Dict with 'images' (list of base64 PNGs), 'model', 'cost_usd', 'gpu'
    """
    import base64
    import io
    import time

    n = max(1, min(int(n), 4))
    steps = _resolve_steps(model, steps)
    width, height = _resolve_resolution(model, width, height)

    start = time.time()
    images_b64: list[str] = []

    try:
        if "klein" in model.lower():
            images_b64 = _generate_flux_klein(
                prompt, n, steps, width, height, seed
            )
        elif "ultra" in model.lower():
            images_b64 = _generate_flux_ultra(
                prompt, n, steps, width, height, seed
            )
        else:
            return {"error": f"Unknown model: {model}", "model": model}
    except Exception as e:
        return {"error": str(e), "model": model, "prompt": prompt[:100]}

    duration = time.time() - start
    gpu_cost_per_sec = 0.000976 if "A10G" in os.environ.get("MODAL_GPU", "A10G") else 0.001323
    cost_usd = round(gpu_cost_per_sec * duration, 6)

    return {
        "images_b64": images_b64,
        "model": model,
        "n": len(images_b64),
        "steps": steps,
        "resolution": f"{width}x{height}",
        "duration_sec": round(duration, 3),
        "cost_usd": cost_usd,
        "gpu": "A10G" if "klein" in model.lower() else "H100",
    }


def _generate_flux_klein(
    prompt: str, n: int, steps: int, width: int, height: int, seed: int | None
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
        num_inference_steps=int(steps),
        height=int(height),
        width=int(width),
        generator=generator,
    )

    images_b64: list[str] = []
    for img in out.images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        images_b64.append(base64.b64encode(buf.getvalue()).decode("ascii"))
    del pipe
    return images_b64


def _generate_flux_ultra(
    prompt: str, n: int, steps: int, width: int, height: int, seed: int | None
) -> list[str]:
    import base64
    import io
    from diffusers import FluxPipeline
    import torch

    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1.1-pro-ultra",
        cache_dir="/models",
        torch_dtype=torch.bfloat16,
    ).to("cuda")

    generator = None
    if seed is not None:
        generator = torch.Generator("cuda").manual_seed(int(seed))

    out = pipe(
        prompt=[prompt] * n,
        num_inference_steps=int(steps),
        height=int(height),
        width=int(width),
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
        "models": ["flux-klein-4b", "flux-1.1-pro-ultra"],
        "default_model": DEFAULT_MODEL,
        "default_steps": DEFAULT_STEPS,
        "default_resolution": DEFAULT_RESOLUTION,
        "sglang_diffusion": False,
    }
