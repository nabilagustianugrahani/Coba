import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from core.notion_sync import NotionDashboard
from core.content_bank_v2 import ContentBankV2

dashboard = NotionDashboard()

# ── Campaigns ──
campaigns = [
    ("Avoskin Miraculous Refining Oil", ["tiktok", "instagram"], "loss aversion, social proof"),
    ("Scarlett Whitening Day Cream", ["tiktok", "shopee", "tokopedia"], "vanity, transformation"),
    ("Somethinc Retinol 0.5%", ["instagram", "youtube"], "authority, fear of missing out"),
]
campaign_ids = {}
for product, platforms, triggers in campaigns:
    cid = dashboard.add_campaign(product, platforms, triggers)
    if cid:
        campaign_ids[product] = cid

# ── Content ──
content_items = [
    ("Avoskin Miraculous Refining Oil", "Beneran oil ini bikin muka glowing? Watch this!", "tiktok", "Aku pake Avoskin 2 minggu, hasilnya...", "posted"),
    ("Avoskin Miraculous Refining Oil", "Avoskin vs serum import 500rb", "instagram", "Let's compare...", "video_generated"),
    ("Avoskin Miraculous Refining Oil", "Rahasia skin glow ala selebgram!", "tiktok", "Ini dia yang ga mereka bilang...", "pending"),
    ("Scarlett Whitening Day Cream", "Scarlett day cream review jujur", "tiktok", "Pemakaian 1 minggu...", "posted"),
    ("Scarlett Whitening Day Cream", "Produk lokal yang bikin whitecast?", "shopee", "Jawabannya...", "scripted"),
    ("Scarlett Whitening Day Cream", "Before after Scarlett 30 days", "tiktok", "Cek hasilnya...", "video_generated"),
    ("Somethinc Retinol 0.5%", "Retinol untuk pemula? Wajib nonton!", "youtube", "Gue kasih tau caranya...", "posted"),
    ("Somethinc Retinol 0.5%", "Somethinc vs The Ordinary", "instagram", "Head to head...", "pending"),
    ("Somethinc Retinol 0.5%", "Anti aging routine murah meriah", "tiktok", "Modal 200rb dapet...", "scripted"),
]
for product, hook, platform, script, status in content_items:
    cid = campaign_ids.get(product)
    if cid:
        dashboard.add_content(cid, hook, platform, script, status)

# ── Products ──
def seed_products():
    bank = ContentBankV2()
    products = [
        {"name": "Avoskin Miraculous Refining Oil", "platform": "shopee", "price": 85000, "commission_rate": 15,
         "affiliate_link": "https://shopee.co.id/avoskin-miraculous-refining-oil", "product_url": "https://shopee.co.id/avoskin-miraculous-refining-oil",
         "rating": 4.8, "sold": 15200, "category": "skincare", "status": "active"},
        {"name": "Scarlett Whitening Day Cream", "platform": "tokopedia", "price": 65000, "commission_rate": 10,
         "affiliate_link": "https://tokopedia.link/scarlett-whitening-day-cream", "product_url": "https://tokopedia.link/scarlett-whitening-day-cream",
         "rating": 4.7, "sold": 9800, "category": "bodycare", "status": "active"},
        {"name": "Somethinc Retinol 0.5%", "platform": "sociolla", "price": 120000, "commission_rate": 20,
         "affiliate_link": "https://sociolla.com/somethinc-retinol-0-5", "product_url": "https://sociolla.com/somethinc-retinol-0-5",
         "rating": 4.6, "sold": 7600, "category": "skincare", "status": "active"},
        {"name": "Wardah UV Shield SPF 50", "platform": "shopee", "price": 45000, "commission_rate": 15,
         "affiliate_link": "https://shopee.co.id/wardah-uv-shield-spf-50", "product_url": "https://shopee.co.id/wardah-uv-shield-spf-50",
         "rating": 4.9, "sold": 23100, "category": "skincare", "status": "active"},
        {"name": "The Originote Hyalucera Moist", "platform": "tokopedia", "price": 55000, "commission_rate": 10,
         "affiliate_link": "https://tokopedia.link/the-originote-hyalucera-moist", "product_url": "https://tokopedia.link/the-originote-hyalucera-moist",
         "rating": 4.5, "sold": 5400, "category": "skincare", "status": "active"},
    ]
    count = 0
    for p in products:
        pid = bank.add_product(
            name=p["name"],
            platform=p["platform"],
            price=p["price"],
            commission=p["commission_rate"],
            affiliate_link=p["affiliate_link"],
            category=p["category"],
            metadata={"product_url": p["product_url"], "rating": p["rating"], "sold": p["sold"], "status": p["status"]},
        )
        if pid:
            count += 1
            print(f"[Products] Seeded: {p['name']} (id={pid})")
    print(f"[Products] Total: {count}")
    return count

