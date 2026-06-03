"""Trend scraper — browser-use agent for trend discovery."""
import logging, json, re
from pathlib import Path
from typing import Optional
from datetime import datetime

from ugc_ai_overpower.browser.bu_agent import BUAgent, BUResult
from ugc_ai_overpower.core.alerter import alerter

log = logging.getLogger(__name__)


class BUScraperAgent(BUAgent):
    """Browser-use agent for trend & competitor intelligence.

    Capabilities:
    - Scrape TikTok trending hashtags
    - Scrape TikTok/IG discover page for viral content
    - Extract competitor content strategies
    - Find trending products in a niche
    """

    def __init__(self, headless: bool = True):
        super().__init__(headless=headless)
        self._output_dir = Path("/tmp") / "trends"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def trending_hashtags(self, niche: str, count: int = 20) -> BUResult:
        """Scrape trending hashtags for a niche from TikTok."""
        task = (
            f"1. Go to https://www.tiktok.com/tag/{niche}\n"
            f"2. Scroll down to load more content\n"
            f"3. Find the trending hashtags section or extract from post captions\n"
            f"4. Collect {count} unique trending hashtags\n"
            f"5. Format them as comma-separated list without #\n"
            f"6. Output ONLY the list: tag1, tag2, tag3"
        )
        result = await self.run(task)
        if result.success:
            hashtags = self._parse_hashtags(result.output)
            self._save("hashtags", niche, hashtags)
            result.output = str(hashtags[:count])
        return result

    async def viral_posts(self, niche: str, platform: str = "tiktok", count: int = 10) -> BUResult:
        """Find viral / high-engagement posts in a niche."""
        site = "tiktok.com" if platform == "tiktok" else "instagram.com"
        task = (
            f"1. Go to https://www.{site}/tag/{niche}\n"
            f"2. Scroll to find top posts (high view/like counts)\n"
            f"3. For each of the top {count} posts extract:\n"
            f"   - Hook / caption text\n"
            f"   - View/like count\n"
            f"   - Hashtags used\n"
            f"   - Post URL\n"
            f"4. Output in structured format\n"
        )
        result = await self.run(task)
        if result.success:
            self._save("viral", f"{platform}_{niche}", result.output)
        return result

    async def competitor_content(self, competitor_username: str, platform: str = "tiktok") -> BUResult:
        """Analyze a competitor's recent content strategy."""
        site = "tiktok.com" if platform == "tiktok" else "instagram.com"
        task = (
            f"1. Go to https://www.{site}/@{competitor_username}\n"
            f"2. Scroll through their recent posts\n"
            f"3. For each post note:\n"
            f"   - Caption/hook style\n"
            f"   - Hashtags they use\n"
            f"   - Engagement level\n"
            f"   - Content format (tutorial, review, etc)\n"
            f"4. Summarize their content strategy\n"
        )
        result = await self.run(task)
        if result.success:
            self._save("competitor", f"{platform}_{competitor_username}", result.output)
        return result

    async def trending_products(self, niche: str, platform: str = "shopee") -> BUResult:
        """Find trending products in a niche from e-commerce + social."""
        if platform == "shopee":
            task = (
                f"1. Go to https://shopee.co.id/search?keyword={niche}\n"
                f"2. Sort by 'Terlaris' (best selling)\n"
                f"3. Extract top 10 products:\n"
                f"   - Name\n"
                f"   - Price\n"
                f"   - Sold count\n"
                f"   - Rating\n"
                f"4. Output structured list\n"
            )
        else:
            task = (
                f"1. Go to https://tokopedia.com/search?q={niche}\n"
                f"2. Find trending products\n"
                f"3. Extract top 10 with prices and ratings\n"
            )
        result = await self.run(task)
        if result.success:
            self._save("products", f"{platform}_{niche}", result.output)
        return result

    def _parse_hashtags(self, text: str) -> list:
        tags = re.findall(r'#(\w+)', text)
        if not tags:
            tags = [t.strip() for t in text.replace("\n", ",").split(",") if t.strip()]
        return [t.lstrip("#").strip() for t in tags if t.strip()]

    def _save(self, category: str, key: str, data):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self._output_dir / f"{category}_{key}_{ts}.json"
        try:
            with open(path, "w") as f:
                json.dump({"category": category, "key": key, "data": data, "timestamp": ts}, f, indent=2)
            log.info("Trend data saved: %s", path)
        except Exception as e:
            log.warning("Failed to save trend data: %s", e)
