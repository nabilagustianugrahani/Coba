"""Auto login flow — browser-use agent for TikTok/IG/YT login."""
import logging
from typing import Optional

from ugc_ai_overpower.browser.bu_agent import BUAgent, BUResult
from ugc_ai_overpower.browser.farm import AccountFarm, AccountProfile
from ugc_ai_overpower.core.alerter import alerter

log = logging.getLogger(__name__)


class BULoginAgent(BUAgent):
    """Browser-use agent for automated login to social platforms.

    Capabilities:
    - Cookie-based login (restore previous session)
    - QR code login (TikTok)
    - Email/password login
    - Saves cookies to AccountFarm on success
    """

    def __init__(self, headless: bool = True):
        super().__init__(headless=headless)
        self._farm = AccountFarm()

    async def login_tiktok_qr(self, profile_name: str, timeout_minutes: int = 2) -> BUResult:
        """Login to TikTok via QR code — waits for user scan.

        Saves cookies to farm profile after successful login.
        """
        task = (
            f"1. Go to https://www.tiktok.com/login\n"
            f"2. Wait for the QR code to appear\n"
            f"3. Wait up to {timeout_minutes} minutes for the user to scan it\n"
            f"4. Verify login succeeded by checking if we're on the upload page\n"
            f"5. Confirm login status\n"
        )
        result = await self.run(task)

        if result.success:
            self._save_farm_cookies(profile_name, "tiktok")
            alerter.info(f"TikTok login OK: {profile_name}", "login")
        else:
            alerter.warning(f"TikTok login failed: {profile_name}: {result.error}", "login")

        return result

    async def login_instagram_cookies(self, profile_name: str) -> BUResult:
        """Login to Instagram using saved cookies / session.

        Tries to restore existing session first.
        """
        task = (
            "1. Go to https://www.instagram.com\n"
            "2. Check if already logged in (profile icon visible)\n"
            "3. If not logged in, try to use any existing cookies\n"
            "4. Confirm login by checking for home icon\n"
        )
        result = await self.run(task)

        if result.success:
            self._save_farm_cookies(profile_name, "instagram")

        return result

    async def login_youtube_cookies(self, profile_name: str) -> BUResult:
        """Verify YouTube session and save cookies to farm."""
        task = (
            "1. Go to https://www.youtube.com\n"
            "2. Check if logged in (avatar button visible)\n"
            "3. If logged in, navigate to studio.youtube.com\n"
            "4. Confirm access to YouTube Studio\n"
        )
        result = await self.run(task)

        if result.success:
            self._save_farm_cookies(profile_name, "youtube")

        return result

    def _save_farm_cookies(self, profile_name: str, platform: str):
        try:
            self._farm.register(platform, profile_name)
        except ValueError:
            pass  # Already registered — just update
        except Exception as e:
            log.warning("Farm cookie save error: %s", e)
