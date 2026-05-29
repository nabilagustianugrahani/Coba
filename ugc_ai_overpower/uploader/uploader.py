import logging
import time
from datetime import datetime, timedelta
import random
import os
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SocialUploader:
    def __init__(self):
        # Local endpoint where the AiToEarn CLI/Server is running on the VPS
        self.aitoearn_endpoint = os.getenv("AITOEARN_ENDPOINT", "http://localhost:3000/api/publish")

    def _execute_aitoearn_upload(self, video_path: str, caption: str):
        """
        Delegates the physical uploading process to the AiToEarn framework.
        AiToEarn handles the multi-platform distribution (Douyin, Xiaohongshu, Kuaishou, TikTok)
        and bypasses anti-bot measures using its own mature infrastructure.
        """
        logger.info(f"[AiToEarn Dispatcher] Transferring video {video_path} to AiToEarn ecosystem...")

        if not os.path.exists(video_path):
            logger.error(f"[AiToEarn Dispatcher] Video file {video_path} not found. Aborting transfer.")
            return False

        try:
            # Payload tailored for AiToEarn API structure
            payload = {
                "title": caption[:50], # Short title
                "description": caption,
                "platforms": ["douyin", "xiaohongshu", "kuaishou", "tiktok"],
                "publish_type": "now"
            }

            with open(video_path, 'rb') as video_file:
                files = {
                    'video': (os.path.basename(video_path), video_file, 'video/mp4')
                }

                logger.info(f"[AiToEarn Dispatcher] Sending multipart payload to {self.aitoearn_endpoint}...")

                # We use a timeout to prevent the pipeline from hanging if AiToEarn is down
                response = requests.post(
                    self.aitoearn_endpoint,
                    data=payload,
                    files=files,
                    timeout=120
                )

                if response.status_code == 200:
                    logger.info(f"[AiToEarn Dispatcher] SUCCESS! Video handed over to AiToEarn for multi-platform blast.")
                    return True
                else:
                    logger.warning(f"[AiToEarn Dispatcher] Failed to transfer. HTTP {response.status_code}: {response.text}")
                    return False

        except requests.exceptions.ConnectionError:
            logger.warning(f"[AiToEarn Dispatcher] Connection refused. Is the AiToEarn server running at {self.aitoearn_endpoint}? (Running in Simulation Mode)")
            return False
        except Exception as e:
            logger.error(f"[AiToEarn Dispatcher] Unexpected error during transfer: {e}")
            return False

    def schedule_upload(self, video_path: str, caption: str, variant_index: int = 0):
        """
        Schedules a drip-feed upload.
        """
        delay_minutes = random.randint(10, 60) + (variant_index * 120)
        upload_time = datetime.now() + timedelta(minutes=delay_minutes)
        time_str = upload_time.strftime("%H:%M")

        logger.info(f"Scheduled Multi-Platform Blast via AiToEarn for {video_path} at {time_str} WIB")

        # In a real daemon environment (e.g., using Celery or APScheduler), this would be queued.
        # For the Skynet pipeline flow, we execute immediately or simulate.
        self._execute_aitoearn_upload(video_path, caption)

        return {"status": "scheduled", "time": time_str, "engine": "AiToEarn"}

if __name__ == "__main__":
    uploader = SocialUploader()
    uploader.schedule_upload("dummy.mp4", "Skincare rahasia #fyp #douyin", 0)
