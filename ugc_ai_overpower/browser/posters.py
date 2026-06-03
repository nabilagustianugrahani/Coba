"""Multi‑platform poster implementations.

This module provides a pluggable ``BasePoster`` interface together with
concrete subclasses for TikTok, Instagram, and YouTube.  Each poster handles:

* Login via saved cookies or QR‑code scanning (TikTok).
* Content upload through a Playwright browser context.
* Graceful logout and resource cleanup.

A factory function ``get_poster`` is exported for callers who just want
a poster instance by platform name.
"""

from __future__ import annotations

import abc
import logging
import random
from pathlib import Path
from typing import Optional

from ugc_ai_overpower.browser.stealth import (
    create_browser,
    save_cookies,
    load_cookies,
    random_delay,
)
from ugc_ai_overpower.browser.cookies import CookieManager

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cookie directory – shared with stealth.py
# ---------------------------------------------------------------------------
_COOKIE_DIR = Path(__file__).parent / "cookies"

# ---------------------------------------------------------------------------
# Base poster
# ---------------------------------------------------------------------------

class BasePoster(abc.ABC):
    """Abstract interface for platform‑specific content poster classes.

    Every subclass **must** implement :meth:`login`, :meth:`post`, and
    :meth:`logout`.  The typical lifecycle is::

        poster = get_poster("tiktok")
        if not poster.login(stealth_context):
            poster.cleanup()
            return
        result = poster.post({"script": "...", "video_path": "..."})
        poster.logout()
        poster.cleanup()
    """

    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self._browser_ctx = None  # set during login / post
        self._cookie_profile = None
        self._cookie_mgr = None

    def set_cookie_profile(self, profile_name: str) -> None:
        self._cookie_profile = profile_name
        self._cookie_mgr = CookieManager()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def login(self, session) -> bool:
        """Authenticate on the target platform.

        The *session* argument can be a Playwright ``BrowserContext`` (if the
        caller already has one) or any other opaque token.  If the platform
        supports cookie‑based login the method will try to restore an existing
        session before falling back to interactive login (e.g. QR code).

        Returns ``True`` on success, ``False`` on failure.
        """

    @abc.abstractmethod
    def post(self, content: dict) -> dict:
        """Upload content to the platform.

        *content* is expected to contain (depending on the platform):

        * ``script`` – the text / caption for the post.
        * ``video_path`` – absolute path to a local video file.
        * ``hashtags`` – a list of tag strings (without the ``#``).
        * ``schedule`` – a ``datetime`` for delayed publishing (optional).

        Returns a dict with keys ``success`` (bool), ``post_url`` (str or
        ``None``), and ``error`` (str or ``None``).
        """

    @abc.abstractmethod
    def logout(self) -> None:
        """Clear the current session.  The poster may still be used after
        a subsequent :meth:`login` call."""

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Close the underlying Playwright context if one exists."""
        if self._browser_ctx is not None:
            try:
                self._browser_ctx.close()
            except Exception:
                log.exception("Error closing browser context")
            self._browser_ctx = None

    def _ensure_browser(self, headless: bool = True):
        """Return a fresh stealth context if we don't already have one."""
        if self._browser_ctx is None:
            self._browser_ctx = create_browser(headless=headless)
        return self._browser_ctx

    def _cookie_name(self) -> str:
        """Derive the cookie file name from ``platform_name``."""
        return f"{self.platform_name}_cookies"

    def _save_session(self) -> None:
        if self._browser_ctx is not None:
            save_cookies(self._browser_ctx, self._cookie_name())
            if self._cookie_mgr and self._cookie_profile:
                self._cookie_mgr.save(self.platform_name, self._cookie_profile)

    def _load_session(self) -> bool:
        if self._browser_ctx is not None:
            profile = self._cookie_profile or "default"
            if self._cookie_mgr:
                cookies = self._cookie_mgr.load(self.platform_name, profile)
                if cookies:
                    return True
            cookie_path = _COOKIE_DIR / f"{self._cookie_name()}.json"
            return cookie_path.is_file()
        return False


