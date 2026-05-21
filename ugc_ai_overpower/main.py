import logging
import os
import json
import modal
import hashlib
import re
import tempfile
from scraper.scraper import EcommerceScraper, TikTokScraper
from evaluator.evaluator import FYPEvaluator
from video_processor.auto_editor import AutoEditor
from uploader.uploader import SocialUploader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from modal_gpu.modal_app import (
    app as modal_app,
    ModelGenerator
)

CACHE_DIR = "broll_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cached_broll(prompt: str) -> bytes:
    prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{prompt_hash}.mp4")
    if os.path.exists(cache_path):
        logger.info(f"B-Roll Cache Hit for prompt: {prompt[:30]}...")
        with open(cache_path, "rb") as f:
            return f.read()
    return None

def set_cached_broll(prompt: str, video_bytes: bytes):
    prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{prompt_hash}.mp4")
    with open(cache_path, "wb") as f:
        f.write(video_bytes)
    logger.info(f"Saved B-Roll to cache: {cache_path}")

def resolve_node_variables(value, nodes):
    if not isinstance(value, str):
        return value
    pattern = r"\{\{(.*?)\}\}"
    matches = re.findall(pattern, value)
    for match in matches:
        for node in nodes:
            if node.get("id") == match:
                value = value.replace(f"{{{{{match}}}}}", node.get("value", ""))
                break
    return value

def generate_video_modal_remote(swarm_data: dict, video_path: str, persona: str = "Host A"):
    logger.info(f"Connecting to Modal B200 God-Tier Node pipeline for {persona}...")
    try:
        nodes = swarm_data.get("nodes", [])
        graph = swarm_data.get("execution_graph", {})
        template = "05_extend_and_stitch"

        generator = ModelGenerator()
        is_remote = os.getenv("MODAL_TOKEN_ID") or os.path.exists(os.path.expanduser("~/.modal.toml"))
        final_video_bytes = None

        ctx = modal_app.run() if is_remote else None

        try:
            if ctx: ctx.__enter__()

            logger.info("Executing 05_extend_and_stitch Template...")

            # Resolve Prompts
            char_prompt = resolve_node_variables(graph.get("generate_character_anchor", ""), nodes)
            prompt_part1 = resolve_node_variables(graph.get("generate_part1_video", ""), nodes)
            prompt_part2 = resolve_node_variables(graph.get("generate_part2_video", ""), nodes)
            audio_text_part1 = resolve_node_variables(graph.get("generate_audio_part1", ""), nodes)
            audio_text_part2 = resolve_node_variables(graph.get("generate_audio_part2", ""), nodes)

            # Map Functions
            gen_img = generator.generate_character_image.remote if is_remote else generator.generate_character_image.local
            gen_vid = generator.generate_base_video.remote if is_remote else generator.generate_base_video.local
            gen_aud = generator.generate_voiceover_f5.remote if is_remote else generator.generate_voiceover_f5.local
            sync_vid = generator.lip_sync_video.remote if is_remote else generator.lip_sync_video.local
            face_swap = generator.face_swap_consistency.remote if is_remote else generator.face_swap_consistency.local

            # Generate Master Face Anchor
            logger.info(f"Generating Character Sheet Anchor for {persona}...")
            face_bytes = gen_img(char_prompt)
            if not face_bytes or len(face_bytes) < 100:
                logger.warning("Character Image Generation failed. Falling back to dummy bytes.")
                face_bytes = b"dummy_face_bytes"

            # Part 1 Generate
            logger.info("Generating Part 1...")
            vid1 = gen_vid(prompt_part1)
            vid1 = face_swap(vid1, face_bytes)
            aud1 = gen_aud(audio_text_part1, persona=persona)
            synced_vid1 = sync_vid(vid1, aud1)

            # Part 2 Generate
            logger.info("Generating Part 2...")
            vid2 = gen_vid(prompt_part2)
            vid2 = face_swap(vid2, face_bytes)
            aud2 = gen_aud(audio_text_part2, persona=persona)
            synced_vid2 = sync_vid(vid2, aud2)

            # B-Roll Generate
            b_roll_data = []
            for n in nodes:
                if n.get("type") == "broll_prompt":
                    b_prompt = n.get("value")
                    cached_bytes = get_cached_broll(b_prompt)
                    if cached_bytes:
                        b_bytes = cached_bytes
                    else:
                        b_bytes = gen_vid(b_prompt)
                        set_cached_broll(b_prompt, b_bytes)
                    b_roll_data.append({"start": n.get("start", 0), "end": n.get("end", 2.0), "clip_bytes": b_bytes})

            logger.info("Stitching Part 1 and Part 2 together...")
            editor = AutoEditor()

            import os as system_os
            from moviepy import VideoFileClip, concatenate_videoclips

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f1:
                f1.write(synced_vid1)
                p1_path = f1.name
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f2:
                f2.write(synced_vid2)
                p2_path = f2.name

            c1 = VideoFileClip(p1_path).resized((720, 1280)).with_fps(30)
            c2 = VideoFileClip(p2_path).resized((720, 1280)).with_fps(30)

            stitched_clip = concatenate_videoclips([c1, c2])

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as fs:
                stitched_path = fs.name

            stitched_clip.write_videofile(stitched_path, fps=30, codec="libx264", logger=None)

            with open(stitched_path, "rb") as f:
                final_base_bytes = f.read()

            system_os.remove(p1_path)
            system_os.remove(p2_path)
            system_os.remove(stitched_path)

            full_narration = f"{audio_text_part1} {audio_text_part2}"
            final_video_bytes = editor.apply_automated_factory_edit(final_base_bytes, b"", full_narration, b_roll_data)

            with open(video_path, "wb") as f:
                f.write(final_video_bytes)

        finally:
            if ctx: ctx.__exit__(None, None, None)

        return True
    except Exception as e:
        logger.error(f"Error executing Modal Node pipeline: {e}")
        return False

