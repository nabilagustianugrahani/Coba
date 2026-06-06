"""Auto-inject affiliate links into social media captions.

Inserts affiliate redirect URLs (ugc.ai/r/{short_code}) at optimal
positions in captions based on platform-specific patterns. Supports
batch injection and placement suggestions.

Typical usage:
    tracker = AffiliateTracker("affiliate.db")
    injector = CaptionLinkInjector(tracker)
    link = tracker.create_link("prod-1", "shopee", "https://shopee.com/p", "aff-123")
    caption = injector.inject("Check out this amazing product!", link)
    # "Check out this amazing product! 🛒 Shop now: https://ugc.ai/r/AbCdEf"
"""
from __future__ import annotations

import re
from typing import Optional

from ugc_ai_overpower.integrations.affiliate import AffiliateLink, AffiliateTracker

# Platform-specific emoji/prefix mapping
PLATFORM_STYLE: dict[str, dict[str, str]] = {
    "shopee": {"emoji": "🛒", "prefix": "Shop now"},
    "tokopedia": {"emoji": "🛍️", "prefix": "Beli di sini"},
    "tiktok_shop": {"emoji": "🔥", "prefix": "Link di sini"},
    "lazada": {"emoji": "🎯", "prefix": "Checkout sekarang"},
    "bukalapak": {"emoji": "✨", "prefix": "Pesan sekarang"},
}

MAX_CAPTION_LENGTH = 2200


class CaptionLinkInjector:
    """Injects affiliate links into captions at optimal positions."""

    def __init__(self, tracker: AffiliateTracker) -> None:
        self.tracker = tracker

    def inject(
        self,
        caption: str,
        link: AffiliateLink,
        position: str = "auto",
    ) -> str:
        """Inject an affiliate link into a caption.

        Args:
            caption: The original caption text.
            link: The AffiliateLink to inject.
            position: Where to place the link:
                      'auto' - smart placement based on caption structure
                      'end' - at the very end
                      'start' - at the very start
                      'before_cta' - before existing CTA line
                      'after_hash' - before hashtags

        Returns:
            Caption with affiliate link injected.
        """
        url = self.tracker.build_redirect_url(link)
        platform_style = PLATFORM_STYLE.get(link.platform, PLATFORM_STYLE["shopee"])
        link_text = f"{platform_style['emoji']} {platform_style['prefix']}: {url}"

        if position == "start":
            result = f"{link_text}\n\n{caption}"
        elif position == "end":
            result = f"{caption}\n\n{link_text}"
        elif position == "before_cta":
            result = self._inject_before_cta(caption, link_text)
        elif position == "after_hash":
            result = self._inject_after_hashtags(caption, link_text)
        else:  # auto
            result = self._auto_inject(caption, link_text)

        # Truncate if needed
        if len(result) > MAX_CAPTION_LENGTH:
            result = result[: MAX_CAPTION_LENGTH - 3] + "..."
        return result

    def inject_batch(
        self,
        captions: list[str],
        links: list[AffiliateLink],
    ) -> list[str]:
        """Inject links into multiple captions (one per caption)."""
        results: list[str] = []
        for caption, link in zip(captions, links):
            results.append(self.inject(caption, link))
        return results

    def suggest_placement(self, caption: str, platform: str) -> int:
        """Suggest the character position where a link should be inserted.

        Returns an integer index (0 = start, len(caption) = end).
        """
        # If caption has hashtags, suggest before them
        hash_match = re.search(r"#\w+", caption)
        if hash_match:
            return hash_match.start()

        # If caption has URLs, suggest after them
        url_match = re.search(r"https?://\S+", caption)
        if url_match:
            return url_match.end()

        # If caption has CTA-like phrases, suggest after them
        cta_patterns = [
            r"(check\s+it\s+out|shop\s+now|get\s+yours|link\s+in\s+bio)",
            r"(click|tap|swipe)\s+(the\s+)?(link|bio)",
            r"(dapatkan|beli|pesan)\s+(sekarang|di)",
        ]
        for pat in cta_patterns:
            match = re.search(pat, caption, re.IGNORECASE)
            if match:
                return match.end()

        # Default: at the end
        return len(caption)

    def validate_caption(self, caption: str, platform: str) -> tuple[bool, str]:
        """Validate a caption for a specific platform.

        Returns (is_valid, reason).
        """
        if not caption or not caption.strip():
            return False, "Caption is empty"

        if len(caption) > MAX_CAPTION_LENGTH:
            return False, f"Caption exceeds {MAX_CAPTION_LENGTH} characters"

        # Check for placeholder text
        placeholders = ["[link]", "[url]", "[affiliate_link]", "{{link}}", "{{url}}"]
        for ph in placeholders:
            if ph in caption:
                return False, f"Caption contains unfilled placeholder: {ph}"

        # Check for broken/malicious content
        suspicious = re.findall(r"<script[^>]*>", caption, re.IGNORECASE)
        if suspicious:
            return False, "Caption contains script tags"

        return True, ""

    def _auto_inject(self, caption: str, link_text: str) -> str:
        """Smart auto-placement of link in caption."""
        # If there are hashtags, put link before them
        if re.search(r"#\w+", caption):
            return self._inject_after_hashtags(caption, link_text)
        # If there's a URL already, put link before it
        url_match = re.search(r"https?://\S+", caption)
        if url_match:
            before = caption[: url_match.start()].rstrip()
            after = caption[url_match.start():]
            return f"{before}\n\n{link_text}\n\n{after}"
        # Default: append
        return f"{caption}\n\n{link_text}"

    def _inject_before_cta(self, caption: str, link_text: str) -> str:
        """Insert link before a CTA line if found, otherwise append."""
        cta_patterns = [
            r"(check\s+it\s+out|shop\s+now|get\s+yours|link\s+in\s+bio)",
            r"(dapatkan|beli|pesan)\s+(sekarang|di)",
        ]
        for pat in cta_patterns:
            match = re.search(pat, caption, re.IGNORECASE)
            if match:
                before = caption[: match.start()].rstrip()
                after = caption[match.start():]
                return f"{before}\n\n{link_text}\n\n{after}"
        return f"{caption}\n\n{link_text}"

    def _inject_after_hashtags(self, caption: str, link_text: str) -> str:
        """Insert link before the first hashtag block."""
        hash_match = re.search(r"\s+#\w+", caption)
        if hash_match:
            before = caption[: hash_match.start()].rstrip()
            hashtags = caption[hash_match.start():]
            return f"{before}\n\n{link_text}\n\n{hashtags}"
        # No hashtags found, just append
        return f"{caption}\n\n{link_text}"


__all__ = [
    "CaptionLinkInjector",
]