# ---------------------------------------------------------------------------
# TikTok poster
# ---------------------------------------------------------------------------

class TikTokPoster(BasePoster):
    """Post content to TikTok via ``tiktok.com/upload``.

    Login strategy:
    1. Try to load saved cookies.
    2. If no cookies are available, navigate to ``tiktok.com/login`` and
       wait for the user to scan the QR code (interactive mode).
    3. Save cookies for subsequent runs.
    """

    LOGIN_URL = "https://www.tiktok.com/login"
    UPLOAD_URL = "https://www.tiktok.com/upload"

    def __init__(self):
        super().__init__("tiktok")

    def login(self, session) -> bool:
        ctx = self._ensure_browser()
        page = ctx.new_page()
        try:
            # Attempt cookie‑based login first.
            if self._load_session():
                # Navigate to upload – if cookies are still valid we get
                # straight in.
                page.goto(self.UPLOAD_URL, timeout=30000)
                load_cookies(ctx, self._cookie_name())
                page.reload()
                # Check whether we are actually logged in.
                if not self._is_login_page(page):
                    log.info("TikTok: session restored from cookies")
                    return True

            # Interactive QR‑code login.
            log.info("TikTok: opening login page – scan QR code or enter credentials")
            page.goto(self.LOGIN_URL, timeout=60000)
            # Wait up to 120 s for the user to complete login.
            self._wait_for_login(page, timeout_seconds=120)
            self._save_session()
            return True
        except Exception as exc:
            log.exception("TikTok login failed")
            return False
        finally:
            page.close()

    def post(self, content: dict) -> dict:
        ctx = self._ensure_browser(headless=False)  # upload often needs the UI
        page = ctx.new_page()
        try:
            page.goto(self.UPLOAD_URL, timeout=30000)
            random_delay(1, 2)

            # ---- file upload -------------------------------------------------
            video_path = content.get("video_path")
            if not video_path:
                msg = "No video_path provided in content dict"
                log.error(msg)
                return {"success": False, "post_url": None, "error": msg}

            # The upload page shows a file input inside a special container.
            # Playwright can directly `set_input_files` on the visible input.
            file_input = page.locator('input[type="file"]').first
            file_input.set_input_files(video_path)
            random_delay(2, 4)  # wait for video processing

            # ---- caption & hashtags ------------------------------------------
            caption = content.get("script", "")
            hashtags = content.get("hashtags", [])
            if hashtags:
                caption += " " + " ".join(f"#{tag}" for tag in hashtags)
            caption_field = page.locator('[contenteditable="true"]').first
            if caption_field:
                caption_field.fill(caption)
                random_delay(1, 2)

            # ---- optional schedule -------------------------------------------
            # TikTok allows scheduling – if a datetime is provided, click the
            # schedule toggle and pick the date/time.  For simplicity we just
            # fall through to immediate posting here.

            # ---- submit ------------------------------------------------------
            post_btn = page.locator('button:has-text("Post")').first
            if post_btn:
                post_btn.click()
                random_delay(2, 4)

            # Wait for success indicator.
            success = page.wait_for_selector(
                ':text("posted")',
                timeout=30000,
            )
            if success:
                return {"success": True, "post_url": page.url, "error": None}

            return {"success": False, "post_url": None, "error": "Post button not found or upload failed"}
        except Exception as exc:
            log.exception("TikTok post failed")
            return {"success": False, "post_url": None, "error": str(exc)}
        finally:
            page.close()

    def logout(self) -> None:
        """Clear cookies for TikTok and restart the context."""
        if self._browser_ctx is not None:
            self._browser_ctx.clear_cookies()
        cookie_path = _COOKIE_DIR / f"{self._cookie_name()}.json"
        if cookie_path.exists():
            cookie_path.unlink()
        log.info("TikTok: session cleared")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_login_page(self, page) -> bool:
        """Heuristic: if the QR code or email/phone form is visible we are
        not logged in."""
        try:
            # Typical login form indicators
            return page.locator("#login-modal").is_visible(timeout=5000)
        except Exception:
            return False

    def _wait_for_login(self, page, timeout_seconds: int = 120) -> None:
        """Wait until the login modal disappears (or until the upload page
        is reachable)."""
        import time as _time
        deadline = _time.time() + timeout_seconds
        while _time.time() < deadline:
            random_delay(2, 3)
            try:
                page.goto(self.UPLOAD_URL, timeout=15000)
                if not self._is_login_page(page):
                    return
            except Exception:
                pass
        raise TimeoutError("TikTok login timed out after %d s" % timeout_seconds)


