import asyncio
import json
import logging
import os
import tempfile
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Adjust import paths for testing
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.scraper import EcommerceScraper, TikTokScraper
from evaluator.evaluator import FYPEvaluator
from uploader.uploader import SocialUploader

import modal
from modal_gpu.modal_app import (
    app as modal_app,
    ModelGenerator
)
from video_processor.auto_editor import AutoEditor
from main import get_cached_broll, set_cached_broll, resolve_node_variables, generate_video_modal_remote

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
            video_path = "mcp_output.mp4"

            # Delegate generation directly to main.py function so MCP server stays aligned with main pipeline
            success = generate_video_modal_remote(swarm_data, video_path, persona="MCP Host")

            if success:
                return [types.TextContent(type="text", text=f"Successfully generated God-Tier B200 video remotely. Saved to {video_path}")]
            else:
                return [types.TextContent(type="text", text="Failed to generate God-Tier B200 video remotely.")]
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
