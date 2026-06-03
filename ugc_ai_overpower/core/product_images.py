"""Auto-source product images from affiliate/e-commerce links."""
import os, logging, hashlib, requests, tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)


class ProductImageScraper:
    """Scrape product images from Shopee, Tokopedia, Lazada, etc.

    Caches downloaded images locally to avoid repeated downloads.
    """

    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or str(
            Path(skynet_config.get("paths", "assets_dir", default="/tmp")) / "product_images"
        )
        os.makedirs(self.cache_dir, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def scrape(self, url: str, max_images: int = 3) -> list[str]:
        """Download product images from an e-commerce URL.

        Returns list of local file paths.
        """
        domain = urlparse(url).netloc.lower()
        scraper = self._get_scraper(domain)
        if scraper:
            image_urls = scraper(url)
        else:
            image_urls = self._generic_scrape(url)

        image_urls = image_urls[:max_images]
        return [self._download(url, img_url) for img_url in image_urls]

    def _get_scraper(self, domain: str):
        if "shopee" in domain:
            return self._scrape_shopee
        if "tokopedia" in domain:
            return self._scrape_tokopedia
        if "lazada" in domain:
            return self._scrape_lazada
        if "tiktok" in domain:
            return self._scrape_tiktok
        return None

    def _scrape_shopee(self, url: str) -> list[str]:
        try:
            resp = self._session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            imgs = []
            for img in soup.select("img[src*='shopeecdn']"):
                src = img.get("src") or img.get("data-src", "")
                if src and "shopeecdn" in src:
                    imgs.append(src)
            return imgs or self._generic_scrape(url)
        except Exception as e:
            log.warning("Shopee scrape failed: %s", e)
            return []

    def _scrape_tokopedia(self, url: str) -> list[str]:
        try:
            resp = self._session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            imgs = []
            for img in soup.select("img[src*='tokopedia']"):
                src = img.get("src") or img.get("data-src", "")
                if src and "tokopedia" in src:
                    imgs.append(src)
            return imgs or self._generic_scrape(url)
        except Exception as e:
            log.warning("Tokopedia scrape failed: %s", e)
            return []

    def _scrape_lazada(self, url: str) -> list[str]:
        try:
            resp = self._session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            imgs = []
            for img in soup.select("img[src*='lazada']"):
                src = img.get("src") or img.get("data-src", "")
                if src and "lazada" in src:
                    imgs.append(src)
            return imgs or self._generic_scrape(url)
        except Exception as e:
            log.warning("Lazada scrape failed: %s", e)
            return []

    def _scrape_tiktok(self, url: str) -> list[str]:
        try:
            resp = self._session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            imgs = []
            for img in soup.select("img"):
                src = img.get("src") or img.get("data-src", "")
                if src and ("p16-" in src or "p9-" in src):
                    imgs.append(src)
            return imgs or self._generic_scrape(url)
        except Exception as e:
            log.warning("TikTok scrape failed: %s", e)
            return []

    def _generic_scrape(self, url: str) -> list[str]:
        try:
            resp = self._session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            urls = []
            for img in soup.select("img[src]")[:10]:
                src = img["src"]
                if src.startswith("http") and "logo" not in src.lower():
                    urls.append(src)
            return urls
        except Exception as e:
            log.warning("Generic scrape failed: %s", e)
            return []

    def _download(self, page_url: str, img_url: str) -> Optional[str]:
        try:
            cache_key = hashlib.md5(img_url.encode()).hexdigest()[:16]
            ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
            local_path = os.path.join(self.cache_dir, f"{cache_key}{ext}")

            if os.path.exists(local_path):
                return local_path

            if not img_url.startswith("http"):
                img_url = page_url + img_url if img_url.startswith("/") else img_url

            resp = self._session.get(img_url, timeout=15, stream=True)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            log.info("Downloaded: %s", local_path)
            return local_path
        except Exception as e:
            log.warning("Image download failed: %s", e)
            return None

    def scrape_from_affiliate(self, affiliate_url: str) -> list[str]:
        """Convenience: scrape product images from an affiliate link."""
        return self.scrape(affiliate_url)
