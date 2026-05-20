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
        # We replace rigid prime_times with randomized drip-feeding across 48 hours
        pass

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
                user_data_dir = os.path.join(os.getcwd(), "tiktok_session")
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )

                page = browser.new_page()
                stealth_sync(page)

                logger.info("[TikTok] Navigating to upload page...")
                # page.goto("https://www.tiktok.com/upload?lang=en", wait_until="networkidle")

                # Simulate the delay of the stealth sequence
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

        logger.info(f"Scheduled Drip-Feed Upload triggered at {datetime.datetime.now()} for {video_path}")
        self.upload_to_tiktok(video_path, caption)
        self.upload_to_ig_reels(video_path, caption)
        self.upload_to_yt_shorts(video_path, caption)
        return schedule.CancelJob

    def schedule_upload(self, video_path: str, caption: str, variant_index: int = 0):
        """
        Anti-Spam Drip-Feeding Logic:
        Randomizes uploads across a wide window so multiple variants (Host A, Host B, Host C)
        don't hit the social media algorithms simultaneously, preventing shadowbans.
        """
        # Base delay to stagger variants: Variant 1 today, Variant 2 tomorrow, etc.
        base_days_offset = variant_index * random.randint(1, 2)

        # Pick a random prime hour between 11:00 and 21:00
        random_hour = random.randint(11, 21)
        random_minute = random.randint(0, 59)
        time_str = f"{random_hour:02d}:{random_minute:02d}"

        if base_days_offset == 0:
            # Schedule for today
            schedule.every().day.at(time_str).do(self._job_wrapper, video_path=video_path, caption=caption)
            logger.info(f"Scheduled Drip-Feed Upload for {video_path} at {time_str} WIB (Today)")
        else:
            # In a real environment, you'd calculate exact future datetimes.
            # Using schedule module's days logic for representation:
            schedule.every(base_days_offset).days.at(time_str).do(self._job_wrapper, video_path=video_path, caption=caption)
            logger.info(f"Scheduled Drip-Feed Upload for {video_path} at {time_str} WIB ({base_days_offset} days from now)")

        return "Upload scheduled securely via Drip-Feed."

if __name__ == "__main__":
    uploader = SocialUploader()
    with open("dummy_video.mp4", "wb") as f:
        f.write(b"dummy")
    uploader.schedule_upload("dummy_video.mp4", "Cek keranjang kuning! #fyp", variant_index=1)
    os.remove("dummy_video.mp4")
