import sys
import os
import asyncio
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from scraper.scraper import EcommerceScraper, TikTokScraper
from evaluator.evaluator import FYPEvaluator
from uploader.uploader import SocialUploader

import modal
from modal_gpu.modal_app import (
    app as modal_app,
    ModelGenerator
)
from video_processor.auto_editor import AutoEditor
from main import get_face_bytes, get_cached_broll, set_cached_broll, resolve_node_variables

scraper = EcommerceScraper()
tiktok_scraper = TikTokScraper()
evaluator = FYPEvaluator()
uploader = SocialUploader()

app = Server("ugc-ai-overpower-b200-mcp")

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="scrape_products",
            description="Scrape top affiliate products from Shopee/Tokopedia",
            inputSchema={
                "type": "object",
                "properties": {
                    "niche": {"type": "string"}
                },
                "required": ["niche"]
            }
        ),
        types.Tool(
            name="hijack_tiktok_trends",
            description="Extract live trending hooks and hashtags from TikTok via Stealth Browser",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="swarm_evaluate_script",
            description="Swarm AI evaluates and generates Node-Based Workflow (including Extend-and-Stitch) using live trends",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "niche": {"type": "string"},
                    "trend_data_json": {"type": "string"}
                },
                "required": ["product_name", "niche"]
            }
        ),
        types.Tool(
            name="generate_god_tier_video",
            description="Trigger Stateful Modal B200 to execute the Node-Based Workflow Video Generation",
            inputSchema={
                "type": "object",
                "properties": {
                    "swarm_json_string": {"type": "string"}
                },
                "required": ["swarm_json_string"]
            }
        ),
        types.Tool(
            name="evaluate_final_video",
            description="Recursive loop evaluation for FYP readiness of the final assembled video",
            inputSchema={
                "type": "object",
                "properties": {
                    "swarm_json_string": {"type": "string"},
                    "video_path": {"type": "string"}
                },
                "required": ["swarm_json_string", "video_path"]
            }
        ),
        types.Tool(
            name="schedule_upload",
            description="Schedule video upload to TikTok/IG/YT using Stealth browser",
            inputSchema={
                "type": "object",
                "properties": {
                    "video_path": {"type": "string"},
                    "caption": {"type": "string"}
                },
                "required": ["video_path", "caption"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "scrape_products":
        niche = arguments.get("niche")
        result = scraper.get_best_products(niche)
        return [types.TextContent(type="text", text=str(result))]

    elif name == "hijack_tiktok_trends":
        result = tiktok_scraper.get_realtime_trends()
        return [types.TextContent(type="text", text=json.dumps(result))]

    elif name == "swarm_evaluate_script":
        product_name = arguments.get("product_name")
        niche = arguments.get("niche", "general")
        trend_str = arguments.get("trend_data_json", "")
        trend_data = json.loads(trend_str) if trend_str else None

        result = evaluator.swarm_evaluate_and_generate(product_name, niche, trend_data)
        return [types.TextContent(type="text", text=json.dumps(result))]

    elif name == "generate_god_tier_video":
        try:
            swarm_data = json.loads(arguments.get("swarm_json_string"))
            nodes = swarm_data.get("nodes", [])
            graph = swarm_data.get("execution_graph", {})
            template = swarm_data.get("template_type", "01_talking_head")

            face_bytes = get_face_bytes()
            generator = ModelGenerator()

            is_remote = os.getenv("MODAL_TOKEN_ID") or os.path.exists(os.path.expanduser("~/.modal.toml"))
            final_video_bytes = None

            ctx = modal_app.run() if is_remote else None

            try:
                if ctx: ctx.__enter__()

                if template == "05_extend_and_stitch":
                    prompt_part1 = resolve_node_variables(graph.get("generate_part1_video", ""), nodes)
                    prompt_part2 = resolve_node_variables(graph.get("generate_part2_video", ""), nodes)
                    audio_text_part1 = resolve_node_variables(graph.get("generate_audio_part1", ""), nodes)
                    audio_text_part2 = resolve_node_variables(graph.get("generate_audio_part2", ""), nodes)

                    gen_vid = generator.generate_base_video.remote if is_remote else generator.generate_base_video.local
                    gen_aud = generator.generate_voiceover_f5.remote if is_remote else generator.generate_voiceover_f5.local
                    sync_vid = generator.lip_sync_video.remote if is_remote else generator.lip_sync_video.local
                    face_swap = generator.face_swap_consistency.remote if is_remote else generator.face_swap_consistency.local

                    vid1 = gen_vid(prompt_part1)
                    vid1 = face_swap(vid1, face_bytes)
                    aud1 = gen_aud(audio_text_part1)
                    synced_vid1 = sync_vid(vid1, aud1)

                    vid2 = gen_vid(prompt_part2)
                    vid2 = face_swap(vid2, face_bytes)
                    aud2 = gen_aud(audio_text_part2)
                    synced_vid2 = sync_vid(vid2, aud2)

                    editor = AutoEditor()

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

                    import tempfile
                    import os as system_os
                    from moviepy import VideoFileClip, concatenate_videoclips

                    p1_path = tempfile.mktemp(suffix=".mp4")
                    p2_path = tempfile.mktemp(suffix=".mp4")

                    with open(p1_path, "wb") as f: f.write(synced_vid1)
                    with open(p2_path, "wb") as f: f.write(synced_vid2)

                    c1 = VideoFileClip(p1_path).resized((720, 1280)).with_fps(30)
                    c2 = VideoFileClip(p2_path).resized((720, 1280)).with_fps(30)

                    stitched_clip = concatenate_videoclips([c1, c2])
                    stitched_path = tempfile.mktemp(suffix=".mp4")
                    stitched_clip.write_videofile(stitched_path, fps=30, codec="libx264", logger=None)

                    with open(stitched_path, "rb") as f:
                        final_base_bytes = f.read()

                    system_os.remove(p1_path)
                    system_os.remove(p2_path)
                    system_os.remove(stitched_path)

                    full_narration = f"{audio_text_part1} {audio_text_part2}"
                    final_video_bytes = editor.apply_automated_factory_edit(final_base_bytes, b"", full_narration, b_roll_data)

                else:
                    return [types.TextContent(type="text", text=f"Template {template} logic not fully built.")]

                video_path = "mcp_output.mp4"
                with open(video_path, "wb") as f:
                    f.write(final_video_bytes)

                return [types.TextContent(type="text", text=f"Successfully generated God-Tier B200 video remotely. Saved to {video_path}")]
            finally:
                if ctx: ctx.__exit__(None, None, None)

        except Exception as e:
            return [types.TextContent(type="text", text=f"Failed to generate video: {str(e)}")]

    elif name == "evaluate_final_video":
        try:
            swarm_data = json.loads(arguments.get("swarm_json_string"))
            video_path = arguments.get("video_path")
            result = evaluator.evaluate_final_video(swarm_data, video_path)
            return [types.TextContent(type="text", text=json.dumps(result))]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Evaluation failed: {str(e)}")]

    elif name == "schedule_upload":
        video_path = arguments.get("video_path")
        caption = arguments.get("caption")
        result = uploader.schedule_upload(video_path, caption)
        return [types.TextContent(type="text", text=str(result))]

    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
