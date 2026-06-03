"""Auto Affiliate Pipeline — search, match, link, inject, track.

Flow:
  1. search_products(niche) → top products from Shopee/Tokopedia via API
  2. match_to_scripts(scripts, products) → AI pairs each script with best product
  3. generate_links(matches) → affiliate links per platform
  4. inject_into_scripts(matches) → links injected into UGC scripts
  5. save_catalog(products) → persistent product DB for reuse
"""
import os, json, re, logging, random
from typing import Optional
from dataclasses import dataclass, field

from ugc_ai_overpower.mcp_server.tools.scraper_tools import ScraperTools
from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
from ugc_ai_overpower.core.affiliate import AffiliateManager

log = logging.getLogger(__name__)

COMMISSION_RATES = {
    "shopee": 0.15,
    "tokopedia": 0.10,
    "lazada": 0.12,
    "sociolla": 0.20,
    "blibli": 0.08,
    "tiktok": 0.12,
}

CTA_INJECTIONS = [
    "🔗 Langsung cek di sini: {link}",
    "Beli sekarang: {link}",
    "Cek link di bio atau klik: {link}",
    "Udah ada yang nyobain? Klik: {link}",
    "Keranjang kuning udah siap: {link}",
    "Link pembelian: {link}",
]


@dataclass
class AffiliateProduct:
    name: str
    price: float
    platform: str
    url: str
    commission: float = 0.0
    image: str = ""
    rating: float = 0.0
    sold: int = 0
    estimated_commission: float = 0.0


@dataclass
class MatchResult:
    script_index: int
    product: AffiliateProduct
    affiliate_link: str = ""
    injected_script: str = ""


class Affiliator:
    def __init__(self):
        self.scraper = ScraperTools()
        self.bank = ContentBankV2()
        self.affiliate = AffiliateManager()

    def search_products(self, query: str, limit: int = 10) -> list[AffiliateProduct]:
        """Search Shopee + Tokopedia for products matching query.

        Returns merged, sorted by estimated commission (highest first).
        """
        products = []

        shopee_items = self.scraper.shopee_search(query, limit)
        for item in shopee_items:
            if "error" in item:
                continue
            price = item.get("price", 0) or item.get("price_min", 0)
            comm = price * COMMISSION_RATES.get("shopee", 0.15)
            products.append(AffiliateProduct(
                name=item.get("name", ""),
                price=price,
                platform="shopee",
                url=f"https://shopee.co.id/search?keyword={query}",
                commission=COMMISSION_RATES["shopee"],
                image=item.get("image", ""),
                rating=item.get("rating", 0),
                sold=item.get("sold", 0),
                estimated_commission=round(comm, 2),
            ))

        tokped_items = self.scraper.tokopedia_search(query, limit)
        for item in tokped_items:
            if "error" in item:
                continue
            price = item.get("price", 0)
            comm = price * COMMISSION_RATES.get("tokopedia", 0.10)
            products.append(AffiliateProduct(
                name=item.get("name", ""),
                price=price,
                platform="tokopedia",
                url=f"https://tokopedia.link/search?q={query}",
                commission=COMMISSION_RATES["tokopedia"],
                rating=item.get("rating", 0),
                estimated_commission=round(comm, 2),
            ))

        products.sort(key=lambda p: p.estimated_commission, reverse=True)
        return products[:limit]

    def match_to_scripts(self, scripts: list[dict],
                          products: list[AffiliateProduct],
                          ai_router=None) -> list[MatchResult]:
        """AI-match each script to the most relevant affiliate product.

        Falls back to round-robin if AI is not available.
        """
        results = []
        if ai_router and products:
            for i, script in enumerate(scripts):
                product = products[i % len(products)]
                try:
                    prompt = (
                        f"Dari daftar produk berikut, pilih yang PALING RELEVAN untuk script UGC ini:\n"
                        f"SCRIPT: {script.get('script', '')[:200]}...\n"
                        f"PRODUK:\n" +
                        "\n".join(f"- {p.name} (Rp{p.price:,.0f}, komisi {p.estimated_commission})" for p in products[:5]) +
                        f"\n\nJawab ONLY nama produk yang paling cocok (1 kata/pilihan)."
                    )
                    chosen_name = ai_router.chat(prompt)
                    chosen = next((p for p in products if p.name.lower() in chosen_name.lower()), product)
                except Exception:
                    chosen = product

                link = self._generate_affiliate_link(chosen, script.get("platform", "tiktok"))
                injected = self._inject_affiliate(script.get("script", ""), link, chosen.name)
                results.append(MatchResult(
                    script_index=i,
                    product=chosen,
                    affiliate_link=link,
                    injected_script=injected,
                ))
        else:
            for i, script in enumerate(scripts):
                product = products[i % len(products)] if products else AffiliateProduct(
                    name="", price=0, platform="", url="")
                link = self._generate_affiliate_link(product, script.get("platform", "tiktok"))
                injected = self._inject_affiliate(script.get("script", ""), link, product.name)
                results.append(MatchResult(
                    script_index=i,
                    product=product,
                    affiliate_link=link,
                    injected_script=injected,
                ))
        return results

    def save_catalog(self, products: list[AffiliateProduct]):
        """Save products to persistent ContentBankV2 catalog."""
        for p in products:
            try:
                self.bank.add_product(
                    name=p.name,
                    platform=p.platform,
                    price=p.price,
                    commission=p.estimated_commission,
                    affiliate_link=p.url,
                    image_url=p.image,
                    category="affiliate",
                )
            except Exception as e:
                log.warning("Failed to save product %s: %s", p.name, e)

    def search_catalog(self, query: str, limit: int = 20) -> list:
        """Search local product catalog."""
        return self.bank.search_products(query, limit)

    def top_commission_products(self, limit: int = 10) -> list:
        """Get highest commission products from local catalog."""
        return self.bank.search_products("", limit)  # relies on ordering

    def _generate_affiliate_link(self, product: AffiliateProduct, platform: str) -> str:
        aff_link = self.affiliate.generate_link(
            platform=product.platform or platform,
            product_name=product.name,
            product_id="",
        )
        return aff_link or product.url

    def _inject_affiliate(self, script: str, link: str, product_name: str) -> str:
        cta = random.choice(CTA_INJECTIONS).format(link=link)
        if not product_name:
            return script
        mention = f" {product_name} "
        if product_name.lower() in script.lower():
            return script + "\n\n" + cta
        else:
            return script.replace(
                "produk", f"produk {product_name}"
            ).replace(
                "Produk", f"Produk {product_name}"
            ) + "\n\n" + cta

    def run_pipeline(self, scripts: list[dict], niche: str,
                      ai_router=None, save: bool = True) -> list[MatchResult]:
        """Full pipeline: search → match → link → inject.

        Args:
            scripts: List of script dicts (from mass_production).
            niche: Niche to search products for.
            ai_router: AIRouter instance for AI matching.
            save: Save products to persistent catalog.

        Returns:
            List of MatchResult with injected scripts.
        """
        log.info("🔍 Searching affiliate products for niche: %s", niche)
        products = self.search_products(niche, limit=10)
        log.info("✅ Found %d products", len(products))

        if save:
            self.save_catalog(products)

        log.info("🧠 Matching products to %d scripts...", len(scripts))
        matches = self.match_to_scripts(scripts, products, ai_router)
        log.info("✅ %d scripts matched with affiliate products", len(matches))

        return matches