# ---------------------------------------------------------------------------
# Instagram poster
# ---------------------------------------------------------------------------

class InstagramPoster(BasePoster):
    """Post content to Instagram via the web interface.

    Because Instagram's web upload flow changes often, this implementation
    relies on a cookie‑based session that the user establishes out of band.

    Login: only cookie‑based (no interactive QR flow).
    Post: navigate to the create page, upload a photo/video, add caption.
    """

    LOGIN_URL = "https://www.instagram.com/accounts/login/"
    CREATE_URL = "https://www.instagram.com/create"

    def __init__(self):
        super().__init__("instagram")

    def login(self, session) -> bool:
        ctx = self._ensure_browser()
        page = ctx.new_page()
        try:
            page.goto("https://www.instagram.com", timeout=30000)
            load_cookies(ctx, self._cookie_name())
            page.reload()
            # Check if we landed on the feed (logged in).
            if page.locator("svg[aria-label='Home']").is_visible(timeout=5000):
                log.info("Instagram: session restored from cookies")
                return True
            log.warning("Instagram: no valid session – please configure cookies manually")
            return False
        except Exception as exc:
            log.exception("Instagram login failed")
            return False
        finally:
            page.close()

    def post(self, content: dict) -> dict:
        ctx = self._ensure_browser(headless=False)
        page = ctx.new_page()
        try:
            page.goto(self.CREATE_URL, timeout=30000)
            random_delay(1, 2)

            video_path = content.get("video_path")
            if not video_path:
                msg = "No video_path provided in content dict"
                log.error(msg)
                return {"success": False, "post_url": None, "error": msg}

            # Upload file.
            file_input = page.locator('input[type="file"]').first
            file_input.set_input_files(video_path)
            random_delay(3, 6)  # processing

            # Click "Next" (may appear twice – once for edit, once for details).
            next_btn = page.locator('div[role="button"]:has-text("Next")')
            if next_btn.is_visible(timeout=5000):
                next_btn.click()
                random_delay(1, 2)

            # Caption.
            caption_area = page.locator('[aria-label="Write a caption..."]').first
            if caption_area:
                caption_text = content.get("script", "")
                hashtags = content.get("hashtags", [])
                if hashtags:
                    caption_text += "\n" + "\n".join(f"#{tag}" for tag in hashtags)
                caption_area.fill(caption_text)
                random_delay(1, 2)

            # Share.
            share_btn = page.locator('div[role="button"]:has-text("Share")').first
            if share_btn:
                share_btn.click()
                random_delay(2, 3)

            # Wait for success.
            page.wait_for_selector(
                ':text("Your post has been shared.")',
                timeout=60000,
            )
            return {"success": True, "post_url": page.url, "error": None}
        except Exception as exc:
            log.exception("Instagram post failed")
            return {"success": False, "post_url": None, "error": str(exc)}
        finally:
            page.close()

    def logout(self) -> None:
        if self._browser_ctx is not None:
            self._browser_ctx.clear_cookies()
        cookie_path = _COOKIE_DIR / f"{self._cookie_name()}.json"
        if cookie_path.exists():
            cookie_path.unlink()
        log.info("Instagram: session cleared")


# ---------------------------------------------------------------------------
# YouTube poster
# ---------------------------------------------------------------------------

