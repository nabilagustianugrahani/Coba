"""Video Producer Agent — renders videos, TTS, thumbnails.

Listens for: render_videos
Broadcasts: videos_ready
"""
import logging, os, concurrent.futures, json
from pathlib import Path

from swarm.base_agent import BaseAgent
from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)


class VideoProducerAgent(BaseAgent):
    name = "video_producer"

    def __init__(self, output_dir: str = None):
        super().__init__(poll_interval=1.0, max_concurrent=1)
        self.output_dir = output_dir or skynet_config.get("paths", "output_dir", default="output/videos")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def handle_render_videos(self, msg: dict) -> dict:
        payload = msg["payload"]
        campaign_id = payload.get("campaign_id", "")
        scripts = payload.get("scripts", [])
        product_image = payload.get("product_image", "")
        face_image = payload.get("face_image", "")
        niche = payload.get("niche", "general")
        theme = payload.get("theme", "default")

        if not scripts:
            log.warning("[VP] No scripts to render for %s", campaign_id)
            self._done(campaign_id, [])
            return {"campaign_id": campaign_id, "videos": 0}

        log.info("[VP] Rendering %d videos for %s", len(scripts), campaign_id)
        use_editor = skynet_config.get("avatar", "use_video_editor", default=True)

        videos = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(scripts))) as pool:
            futures = {}
            for i, s in enumerate(scripts):
                fut = pool.submit(
                    self._render_one, s, product_image, face_image, niche, theme, use_editor
                )
                futures[fut] = i

            for fut in concurrent.futures.as_completed(futures):
                idx = futures[fut]
                try:
                    path = fut.result()
                    if path:
                        scripts[idx]["video_path"] = path
                        videos.append(path)
                except Exception as e:
                    log.warning("[VP] Video %d failed: %s", idx, e)

        log.info("[VP] %d videos ready for %s", len(videos), campaign_id)
        self._done(campaign_id, videos)
        return {"campaign_id": campaign_id, "videos": len(videos)}

    def _render_one(self, script, product_image, face_image, niche, theme, use_editor) -> str:
        if use_editor:
            try:
                from ugc_ai_overpower.gpu.video_editor import UGCVideoEditor
                editor = UGCVideoEditor(theme=theme)
                return editor.render(
                    script=script.get("script", ""),
                    product_image=product_image or None,
                    face_image=face_image or None,
                    gender=script.get("gender", "male"),
                    niche=niche,
                )
            except Exception as e:
                log.warning("[VP] Editor failed, fallback: %s", e)

        try:
            from ugc_ai_overpower.gpu.video_composer import VideoComposer
            vc = VideoComposer(theme)
            return vc.create_ugc_video(
                script=script.get("script", ""),
                influencer=script.get("influencer", "creator"),
                product_image=product_image or None,
                niche=niche,
                gender=script.get("gender", "male"),
            )
        except Exception as e:
            log.error("[VP] All renderers failed: %s", e)
            return ""

    def _done(self, campaign_id: str, videos: list):
        self.send("orchestrator", "videos_ready", {
            "campaign_id": campaign_id,
            "videos": videos,
        })
