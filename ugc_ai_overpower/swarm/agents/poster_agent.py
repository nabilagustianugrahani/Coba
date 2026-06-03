"""Poster Agent — posts videos to platforms with farm rotation.

Listens for: post_videos
Broadcasts: posting_done
"""
import logging, os, json, time, random
from typing import Optional

from swarm.base_agent import BaseAgent

log = logging.getLogger(__name__)


class PosterAgent(BaseAgent):
    name = "poster"

    def __init__(self):
        super().__init__(poll_interval=1.0, max_concurrent=2)

    def handle_post_videos(self, msg: dict) -> dict:
        payload = msg["payload"]
        campaign_id = payload.get("campaign_id", "")
        videos = payload.get("videos", [])
        platforms = payload.get("platforms", ["tiktok"])
        scripts = payload.get("scripts", [])

        if not videos:
            log.warning("[POST] No videos to post for %s", campaign_id)
            self._done(campaign_id, [])
            return {"campaign_id": campaign_id, "posted": 0}

        log.info("[POST] Posting %d videos to %s", len(videos), platforms)
        results = []

        for i, video_path in enumerate(videos):
            for platform in platforms:
                try:
                    result = self._post_one(video_path, platform, scripts[i] if i < len(scripts) else {})
                    results.append(result)
                except Exception as e:
                    log.warning("[POST] Failed %s → %s: %s", video_path, platform, e)
                    results.append({"video": video_path, "platform": platform, "success": False, "error": str(e)})

        log.info("[POST] Posted %d/%d for %s", sum(1 for r in results if r.get("success")), len(results), campaign_id)
        self._done(campaign_id, results)
        return {"campaign_id": campaign_id, "results": results}

    def _post_one(self, video_path: str, platform: str, script: dict) -> dict:
        if not os.path.exists(video_path):
            return {"video": video_path, "platform": platform, "success": False, "error": "file not found"}
        try:
            from ugc_ai_overpower.browser.posters import get_poster
            poster = get_poster(platform)
            payload = {
                "video_path": video_path,
                "script": script.get("script", ""),
                "hashtags": script.get("hashtags", []),
            }
            result = poster.post(payload)
            poster.cleanup()
            return {
                "video": video_path, "platform": platform,
                "success": result.get("success", False),
                "post_url": result.get("post_url", ""),
            }
        except Exception as e:
            return {"video": video_path, "platform": platform, "success": False, "error": str(e)}

    def _done(self, campaign_id: str, results: list):
        self.send("orchestrator", "posting_done", {
            "campaign_id": campaign_id,
            "results": results,
        })