# ── Inbox (direct API) ──
inbox_msgs = [
    {"platform": "tiktok", "sender": "beauty_lover92", "type": "comment", "sentiment": "neutral", "content": "Kak Avoskin cocok gak buat kulit berminyak?"},
    {"platform": "instagram", "sender": "ratih_skincare", "type": "dm", "sentiment": "urgent", "content": "Mau order Somethinc retinol 3 botol, ada stok?"},
    {"platform": "tiktok", "sender": "ayobeliskincare", "type": "comment", "sentiment": "positive", "content": "Udah pake Scarlett 2 minggu, cerah banget!"},
    {"platform": "youtube", "sender": "hijab_beauty", "type": "comment", "sentiment": "positive", "content": "Reviewnya jujur banget, makasih kak"},
    {"platform": "instagram", "sender": "dian_skincareroutine", "type": "mention", "sentiment": "positive", "content": "Rekomendasiin ini @skincare_id @avoskin_id"},
]
import requests
headers = {
    "Authorization": f"Bearer {dashboard.token}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}
db_id = dashboard.inbox_db
if db_id:
    for msg in inbox_msgs:
        payload = {
            "parent": {"database_id": db_id},
            "properties": {
                "Content": {"title": [{"type": "text", "text": {"content": msg["content"][:80]}}]},
                "Platform": {"select": {"name": msg["platform"]}},
                "Sender": {"rich_text": [{"type": "text", "text": {"content": msg["sender"]}}]},
                "Type": {"select": {"name": msg["type"]}},
                "Sentiment": {"select": {"name": msg["sentiment"]}},
                "Is Read": {"checkbox": False},
                "Replied": {"checkbox": False},
                "Created At": {"date": {"start": "2026-06-03T00:00:00Z"}},
            },
        }
        r = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
        if r.status_code == 200:
            print(f"[Inbox] Synced: {msg['sender']}")
        else:
            print(f"[Inbox] Failed {msg['sender']}: {r.text[:100]}")

# ── Analytics (direct API) ──
analytics_data = [
    {"post": "Avoskin review tiktok", "platform": "tiktok", "views": 32100, "likes": 5230, "comments": 312, "shares": 2100, "clicks": 890, "commission": 12750, "conversions": 45},
    {"post": "Scarlett day cream IG", "platform": "instagram", "views": 15230, "likes": 2341, "comments": 156, "shares": 567, "clicks": 234, "commission": 6500, "conversions": 23},
    {"post": "Somethinc retinol yt", "platform": "youtube", "views": 28450, "likes": 4120, "comments": 289, "shares": 1234, "clicks": 456, "commission": 24000, "conversions": 67},
    {"post": "Dear Me sunscreen tiktok", "platform": "tiktok", "views": 19800, "likes": 3100, "comments": 198, "shares": 890, "clicks": 345, "commission": 4500, "conversions": 18},
    {"post": "Wardah moisturizer tutorial", "platform": "youtube", "views": 8900, "likes": 1567, "comments": 89, "shares": 345, "clicks": 123, "commission": 6750, "conversions": 8},
]
db_id = dashboard.analytics_db
if db_id:
    for a in analytics_data:
        payload = {
            "parent": {"database_id": db_id},
            "properties": {
                "Post": {"title": [{"type": "text", "text": {"content": a["post"]}}]},
                "Date": {"date": {"start": "2026-06-03"}},
                "Views": {"number": a["views"]},
                "Likes": {"number": a["likes"]},
                "Comments": {"number": a["comments"]},
                "Shares": {"number": a["shares"]},
                "Clicks": {"number": a["clicks"]},
                "Commission": {"number": a["commission"]},
                "Conversions": {"number": a["conversions"]},
                "Commission Rate": {"number": 15},
            },
        }
        r = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
        if r.status_code == 200:
            print(f"[Analytics] Synced: {a['post']}")
        else:
            print(f"[Analytics] Failed: {r.text[:100]}")

product_count = seed_products()

print("\n✅ FULL SEED COMPLETE!")
print(f"Campaigns: {len(campaign_ids)}")
print(f"Content: {len(content_items)}")
print(f"Inbox: {len(inbox_msgs)}")
print(f"Analytics: {len(analytics_data)}")
print(f"Products: {product_count}")