class YouTubePoster(BasePoster):
    """Post content to YouTube Studio.

    Login: cookie‑based only.  The user must have an active session in the
    cookie store.
    Post: navigate to ``studio.youtube.com/upload``, upload a video, fill
    in the details, and publish.
    """

    LOGIN_URL = "https://accounts.google.com/ServiceLogin"
    UPLOAD_URL = "https://studio.youtube.com/upload"

    def __init__(self):
        super().__init__("youtube")

    def login(self, session) -> bool:
        ctx = self._ensure_browser()
        page = ctx.new_page()
        try:
            page.goto("https://www.youtube.com", timeout=30000)
            load_cookies(ctx, self._cookie_name())
            page.reload()
            # Simple check – if the avatar is visible we are logged in.
            if page.locator("#avatar-btn").is_visible(timeout=5000):
                log.info("YouTube: session restored from cookies")
                return True
            log.warning("YouTube: no valid session – please configure cookies manually")
            return False
        except Exception as exc:
            log.exception("YouTube login failed")
            return False
        finally:
            page.close()

    def post(self, content: dict) -> dict:
        ctx = self._ensure_browser(headless=False)
        page = ctx.new_page()
        try:
            page.goto(self.UPLOAD_URL, timeout=45000)
            random_delay(1, 2)

            video_path = content.get("video_path")
            if not video_path:
                msg = "No video_path provided in content dict"
                log.error(msg)
                return {"success": False, "post_url": None, "error": msg}

            # The upload page has a hidden file input.
            file_input = page.locator('input[type="file"]').first
            file_input.set_input_files(video_path)

            # Wait for the upload to finish (progress bar disappears).
            page.wait_for_selector(
                "#progress-bar:not([style*='100'])",
                state="hidden",
                timeout=120000,
            )
            random_delay(2, 4)

            # Title & description.
            title_box = page.locator("#title-textbox").first
            if title_box:
                title_box.fill(content.get("hook", "Untitled"))
                random_delay(1, 2)

            desc_box = page.locator("#description-textbox").first
            if desc_box:
                caption_text = content.get("script", "")
                hashtags = content.get("hashtags", [])
                if hashtags:
                    caption_text += "\n" + "\n".join(f"#{tag}" for tag in hashtags)
                desc_box.fill(caption_text)
                random_delay(1, 2)

            # Set to "Unlisted" by default to avoid cluttering the channel.
            # Scroll to visibility settings.
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            random_delay(1, 2)
            unlisted_radio = page.locator('input[name="PUBLIC_EXPLICIT"][value="UNLISTED"]')
            if unlisted_radio.is_visible(timeout=3000):
                unlisted_radio.click()
                random_delay(1, 2)

            # Publish.
            publish_btn = page.locator("#publish-button").first
            if publish_btn:
                publish_btn.click()
                random_delay(2, 4)

            # Wait for the confirmation dialog.
            page.wait_for_selector(
                ':text("Video published")',
                timeout=60000,
            )
            return {"success": True, "post_url": page.url, "error": None}
        except Exception as exc:
            log.exception("YouTube post failed")
            return {"success": False, "post_url": None, "error": str(exc)}
        finally:
            page.close()

    def logout(self) -> None:
        if self._browser_ctx is not None:
            self._browser_ctx.clear_cookies()
        cookie_path = _COOKIE_DIR / f"{self._cookie_name()}.json"
        if cookie_path.exists():
            cookie_path.unlink()
        log.info("YouTube: session cleared")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PLATFORM_POSTER_MAP = {
    "tiktok": TikTokPoster,
    "instagram": InstagramPoster,
    "youtube": YouTubePoster,
}


def get_poster(platform: str) -> BasePoster:
    """Return a :class:`BasePoster` instance for *platform*.

    Supported platforms: ``"tiktok"``, ``"instagram"``, ``"youtube"``.

    Raises :class:`ValueError` for unknown platform names.
    """
    cls = _PLATFORM_POSTER_MAP.get(platform.lower())
    if cls is None:
        raise ValueError(
            f"Unknown platform: {platform!r}. "
            f"Supported: {list(_PLATFORM_POSTER_MAP)}"
        )
    return cls()
