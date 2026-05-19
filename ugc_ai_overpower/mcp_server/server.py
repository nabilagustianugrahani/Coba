import sys
import os
import asyncio
import json

# Ensure modules can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from scraper.scraper import EcommerceScraper
from evaluator.evaluator import FYPEvaluator
from uploader.uploader import SocialUploader

# To trigger Modal remotely from MCP
import modal
from modal_gpu.modal_app import (
    app as modal_app,
    generate_base_video,
    face_swap_consistency,
    generate_voiceover,
    lip_sync_video
)
from video_processor.auto_editor import AutoEditor

# Initialize core components
scraper = EcommerceScraper()
evaluator = FYPEvaluator()
uploader = SocialUploader()

# Initialize MCP Server
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
            name="swarm_evaluate_script",
            description="Swarm AI evaluates and generates Hook, Narration, and Vlog Motion Prompt",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "niche": {"type": "string"}
                },
                "required": ["product_name", "niche"]
            }
        ),
        types.Tool(
            name="generate_god_tier_video",
            description="Trigger Modal B200 (H100) to generate Vlog-style AI Influencer Video with Auto-Captions remotely",
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
            description="Schedule video upload to TikTok/IG/YT",
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

    elif name == "swarm_evaluate_script":
        product_name = arguments.get("product_name")
        niche = arguments.get("niche", "general")
        result = evaluator.swarm_evaluate_and_generate(product_name, niche)
        return [types.TextContent(type="text", text=json.dumps(result))]

    elif name == "generate_god_tier_video":
        try:
            swarm_data = json.loads(arguments.get("swarm_json_string"))
            narration = swarm_data["narration"]
            motion_prompt = swarm_data["avatar_motion_prompt"]

            face_path = "assets/influencer_face.jpg"
            face_bytes = b"dummy_face_bytes"
            if os.path.exists(face_path):
                with open(face_path, "rb") as f:
                    face_bytes = f.read()

            if os.getenv("MODAL_TOKEN_ID") or os.path.exists(os.path.expanduser("~/.modal.toml")):
                with modal_app.run():
                    base_vid_bytes = generate_base_video.remote(motion_prompt)
                    swapped_vid_bytes = face_swap_consistency.remote(base_vid_bytes, face_bytes)
                    audio_bytes = generate_voiceover.remote(narration)
                    synced_vid_bytes = lip_sync_video.remote(swapped_vid_bytes, audio_bytes)
            else:
                base_vid_bytes = generate_base_video.local(motion_prompt)
                swapped_vid_bytes = face_swap_consistency.local(base_vid_bytes, face_bytes)
                audio_bytes = generate_voiceover.local(narration)
                synced_vid_bytes = lip_sync_video.local(swapped_vid_bytes, audio_bytes)

            editor = AutoEditor()
            final_video_bytes = editor.apply_hormozi_captions(synced_vid_bytes, audio_bytes, narration)

            video_path = "mcp_output.mp4"
            with open(video_path, "wb") as f:
                f.write(final_video_bytes)

            return [types.TextContent(type="text", text=f"Successfully generated B200 video remotely. Saved to {video_path}")]
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
