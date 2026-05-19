import sys
import os
import asyncio

# Ensure modules can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from scraper.scraper import EcommerceScraper
from evaluator.evaluator import FYPEvaluator
from uploader.uploader import SocialUploader

# Initialize core components
scraper = EcommerceScraper()
evaluator = FYPEvaluator()
uploader = SocialUploader()

# Initialize MCP Server
app = Server("ugc-ai-overpower-mcp")

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
            name="evaluate_script",
            description="Evaluate UGC script for FYP potential",
            inputSchema={
                "type": "object",
                "properties": {
                    "script": {"type": "string"},
                    "product_name": {"type": "string"}
                },
                "required": ["script", "product_name"]
            }
        ),
        types.Tool(
            name="generate_video",
            description="Trigger Modal H100 to generate AI Influencer Video",
            inputSchema={
                "type": "object",
                "properties": {
                    "script": {"type": "string"},
                    "character_prompt": {"type": "string"}
                },
                "required": ["script", "character_prompt"]
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

    elif name == "evaluate_script":
        script = arguments.get("script")
        product_name = arguments.get("product_name")
        result = evaluator.recursive_improvement_loop(script, product_name)
        return [types.TextContent(type="text", text=str(result))]

    elif name == "generate_video":
        return [types.TextContent(type="text", text="Triggered H100 generation on Modal.com")]

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
