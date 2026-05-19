import logging
import os
import json
import modal
from scraper.scraper import EcommerceScraper
from evaluator.evaluator import FYPEvaluator
from video_processor.auto_editor import AutoEditor
from uploader.uploader import SocialUploader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from modal_gpu.modal_app import (
    app as modal_app,
    generate_base_video,
    face_swap_consistency,
    generate_voiceover,
    lip_sync_video
)

def get_face_bytes():
    face_path = "assets/influencer_face.jpg"
    if os.path.exists(face_path):
        with open(face_path, "rb") as f:
            return f.read()
    return b"dummy_face_bytes"

def generate_video_modal_remote(swarm_data: dict, video_path: str):
    logger.info("Connecting to Modal B200 God-Tier pipeline...")
    try:
        narration = swarm_data["narration"]
        motion_prompt = swarm_data["avatar_motion_prompt"]
        face_bytes = get_face_bytes()

        # Check if modal token exists, otherwise fallback to local execution for testing
        if os.getenv("MODAL_TOKEN_ID") or os.path.exists(os.path.expanduser("~/.modal.toml")):
            with modal_app.run():
                logger.info("Generating Text-to-Video Base remotely on Modal...")
                base_vid_bytes = generate_base_video.remote(motion_prompt)

                logger.info("Applying FaceFusion remotely on Modal...")
                swapped_vid_bytes = face_swap_consistency.remote(base_vid_bytes, face_bytes)

                logger.info("Generating Edge-TTS Audio remotely on Modal...")
                audio_bytes = generate_voiceover.remote(narration)

                logger.info("Running LivePortrait Lip-Sync remotely on Modal...")
                synced_vid_bytes = lip_sync_video.remote(swapped_vid_bytes, audio_bytes)
        else:
            logger.warning("No Modal Token found. Falling back to local execution for pipeline testing.")
            logger.info("Generating Text-to-Video Base locally...")
            base_vid_bytes = generate_base_video.local(motion_prompt)
            logger.info("Applying FaceFusion locally...")
            swapped_vid_bytes = face_swap_consistency.local(base_vid_bytes, face_bytes)
            logger.info("Generating Edge-TTS Audio locally...")
            audio_bytes = generate_voiceover.local(narration)
            logger.info("Running LivePortrait Lip-Sync locally...")
            synced_vid_bytes = lip_sync_video.local(swapped_vid_bytes, audio_bytes)

        logger.info("Applying Auto-Captions locally...")
        editor = AutoEditor()
        final_video_bytes = editor.apply_hormozi_captions(synced_vid_bytes, audio_bytes, narration)

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
    # We safely grab the JSON if it fell back to dict, or parse it if it returned a raw string dict
    try:
        if isinstance(final_eval, dict):
            logger.info(json.dumps(final_eval, indent=2))
        else:
            logger.info(final_eval)
    except Exception:
        logger.info(str(final_eval))

    # In a real scenario, if final_eval["is_viral_ready"] == False, we would loop back to step 2.

    # 5. Schedule Upload
    uploader = SocialUploader()
    caption = f"{swarm_blueprint['hook']} Cek keranjang sekarang! #fyp #ugc"
    uploader.schedule_upload(video_path, caption)

    logger.info("Pipeline completed successfully. Awaiting scheduled uploads.")

if __name__ == "__main__":
    main()
