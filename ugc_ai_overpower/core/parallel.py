"""Parallel batch processor — generate 50+ content pieces concurrently."""
import os, json, time, random, logging, concurrent.futures
from typing import Optional
from datetime import datetime

log = logging.getLogger(__name__)


class ParallelBatch:
    """Generate content in bulk using ThreadPoolExecutor."""

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self._stats = {"total": 0, "success": 0, "failed": 0, "time_ms": 0}

    def generate_batch(
        self,
        ai_router,
        product: str,
        influencers: list,
        platforms: list = None,
        count: int = 10,
        hooks: list = None,
        image_path: str = "",
    ) -> list:
        """Generate *count* content pieces in parallel.

        If *hooks* is provided they are cycled through; otherwise the AI
        generates a unique script for each task.
        """
        platforms = platforms or ["tiktok"]
        hooks = hooks or []
        start = time.time()
        results = []
        errors = []

        tasks = []
        for i in range(count):
            platform = random.choice(platforms)
            influencer = random.choice(influencers)
            hook = hooks[i % max(len(hooks), 1)] if hooks else ""
            tasks.append((i, platform, influencer, hook))

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_map = {}
            for idx, platform, influencer, hook in tasks:
                future = pool.submit(
                    self._generate_one, ai_router, product, platform, influencer, hook
                )
                future_map[future] = idx

            for future in concurrent.futures.as_completed(future_map):
                idx = future_map[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                    else:
                        errors.append((idx, "empty result"))
                except Exception as e:
                    errors.append((idx, str(e)))

        elapsed = int((time.time() - start) * 1000)
        self._stats = {
            "total": count,
            "success": len(results),
            "failed": len(errors),
            "time_ms": elapsed,
        }
        log.info("Batch: %d/%d generated in %.1fs", len(results), count, elapsed / 1000)

        return results

    def _generate_one(self, ai_router, product: str, platform: str, influencer: dict, hook: str) -> Optional[dict]:
        try:
            prompt = (
                f"Buat script UGC viral untuk {product} sebagai {influencer['name']} "
                f"({influencer.get('personality', 'casual')}). "
                f"Gaya: {influencer.get('voice_style', 'natural')}. Platform: {platform}. Bahasa Indonesia."
            )
            if hook:
                prompt += f"\nHook: {hook}"

            script = ai_router.chat(prompt)
            if not script:
                return None

            generated_hook = script.split("\n")[0][:60] if script else hook or f"Review {product}"

            hashtag_prompt = f"Generate 10 hashtag trending Indonesia untuk {product} di {platform}. Pisahkan dengan koma."
            hashtag_raw = ai_router.chat(hashtag_prompt)
            hashtags = [h.strip().lstrip("#") for h in hashtag_raw.split(",") if h.strip()]

            return {
                "influencer": influencer["name"],
                "platform": platform,
                "hook": generated_hook,
                "script": script,
                "hashtags": hashtags[:10],
            }
        except Exception as e:
            log.warning("Generate one failed: %s", e)
            return None

    def generate_videos_batch(
        self,
        video_composer,
        contents: list,
        product_image: str = "",
        max_workers: int = 4,
    ) -> list:
        """Generate videos for multiple scripts in parallel."""
        start = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {}
            for i, content in enumerate(contents):
                future = pool.submit(
                    self._generate_video_one, video_composer, content, product_image
                )
                future_map[future] = i

            results = list(contents)  # copy, will update in place
            for future in concurrent.futures.as_completed(future_map):
                idx = future_map[future]
                try:
                    video_path = future.result()
                    if video_path:
                        results[idx]["video_path"] = video_path
                except Exception as e:
                    log.warning("Video gen failed for item %d: %s", idx, e)

        elapsed = int((time.time() - start) * 1000)
        log.info("Videos: %d generated in %.1fs",
                 sum(1 for c in results if c.get("video_path")), elapsed / 1000)
        return results

    def _generate_video_one(self, video_composer, content: dict, product_image: str) -> Optional[str]:
        import asyncio
        try:
            path = asyncio.run(video_composer.create_ugc_video(
                script=content.get("script", ""),
                influencer=content.get("influencer", "default"),
                product_image=product_image,
            ))
            return path
        except Exception as e:
            log.warning("Video gen error: %s", e)
            return None

    def get_stats(self) -> dict:
        return dict(self._stats)
