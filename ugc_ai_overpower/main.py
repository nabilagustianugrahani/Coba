import logging
import os
import json
import modal
import hashlib
from scraper.scraper import EcommerceScraper
from evaluator.evaluator import FYPEvaluator
from video_processor.auto_editor import AutoEditor
from uploader.uploader import SocialUploader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from modal_gpu.modal_app import (
    app as modal_app,
    ModelGenerator,
    generate_voiceover
)

# Initialize caching directory
CACHE_DIR = "broll_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_face_bytes():
    face_path = "assets/influencer_face.jpg"
    if os.path.exists(face_path):
        with open(face_path, "rb") as f:
            return f.read()
    return b"dummy_face_bytes"

def get_cached_broll(prompt: str) -> bytes:
    """Returns cached B-Roll bytes if available, else None."""
    prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{prompt_hash}.mp4")
    if os.path.exists(cache_path):
        logger.info(f"B-Roll Cache Hit for prompt: {prompt[:30]}...")
        with open(cache_path, "rb") as f:
            return f.read()
    return None

def set_cached_broll(prompt: str, video_bytes: bytes):
    """Saves generated B-Roll bytes to cache."""
    prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{prompt_hash}.mp4")
    with open(cache_path, "wb") as f:
        f.write(video_bytes)
    logger.info(f"Saved B-Roll to cache: {cache_path}")

def generate_video_modal_remote(swarm_data: dict, video_path: str):
    logger.info("Connecting to Modal B200 God-Tier pipeline...")
    try:
        narration = swarm_data["narration"]
        motion_prompt = swarm_data["avatar_motion_prompt"]
        b_roll_schedule = swarm_data.get("b_roll_schedule", [])
        face_bytes = get_face_bytes()

        b_roll_data = []

        # Instantiate the Stateful generator class
        generator = ModelGenerator()

        if os.getenv("MODAL_TOKEN_ID") or os.path.exists(os.path.expanduser("~/.modal.toml")):
            with modal_app.run():
                logger.info("Generating Text-to-Video Base remotely on Modal...")
                base_vid_bytes = generator.generate_base_video.remote(motion_prompt)

                logger.info("Generating B-Rolls remotely on Modal (with Caching)...")
                for b_roll in b_roll_schedule:
                    cached_bytes = get_cached_broll(b_roll["prompt"])
                    if cached_bytes:
                        b_bytes = cached_bytes
                    else:
                        b_bytes = generator.generate_base_video.remote(b_roll["prompt"])
                        set_cached_broll(b_roll["prompt"], b_bytes)

                    b_roll_data.append({
                        "start": b_roll["start"],
                        "end": b_roll["end"],
                        "clip_bytes": b_bytes
                    })

                logger.info("Applying FaceFusion remotely on Modal...")
                swapped_vid_bytes = generator.face_swap_consistency.remote(base_vid_bytes, face_bytes)

                logger.info("Generating Edge-TTS Audio remotely on Modal...")
                audio_bytes = generate_voiceover.remote(narration)

                logger.info("Running LivePortrait Lip-Sync remotely on Modal...")
                synced_vid_bytes = generator.lip_sync_video.remote(swapped_vid_bytes, audio_bytes)
        else:
            logger.warning("No Modal Token found. Falling back to local execution for pipeline testing.")
            logger.info("Generating Text-to-Video Base locally...")
            base_vid_bytes = generator.generate_base_video.local(motion_prompt)

            logger.info("Generating B-Rolls locally (with Caching)...")
            for b_roll in b_roll_schedule:
                cached_bytes = get_cached_broll(b_roll["prompt"])
                if cached_bytes:
                    b_bytes = cached_bytes
                else:
                    b_bytes = generator.generate_base_video.local(b_roll["prompt"])
                    set_cached_broll(b_roll["prompt"], b_bytes)

                b_roll_data.append({
                    "start": b_roll["start"],
                    "end": b_roll["end"],
                    "clip_bytes": b_bytes
                })

            logger.info("Applying FaceFusion locally...")
            swapped_vid_bytes = generator.face_swap_consistency.local(base_vid_bytes, face_bytes)
            logger.info("Generating Edge-TTS Audio locally...")
            audio_bytes = generate_voiceover.local(narration)
            logger.info("Running LivePortrait Lip-Sync locally...")
            synced_vid_bytes = generator.lip_sync_video.local(swapped_vid_bytes, audio_bytes)

        logger.info("Applying Auto-Captions and B-Rolls locally...")
        editor = AutoEditor()
        final_video_bytes = editor.apply_automated_factory_edit(synced_vid_bytes, audio_bytes, narration, b_roll_data)

        with open(video_path, "wb") as f:
            f.write(final_video_bytes)

        return True
    except Exception as e:
        logger.error(f"Error executing Modal pipeline: {e}")
        return False

def main():
    logger.info("Starting God-Tier UGC Pipeline (B200 Setup)...")

    # 1. Scrape
    scraper = EcommerceScraper()
    niche = os.getenv("UGC_NICHE", "beauty")
    products = scraper.get_best_products(niche=niche)
    if not products:
        logger.error("No products found.")
        return

    top_product = products[0]
    logger.info(f"Selected Product: {top_product['product_name']} | Com: {top_product['commission_rate']}%")

    # 2. Swarm AI Evaluation & Generation
    evaluator = FYPEvaluator()
    swarm_blueprint = evaluator.swarm_evaluate_and_generate(top_product['product_name'], niche)

    logger.info("Swarm Blueprint Approved:")
    logger.info(json.dumps(swarm_blueprint, indent=2))

    # 3. Trigger Modal GPU Pipeline + Auto Editor
    video_path = "output_god_tier_ugc.mp4"
    logger.info("Triggering AI Video Generation via Modal...")

    success = generate_video_modal_remote(swarm_blueprint, video_path)

    if not success:
        logger.warning("Pipeline execution failed.")
        return

    logger.info(f"God-Tier Video ready at: {video_path}")

    # 4. Recursive FYP Evaluation Loop on Final Video
    final_eval = evaluator.evaluate_final_video(swarm_blueprint, video_path)
    logger.info("Final Video FYP Evaluation Result:")
    try:
        if isinstance(final_eval, dict):
            logger.info(json.dumps(final_eval, indent=2))
        else:
            logger.info(final_eval)
    except Exception:
        logger.info(str(final_eval))

    # 5. Schedule Upload
    uploader = SocialUploader()
    caption = f"{swarm_blueprint['hook']} Cek keranjang sekarang! #fyp #ugc"
    uploader.schedule_upload(video_path, caption)

    logger.info("Pipeline completed successfully. Awaiting scheduled uploads.")

if __name__ == "__main__":
    main()
