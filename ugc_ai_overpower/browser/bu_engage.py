"""Auto engage — browser-use agent for like, comment, follow at scale."""
import logging, random
from typing import Optional

from ugc_ai_overpower.browser.bu_agent import BUAgent, BUResult
from ugc_ai_overpower.core.alerter import alerter

log = logging.getLogger(__name__)


class BUEngageAgent(BUAgent):
    """Browser-use agent for social media engagement automation.

    Capabilities:
    - Scroll feed (TikTok FYP, IG explore, YT shorts)
    - Like posts matching niche keywords
    - Comment on posts with generated comments
    - Follow creators in target niche
    """

    COMMENT_TEMPLATES = {
        "skincare": [
            "wajib coba nih buat yang belum",
            "udah pake ini? gue baru tau",
            "hasilnya beneran kayak gitu?",
            "ihhh pengen coba!",
            "recommended banget gak?",
            "udah pake berapa lama?",
            "yang ini cocok buat kulit berminyak?",
        ],
        "fashion": [
            "outfitnya keren kak!",
            "cocok buat daily look",
            "dimana belinya kak?",
            "recomended banget!",
            "size chartnya gimana?",
            "bahan nyaman gak?",
            "pengen punya jugaaa",
        ],
        "food": [
            "kok kayanya enak banget",
            "resepnya dong kak!",
            "halal semua kak?",
            "dimana alamatnya?",
            "harganya berapa?",
        ],
        "tech": [
            "worth it gak belinya?",
            "speknya gimana?",
            "udah pake berapa lama?",
            "ada minusnya gak?",
            "rivalnya apa aja?",
        ],
        "general": [
            "nice!",
            "mantap",
            "keren abis",
            "gas poll!",
            "saved buat referensi",
            "share dong infonya",
        ],
    }

    def __init__(self, headless: bool = True):
        super().__init__(headless=headless)

    async def scroll_tiktok_fyp(self, count: int = 20, niche: str = "general") -> BUResult:
        """Scroll TikTok FYP, optionally engage with posts."""
        task = (
            f"1. Go to https://www.tiktok.com\n"
            f"2. Scroll through the FYP feed {count} times\n"
            f"3. For each post, check if it's about '{niche}'\n"
            f"4. If it matches: like the post\n"
            f"5. Continue scrolling\n"
            f"6. Report how many posts were liked\n"
        )
        return await self.run(task)

    async def scroll_instagram_explore(self, count: int = 15, niche: str = "general") -> BUResult:
        """Scroll Instagram explore page."""
        task = (
            f"1. Go to https://www.instagram.com/explore\n"
            f"2. Scroll through {count} posts\n"
            f"3. Like posts related to '{niche}'\n"
            f"4. Scroll at a natural pace (1-2 seconds between scrolls)\n"
            f"5. Report how many posts were liked\n"
        )
        return await self.run(task)

    async def like_comment_post(self, post_url: str, niche: str = "general") -> BUResult:
        """Like and comment on a specific post."""
        comment = random.choice(self.COMMENT_TEMPLATES.get(niche, self.COMMENT_TEMPLATES["general"]))
        task = (
            f"1. Go to {post_url}\n"
            f"2. Wait for the post to load\n"
            f"3. Click the like/heart button\n"
            f"4. Type this comment: '{comment}'\n"
            f"5. Post the comment by pressing Enter\n"
            f"6. Confirm the comment was posted\n"
        )
        return await self.run(task)

    async def follow_creator(self, profile_url: str) -> BUResult:
        """Follow a creator's profile."""
        task = (
            f"1. Go to {profile_url}\n"
            f"2. Wait for the profile to load\n"
            f"3. Click the Follow button\n"
            f"4. Confirm the button changed to Following\n"
        )
        return await self.run(task)

    async def batch_engage(self, niche: str, platform: str = "tiktok",
                           likes: int = 20, follows: int = 5, comments: int = 3) -> dict:
        """Full engagement run: scroll → like → follow → comment.

        Args:
            niche: Target niche keywords.
            platform: 'tiktok' or 'instagram'.
            likes: Number of posts to like.
            follows: Number of creators to follow.
            comments: Number of comments to post.

        Returns:
            Dict with results per action.
        """
        results = {}

        if platform == "tiktok":
            r = await self.scroll_tiktok_fyp(likes, niche)
        else:
            r = await self.scroll_instagram_explore(likes, niche)
        results["scroll"] = {"success": r.success, "likes": likes}

        if follows > 0:
            r = await self._auto_follow(follows)
            results["follows"] = {"success": r.success, "count": follows}

        if comments > 0:
            r = await self._auto_comment(comments, niche)
            results["comments"] = {"success": r.success, "count": comments}

        summary = f"Engage {platform}/{niche}: {likes} likes, {follows} follows, {comments} comments"
        if r.success:
            alerter.info(summary, "engage")
        else:
            alerter.warning(f"Engage partial: {summary}", "engage")

        return results

    async def _auto_follow(self, count: int) -> BUResult:
        task = (
            f"1. On the current feed, find creators posting relevant content\n"
            f"2. Visit their profiles (click username)\n"
            f"3. Click the Follow button\n"
            f"4. Go back to the feed\n"
            f"5. Repeat for {count} different creators\n"
            f"6. Report how many were followed\n"
        )
        return await self.run(task)

    async def _auto_comment(self, count: int, niche: str) -> BUResult:
        templates = self.COMMENT_TEMPLATES.get(niche, self.COMMENT_TEMPLATES["general"])
        comments_text = ", ".join([f"'{c}'" for c in random.sample(templates, min(count, len(templates)))])
        task = (
            f"1. On the current feed, click on the first {count} posts\n"
            f"2. Type these comments respectively: {comments_text}\n"
            f"3. Post each comment (Enter)\n"
            f"4. Go back to the feed after each\n"
            f"5. Report how many comments were posted\n"
        )
        return await self.run(task)

    def batch_engage_sync(self, niche: str, **kwargs) -> dict:
        import asyncio
        return asyncio.run(self.batch_engage(niche, **kwargs))
