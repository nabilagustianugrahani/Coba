# UGC AI Overpower - Affiliate Influencer Generator

This project is an overpowered, zero-cost (where possible) AI UGC Influencer generator tailored for Indonesian e-commerce (Shopee, Tokopedia). It leverages Modal.com for GPU workloads (B200/H100/A100), open-source AI models for consistent character generation and animation, and an MCP (Model Context Protocol) server for easy integration with agents like Claude Code.

## Features
- **Scraper**: Autonomous product scraping for Shopee/Tokopedia based on niche and highest commission.
- **Modal GPU Engine**: High-end GPU processing for AI generation using open-source models.
  - *Consistent Character*: SDXL / Flux with LoRA or IP-Adapter.
  - *Voice*: Edge TTS (Zero cost).
  - *Animation*: LivePortrait for smooth, realistic lip-sync and facial expressions.
- **Video Processor**: Assembles assets into a standard TikTok format (9:16).
- **AI Evaluator**: A recursive loop that critiques the script and generated video for "FYP" potential.
- **Auto Uploader**: Publishes to TikTok/Instagram Reels/YouTube Shorts during active hours.
- **MCP Server**: Lightweight server exposing these tools to any MCP-compatible agent.
