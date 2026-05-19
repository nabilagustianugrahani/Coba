import modal
import os
import asyncio
from io import BytesIO

app = modal.App("ugc-ai-overpower-gpu")

# Download weights during image build step to prevent cold-boot delays
def download_models():
    import torch
    from diffusers import StableDiffusionXLPipeline
    model_id = "stabilityai/sdxl-turbo"
    StableDiffusionXLPipeline.from_pretrained(
        model_id, torch_dtype=torch.float16, variant="fp16"
    )
    # Placeholder for downloading LivePortrait / SadTalker weights
    print("Downloaded SDXL Turbo weights.")

# Overkill environment: We install heavy ML packages
image_env = (
    modal.Image.debian_slim()
    .pip_install(
        "torch", "diffusers", "transformers", "accelerate", "edge-tts", "moviepy>=2.0.0", "pillow", "opencv-python", "numpy"
    )
    .run_function(download_models)
)

@app.function(image=image_env, gpu="H100") # B200 / H100
def generate_influencer_character(prompt: str) -> bytes:
    """
    Overkill consistent character generation using SDXL.
    """
    print(f"Generating highly consistent AI Influencer on H100 with prompt: {prompt}")
    import torch
    from diffusers import StableDiffusionXLPipeline
    from PIL import Image

    model_id = "stabilityai/sdxl-turbo"
    try:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id, torch_dtype=torch.float16, variant="fp16"
        ).to("cuda")

        image = pipe(prompt=prompt, num_inference_steps=4, guidance_scale=0.0).images[0]

        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"Failed to generate image: {e}")
        return b""

@app.function(image=image_env)
def generate_voiceover(text: str, voice: str = "id-ID-ArdiNeural") -> bytes:
    """
    Zero cost TTS using edge-tts for Indonesian voices.
    """
    print(f"Generating TTS for text: {text} with voice {voice}")
    import edge_tts

    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data

    return asyncio.run(_generate())

@app.function(image=image_env, gpu="H100", timeout=600)
def animate_character(image_bytes: bytes, audio_bytes: bytes) -> bytes:
    """
    Overkill animation combining the static image and audio.
    This simulates a full LivePortrait lip-sync integration by processing frames.
    """
    print("Animating character with lip-sync on H100 (LivePortrait Simulation)...")
    import tempfile
    import os
    import numpy as np
    from moviepy.editor import ImageSequenceClip, AudioFileClip
    from PIL import Image

    try:
        if not image_bytes or not audio_bytes:
            raise ValueError("Missing image or audio bytes")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_tmp:
            img_tmp.write(image_bytes)
            img_path = img_tmp.name

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as aud_tmp:
            aud_tmp.write(audio_bytes)
            aud_path = aud_tmp.name

        audio_clip = AudioFileClip(aud_path)
        fps = 24
        duration = audio_clip.duration
        num_frames = int(duration * fps)

        # Open base image
        base_img = Image.open(img_path).convert("RGB")
        base_np = np.array(base_img)

        # Simulate lip-syncing by applying minor deformations to the mouth region across frames
        # In actual production, this loop invokes LivePortrait/SadTalker inference per frame
        print(f"Generating {num_frames} frames for lip-sync...")
        frames = []
        for i in range(num_frames):
            # Simple simulation: jitter the image slightly
            jitter_x = np.random.randint(-2, 3)
            jitter_y = np.random.randint(-2, 3)
            shifted = np.roll(base_np, jitter_x, axis=1)
            shifted = np.roll(shifted, jitter_y, axis=0)
            frames.append(shifted)

        video_clip = ImageSequenceClip(frames, fps=fps)
        video_clip = video_clip.set_audio(audio_clip)

        out_path = tempfile.mktemp(suffix=".mp4")

        video_clip.write_videofile(
            out_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            logger=None
        )

        with open(out_path, "rb") as f:
            final_video_bytes = f.read()

        os.remove(img_path)
        os.remove(aud_path)
        os.remove(out_path)

        return final_video_bytes

    except Exception as e:
        print(f"Error in animation pipeline: {e}")
        return b""

@app.local_entrypoint()
def main():
    print("Testing Modal GPU pipeline...")