def main():
    logger.info("Starting God-Tier UGC Pipeline (Multi-Persona Network Setup)...")

    scraper = EcommerceScraper()
    niche = os.getenv("UGC_NICHE", "beauty")
    products = scraper.get_best_products(niche=niche)
    if not products:
        return

    top_product = products[0]

    tiktok_scraper = TikTokScraper()
    trend_data = tiktok_scraper.get_realtime_trends()

    evaluator = FYPEvaluator()
    swarm_blueprint = evaluator.swarm_evaluate_and_generate(top_product['product_name'], niche, trend_data)

    logger.info("Node-Based Swarm Blueprint Approved:")
    logger.info(json.dumps(swarm_blueprint, indent=2))

    personas = ["Host A", "Host B", "Host C"]
    uploader = SocialUploader()

    for i, persona in enumerate(personas):
        video_path = f"output_god_tier_ugc_variant_{i+1}.mp4"
        logger.info(f"Triggering AI Video Node Graph for {persona}...")

        success = generate_video_modal_remote(swarm_blueprint, video_path, persona=persona)

        if success:
            logger.info(f"God-Tier Video {persona} ready at: {video_path}")

            final_eval = evaluator.evaluate_final_video(swarm_blueprint, video_path)
            logger.info(f"Final Video {persona} FYP Evaluation Result:")
            try:
                if isinstance(final_eval, dict):
                    logger.info(json.dumps(final_eval, indent=2))
                else:
                    logger.info(final_eval)
            except Exception:
                logger.info(str(final_eval))

            tags = " ".join(swarm_blueprint.get("hashtags", []))
            caption = f"{swarm_blueprint['hook']} {tags} #fyp"

            uploader.schedule_upload(video_path, caption, variant_index=i)
        else:
            logger.warning(f"Pipeline execution failed for {persona}.")

    logger.info("Pipeline completed successfully. All variants awaiting scheduled drip-feed uploads.")

if __name__ == "__main__":
    main()
