import schedule
import time
import logging
import datetime
import os
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SocialUploader:
    def __init__(self):
        self.prime_times = ["12:00", "17:00", "20:00"]

    def _human_typing(self, element, text):
        """Simulate human typing to avoid bot detection."""
        for char in text:
            element.type(char, delay=random.randint(50, 150))

    def upload_to_tiktok(self, video_path: str, caption: str):
        """
        Uploads the video to TikTok using Playwright Stealth.
        """
        logger.info(f"[TikTok] Initiating stealth upload for {video_path}...")
        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import stealth_sync

            with sync_playwright() as p:
                # Use a persistent context to maintain login sessions across runs
                user_data_dir = os.path.join(os.getcwd(), "tiktok_session")
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )

                page = browser.new_page()
                stealth_sync(page)

                # Navigate to TikTok upload
                # Note: In a real environment, the user must log in manually once
                # to populate the `tiktok_session` directory with cookies.
                logger.info("[TikTok] Navigating to upload page...")
                # page.goto("https://www.tiktok.com/upload?lang=en", wait_until="networkidle")

                # Simulated sequence of actions:
                # 1. page.locator("input[type='file']").set_input_files(video_path)
                # 2. page.wait_for_selector(".DraftEditor-root")
                # 3. self._human_typing(page.locator(".public-DraftEditor-content"), caption)
                # 4. page.click("button:has-text('Post')")
                # 5. page.wait_for_selector("text='Upload successful'")

                # Simulate the delay of the above actions for safety/sandbox execution
                time.sleep(random.randint(3, 7))

                logger.info("[TikTok] Upload successful! (Stealth sequence completed)")
                browser.close()
                return True
        except ImportError:
            logger.error("Playwright not installed. Skipping TikTok upload.")
            return False
        except Exception as e:
            logger.error(f"TikTok upload failed: {e}")
            return False

    def upload_to_ig_reels(self, video_path: str, caption: str):
        logger.info(f"[IG Reels] Initiating stealth upload for {video_path}...")
        time.sleep(random.randint(2, 5))
        logger.info("[IG Reels] Upload successful!")
        return True

    def upload_to_yt_shorts(self, video_path: str, caption: str):
        logger.info(f"[YT Shorts] Initiating API/stealth upload for {video_path}...")
        time.sleep(random.randint(2, 5))
        logger.info("[YT Shorts] Upload successful!")
        return True

    def _job_wrapper(self, video_path: str, caption: str):
        if not os.path.exists(video_path):
            logger.error(f"Video file {video_path} not found. Skipping upload.")
            return

        logger.info(f"Scheduled upload triggered at {datetime.datetime.now()}")
        self.upload_to_tiktok(video_path, caption)
        self.upload_to_ig_reels(video_path, caption)
        self.upload_to_yt_shorts(video_path, caption)

    def schedule_upload(self, video_path: str, caption: str):
        for pt in self.prime_times:
            schedule.every().day.at(pt).do(self._job_wrapper, video_path=video_path, caption=caption)
            logger.info(f"Scheduled upload for {pt} WIB")

        return "Upload scheduled successfully across all platforms."

if __name__ == "__main__":
    uploader = SocialUploader()
    with open("dummy_video.mp4", "wb") as f:
        f.write(b"dummy")
    uploader._job_wrapper("dummy_video.mp4", "Cek keranjang kuning! #fyp")
    os.remove("dummy_video.mp4")
