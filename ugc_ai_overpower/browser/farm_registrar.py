"""Auto-register farm accounts via temp mail + browser-use."""
import logging, json, time, random, string, asyncio
from typing import Optional
from datetime import datetime

from ugc_ai_overpower.browser.bu_agent import BUAgent, BUResult
from ugc_ai_overpower.browser.farm import AccountFarm
from ugc_ai_overpower.core.alerter import alerter
from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)


class TempMailClient:
    """Temporary email client for account registration.

    Uses smailpro.com API to create temp inboxes and check for
    verification emails.
    """

    def __init__(self):
        self._api_key = skynet_config.get("farm", "temp_mail_key", default="")
        self._base = skynet_config.get("farm", "temp_mail_api", default="https://api.smailpro.com")

    def create_inbox(self) -> Optional[dict]:
        """Create a temporary email inbox.

        Returns dict with 'email' and 'token' or None.
        """
        try:
            import requests
            resp = requests.post(
                f"{self._base}/v1/inboxes",
                headers={"Authorization": f"Bearer {self._api_key}"} if self._api_key else {},
                json={"lifetime": 30},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                log.info("Temp inbox created: %s", data.get("email"))
                return {"email": data["email"], "token": data.get("token", "")}
        except Exception as e:
            log.warning("Temp mail API failed: %s", e)
        return None

    def wait_for_code(self, inbox_token: str, sender_keyword: str = "verify",
                      timeout: int = 120) -> Optional[str]:
        """Wait for a verification email and extract the code.

        Args:
            inbox_token: Token from create_inbox().
            sender_keyword: Keyword to identify the verification email.
            timeout: Max wait time in seconds.

        Returns:
            Verification code string or None.
        """
        import requests
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = requests.get(
                    f"{self._base}/v1/inboxes/{inbox_token}/messages",
                    timeout=10,
                )
                if resp.status_code == 200:
                    messages = resp.json().get("messages", [])
                    for msg in messages:
                        if sender_keyword.lower() in msg.get("subject", "").lower():
                            code = self._extract_code(msg.get("body", ""))
                            if code:
                                return code
            except Exception:
                pass
            time.sleep(5)
        return None

    @staticmethod
    def _extract_code(body: str) -> Optional[str]:
        import re
        patterns = [
            r'(\d{4,6})',
            r'verification code[:\s]*(\w+)',
            r'kode verifikasi[:\s]*(\w+)',
            r'(\w{6,8}) is your',
        ]
        for p in patterns:
            match = re.search(p, body, re.I)
            if match:
                return match.group(1)
        return None


class BUFarmRegistrar(BUAgent):
    """Browser-use agent for auto-creating farm accounts.

    Flow:
    1. Generate random identity (name, username, password)
    2. Create temp email inbox
    3. Navigate to TikTok/IG signup page
    4. Fill registration form
    5. Check temp email for verification code
    6. Submit verification code
    7. Save cookies to farm profile
    """

    def __init__(self, headless: bool = True):
        super().__init__(headless=headless, model="gemini-2.5-flash")
        self._farm = AccountFarm()
        self._temp_mail = TempMailClient()

    async def register_tiktok(self, profile_name: str, username: str = None,
                              password: str = None) -> BUResult:
        """Create a new TikTok account and register it in the farm."""
        inbox = self._temp_mail.create_inbox()
        if not inbox:
            return BUResult(success=False, error="Failed to create temp inbox")

        email = inbox["email"]
        username = username or self._gen_username()
        password = password or self._gen_password()

        task = (
            f"1. Go to https://www.tiktok.com/signup\n"
            f"2. Choose 'Phone/Email' option\n"
            f"3. Select 'Email' tab\n"
            f"4. Enter email: {email}\n"
            f"5. Enter password: {password}\n"
            f"6. Click Sign Up\n"
            f"7. Wait for the verification code page\n"
            f"8. Once code is entered (manually or automatically), confirm account\n"
        )
        result = await self.run(task, sensitive=True)

        if result.success:
            self._farm.register("tiktok", profile_name)
            alerter.info(f"TikTok account registered: {profile_name} ({email})", "farm")
        else:
            alerter.warning(f"TikTok registration failed: {profile_name}: {result.error}", "farm")

        return result

    async def register_instagram(self, profile_name: str, email: str = None,
                                  username: str = None, password: str = None) -> BUResult:
        """Create a new Instagram account."""
        inbox = self._temp_mail.create_inbox()
        if not inbox:
            return BUResult(success=False, error="Failed to create temp inbox")

        email = email or inbox["email"]
        username = username or self._gen_username()
        password = password or self._gen_password()
        full_name = f"user_{random.randint(100, 999)}"

        task = (
            f"1. Go to https://www.instagram.com/accounts/signup\n"
            f"2. Enter email: {email}\n"
            f"3. Enter full name: {full_name}\n"
            f"4. Enter username: {username}\n"
            f"5. Enter password: {password}\n"
            f"6. Click Sign Up\n"
            f"7. Fill in birthday (January 1, 2000)\n"
            f"8. Complete the signup process\n"
        )
        result = await self.run(task, sensitive=True)

        if result.success:
            self._farm.register("instagram", profile_name)
            alerter.info(f"IG account registered: {profile_name} ({email})", "farm")

        return result

    async def validate_code(self, inbox_token: str, code: str, platform: str) -> BUResult:
        """Enter a verification code on the platform."""
        task = (
            f"1. On the verification code page, enter: {code}\n"
            f"2. Press Enter/Submit\n"
            f"3. Wait for account confirmation\n"
            f"4. Confirm the account is created\n"
        )
        return await self.run(task, sensitive=True)

    @staticmethod
    def _gen_username() -> str:
        adj = ["viral", "trend", "gemoy", "kece", "jago", "asik", "top", "seru"]
        nouns = ["skincare", "fashion", "daily", "beauty", "lifestyle", "tips"]
        return f"{random.choice(adj)}_{random.choice(nouns)}_{random.randint(100, 9999)}"

    @staticmethod
    def _gen_password(length: int = 12) -> str:
        chars = string.ascii_letters + string.digits + "!@#$"
        return "".join(random.choice(chars) for _ in range(length)) + "Aa1!"
