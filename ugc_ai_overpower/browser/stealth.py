"""Playwright stealth utilities.

This module provides helpers to create a Playwright browser context with common
anti‑detection measures (user‑agent rotation, viewport spoofing, geolocation
spoofing, and proxy rotation). It also supplies a simple ``random_delay``
function that can be used to mimic human interaction timing.

The implementation is intentionally lightweight – it does not depend on any
external stealth library. Instead we inject a minimal ``stealth.min.js`` script
that applies a handful of well‑known tricks (navigator.webdriver, languages,
plugins, etc.). The script content is stored in the ``_STEALTH_JS`` constant
so the file is self‑contained.

Configuration (proxy pool, user‑agents, etc.) is read from the project's
``config.yaml`` which lives at the project root. The relevant section looks
like::

    proxy:
      enabled: true
      pool:
        - "http://user:pass@proxy1.example.com:3128"
        - "http://proxy2.example.com:8080"
      rotation_strategy: "round-robin"

If proxy support is disabled or the pool is empty the ``create_browser``
function returns a normal context without a proxy.
"""

import json
import random
import time
from pathlib import Path
from typing import Optional, List

from playwright.sync_api import sync_playwright, Browser, BrowserContext

# ---------------------------------------------------------------------------
# Minimal stealth script – based on the popular ``playwright-stealth`` package.
# It overwrites a few properties that are commonly checked by anti‑bot
# services. The script runs in the page before any navigation.
# ---------------------------------------------------------------------------
_STEALTH_JS = """
(() => {
  // Pass the Chrome test.
  Object.defineProperty(navigator, 'webdriver', { get: () => false });
  // Pass the languages test.
  Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
  // Pass the plugins test.
  Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
  });
  // Pass the Chrome app test.
  window.chrome = {
    runtime: {},
    // add more properties if needed
  };
})();
"""

# ---------------------------------------------------------------------------
# Helpers to load configuration
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parents[2] / "config.yaml"

def _load_config() -> dict:
    try:
        import yaml
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        # If yaml is not available or config missing, return empty config.
        return {}

_config_cache: Optional[dict] = None

def _get_config() -> dict:
    global _config_cache
    if _config_cache is None:
        _config_cache = _load_config()
    return _config_cache

# ---------------------------------------------------------------------------
# Proxy handling
# ---------------------------------------------------------------------------
_proxy_index = 0

def _select_proxy() -> Optional[str]:
    cfg = _get_config().get("proxy", {})
    if not cfg.get("enabled", False):
        return None
    pool: List[str] = cfg.get("pool", [])
    if not pool:
        return None
    # Simple round‑robin rotation – shared module‑level index.
    global _proxy_index
    proxy = pool[_proxy_index % len(pool)]
    _proxy_index += 1
    return proxy

# ---------------------------------------------------------------------------
# User‑agent rotation – a short list of common desktop UA strings.
# ---------------------------------------------------------------------------
_UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

def _random_user_agent() -> str:
    return random.choice(_UA_LIST)

# ---------------------------------------------------------------------------
# Random delay – mimics human typing / mouse movement latency.
# ---------------------------------------------------------------------------
def random_delay(min_seconds: float = 0.1, max_seconds: float = 0.5) -> None:
    """Sleep for a random duration between *min_seconds* and *max_seconds*.

    The default values are tuned for short human‑like pauses (100‑500 ms).
    """
    time.sleep(random.uniform(min_seconds, max_seconds))

# ---------------------------------------------------------------------------
# Browser factory
# ---------------------------------------------------------------------------
def create_browser(headless: bool = True) -> BrowserContext:
    """Create a Playwright ``BrowserContext`` with stealth settings.

    The function performs the following steps:

    1. Starts Playwright (Chromium) with an optional proxy.
    2. Sets a random user‑agent and viewport.
    3. Injects ``_STEALTH_JS`` into every new page.
    4. Spoofs a generic geolocation (you can extend this to read from the
       config if desired).

    The returned object is a **BrowserContext** – callers can create pages via
    ``context.new_page()``. The context should be closed when finished to free
    resources.
    """
    proxy = _select_proxy()
    # Build launch arguments.
    launch_kwargs = {
        "headless": headless,
        "proxy": {"server": proxy} if proxy else None,
    }
    # Remove the ``proxy`` key if None to keep the dict clean (Playwright
    # expects the argument to be omitted entirely when there is no proxy).
    if not proxy:
        launch_kwargs.pop("proxy")

    playwright = sync_playwright().start()
    browser: Browser = playwright.chromium.launch(**launch_kwargs)
    # Random viewport – typical desktop sizes.
    viewport = {
        "width": random.choice([1280, 1440, 1600, 1920]),
        "height": random.choice([720, 800, 900, 1080]),
    }
    context: BrowserContext = browser.new_context(
        user_agent=_random_user_agent(),
        viewport=viewport,
        geolocation={"latitude": -6.2, "longitude": 106.8},  # Jakarta as default
        permissions=["geolocation"],
    )

    # Attach stealth script to each new page.
    def _add_stealth(page):  # pragma: no cover – trivial lambda
        page.add_init_script(_STEALTH_JS)

    context.on("page", _add_stealth)
    return context

# ---------------------------------------------------------------------------
# Example helper – convenient wrapper for quick use cases.
# ---------------------------------------------------------------------------
def open_page(url: str, headless: bool = True) -> BrowserContext:
    """Open *url* in a new stealth context and return the page.

    The returned value is the **Page** object; the underlying context is kept
    alive as an attribute ``page.context`` so callers can later call
    ``page.context.close()``.
    """
    ctx = create_browser(headless=headless)
    page = ctx.new_page()
    page.goto(url)
    return page

# ---------------------------------------------------------------------------
# Persistence – cookies & storage
# ---------------------------------------------------------------------------
_COOKIES_DIR = Path(__file__).parent / "cookies"
_COOKIES_DIR.mkdir(exist_ok=True)

def save_cookies(context: BrowserContext, name: str) -> None:
    """Save cookies for *name* (e.g. ``"tiktok"``) to disk.

    The file is stored as ``cookies/<name>.json``. It can later be loaded with
    :func:`load_cookies`.
    """
    cookies = context.cookies()
    path = _COOKIES_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f)

def load_cookies(context: BrowserContext, name: str) -> None:
    """Load previously saved cookies back into *context*.

    If the cookie file does not exist the function silently returns.
    """
    path = _COOKIES_DIR / f"{name}.json"
    if not path.is_file():
        return
    with open(path, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    context.add_cookies(cookies)

# End of ``stealth.py``
""