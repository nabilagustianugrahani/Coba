import requests
import json
import os

class ScraperTools:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def shopee_search(self, query, limit=5):
        try:
            url = f"https://shopee.co.id/api/v4/search/search_items?by=relevancy&keyword={query}&limit={limit}"
            r = self.session.get(url, timeout=10)
            data = r.json()
            items = data.get("items", [])
            results = []
            for item in items[:limit]:
                ib = item.get("item_basic", {})
                results.append({
                    "name": ib.get("name", ""),
                    "price": ib.get("price", 0) / 100000,
                    "price_min": ib.get("price_min", 0) / 100000,
                    "price_max": ib.get("price_max", 0) / 100000,
                    "stock": ib.get("stock", 0),
                    "sold": ib.get("sold", 0),
                    "shop_location": ib.get("shop_location", ""),
                    "rating": ib.get("item_rating", {}).get("rating_star", 0),
                    "image": ib.get("image", ""),
                })
            return results
        except Exception as e:
            return [{"error": str(e)}]

    def tokopedia_search(self, query, limit=5):
        try:
            url = f"https://ta.tokopedia.com/promo/v1.2/merchant?q={query}&rows={limit}"
            r = self.session.get(url, timeout=10)
            data = r.json()
            results = []
            for item in data.get("data", {}).get("list", [])[:limit]:
                results.append({
                    "name": item.get("name", ""),
                    "price": item.get("price", 0),
                    "rating": item.get("rating", 0),
                    "merchant": item.get("merchant_name", ""),
                })
            return results
        except Exception as e:
            return [{"error": str(e)}]

    def trending_tiktok(self):
        try:
            url = "https://ads.tiktok.com/creative_radar/api/v1/top_keywords?period=7d"
            r = self.session.get(url, timeout=10)
            return r.json().get("data", {}).get("list", [])[:10]
        except Exception as e:
            return [{"error": str(e)}]

    def search_best_commission(self, query):
        shopee = self.shopee_search(query)
        result = []
        for item in shopee:
            if "error" not in item:
                item["platform"] = "shopee"
                item["estimated_commission"] = round(item.get("price", 0) * 0.15, 2)
                result.append(item)
        return result