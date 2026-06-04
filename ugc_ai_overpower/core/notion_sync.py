import os
import json
import time
import datetime
import requests
from typing import Optional, Any

NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"

SCHEMAS = {
    "Campaigns": {
        "title": "Campaign Name",
        "properties": {
            "Name": {"title": {}},
            "Product": {"rich_text": {}},
            "Status": {"select": {"options": [
                {"name": "Active", "color": "green"},
                {"name": "Paused", "color": "yellow"},
                {"name": "Completed", "color": "blue"},
                {"name": "Failed", "color": "red"},
            ]}},
            "Target Platforms": {"multi_select": {"options": [
                {"name": "tiktok", "color": "purple"}, {"name": "instagram", "color": "pink"},
                {"name": "youtube", "color": "red"}, {"name": "shopee", "color": "orange"},
                {"name": "tokopedia", "color": "green"}, {"name": "lazada", "color": "blue"},
            ]}},
            "Psychology Triggers": {"rich_text": {}},
            "Total Content": {"number": {}},
            "Content Generated": {"number": {}},
            "Videos Generated": {"number": {}},
            "Posts Published": {"number": {}},
            "Created At": {"date": {}},
            "Updated At": {"date": {}},
            "Last Run": {"date": {}},
        },
    },
    "Content": {
        "title": "Content Hook",
        "properties": {
            "Hook": {"title": {}},
            "Campaign": {"relation": {}},
            "Platform": {"select": {"options": [
                {"name": "tiktok", "color": "purple"}, {"name": "instagram", "color": "pink"},
                {"name": "youtube", "color": "red"}, {"name": "shopee", "color": "orange"},
                {"name": "tokopedia", "color": "green"}, {"name": "lazada", "color": "blue"},
            ]}},
            "Status": {"select": {"options": [
                {"name": "pending", "color": "gray"},
                {"name": "scripted", "color": "yellow"},
                {"name": "video_generated", "color": "orange"},
                {"name": "posted", "color": "green"},
                {"name": "failed", "color": "red"},
            ]}},
            "Script": {"rich_text": {}},
            "Post URL": {"url": {}},
            "File Path": {"rich_text": {}},
            "Created At": {"date": {}},
            "Updated At": {"date": {}},
            "Affiliate Product": {"relation": {"database_id": "", "type": "single_property", "single_property": {}}},
        },
    },
    "Gallery": {
        "title": "Video Title",
        "properties": {
            "Title": {"title": {}},
            "Slug": {"rich_text": {}},
            "Description": {"rich_text": {}},
            "Niche": {"select": {"options": [
                {"name": "skincare", "color": "pink"}, {"name": "fashion", "color": "purple"},
                {"name": "food", "color": "orange"}, {"name": "tech", "color": "blue"},
                {"name": "lifestyle", "color": "green"}, {"name": "general", "color": "gray"},
            ]}},
            "Platform": {"select": {"options": [
                {"name": "tiktok", "color": "purple"}, {"name": "instagram", "color": "pink"},
                {"name": "youtube", "color": "red"},
            ]}},
            "Product": {"rich_text": {}},
            "Tags": {"multi_select": {}},
            "Views": {"number": {}},
            "Likes": {"number": {}},
            "SEO Page": {"url": {}},
            "Created At": {"date": {}},
        },
    },
    "Inbox": {
        "title": "Message",
        "properties": {
            "Content": {"title": {}},
            "Platform": {"select": {"options": [
                {"name": "tiktok", "color": "purple"}, {"name": "instagram", "color": "pink"},
                {"name": "youtube", "color": "red"}, {"name": "telegram", "color": "blue"},
                {"name": "whatsapp", "color": "green"}, {"name": "discord", "color": "gray"},
            ]}},
            "Sender": {"rich_text": {}},
            "Account": {"rich_text": {}},
            "Type": {"select": {"options": [
                {"name": "comment", "color": "green"}, {"name": "dm", "color": "purple"},
                {"name": "mention", "color": "blue"}, {"name": "reply", "color": "gray"},
            ]}},
            "Sentiment": {"select": {"options": [
                {"name": "positive", "color": "green"}, {"name": "negative", "color": "red"},
                {"name": "neutral", "color": "gray"}, {"name": "urgent", "color": "orange"},
            ]}},
            "AI Reply": {"rich_text": {}},
            "Replied": {"checkbox": {}},
            "Is Read": {"checkbox": {}},
            "Created At": {"date": {}},
        },
    },
    "Brands": {
        "title": "Brand Name",
        "properties": {
            "Name": {"title": {}},
            "Tone": {"select": {"options": [
                {"name": "professional", "color": "blue"}, {"name": "casual", "color": "green"},
                {"name": "humorous", "color": "yellow"}, {"name": "aspirational", "color": "purple"},
                {"name": "urgent", "color": "red"}, {"name": "luxury", "color": "orange"},
                {"name": "educational", "color": "gray"}, {"name": "playful", "color": "pink"},
            ]}},
            "Voice": {"select": {"options": [
                {"name": "formal", "color": "blue"}, {"name": "friendly", "color": "green"},
                {"name": "authoritative", "color": "red"}, {"name": "playful", "color": "pink"},
                {"name": "empathetic", "color": "purple"}, {"name": "bold", "color": "orange"},
            ]}},
            "Language": {"select": {"options": [
                {"name": "en", "color": "blue"}, {"name": "id", "color": "red"},
                {"name": "mix", "color": "purple"},
            ]}},
            "Color Palette": {"rich_text": {}},
            "Target Audience": {"rich_text": {}},
            "Emoji Style": {"select": {"options": [
                {"name": "none", "color": "gray"}, {"name": "minimal", "color": "blue"},
                {"name": "moderate", "color": "green"}, {"name": "heavy", "color": "pink"},
            ]}},
            "Default CTA": {"rich_text": {}},
            "Active": {"checkbox": {}},
            "Created At": {"date": {}},
        },
    },
    "Approvals": {
        "title": "Content Preview",
        "properties": {
            "Preview": {"title": {}},
            "Type": {"select": {"options": [
                {"name": "script", "color": "blue"}, {"name": "caption", "color": "green"},
                {"name": "video", "color": "purple"}, {"name": "image", "color": "orange"},
                {"name": "hashtag_set", "color": "gray"},
            ]}},
            "Platform": {"select": {"options": [
                {"name": "tiktok", "color": "purple"}, {"name": "instagram", "color": "pink"},
                {"name": "youtube", "color": "red"},
            ]}},
            "Product": {"rich_text": {}},
            "Status": {"select": {"options": [
                {"name": "pending_review", "color": "yellow"},
                {"name": "approved", "color": "green"},
                {"name": "rejected", "color": "red"},
                {"name": "auto_approved", "color": "blue"},
            ]}},
            "Reviewer": {"rich_text": {}},
            "Review Note": {"rich_text": {}},
            "Urgent": {"checkbox": {}},
            "Created At": {"date": {}},
            "Reviewed At": {"date": {}},
        },
    },
    "Analytics": {
        "title": "Post URL",
        "properties": {
            "Post": {"title": {}},
            "Content": {"relation": {}},
            "Campaign": {"relation": {}},
            "Date": {"date": {}},
            "Views": {"number": {}},
            "Likes": {"number": {}},
            "Comments": {"number": {}},
            "Shares": {"number": {}},
            "Clicks": {"number": {}},
            "📊 Engagement Rate": {"formula": {"expression": "if(prop(\"Views\") > 0, format(round((prop(\"Likes\") + prop(\"Comments\") + prop(\"Shares\")) / prop(\"Views\") * 10000) / 100) + \"%\", \"0%\")"}},
            "📈 Click Rate": {"formula": {"expression": "if(prop(\"Views\") > 0, format(round(prop(\"Clicks\") / prop(\"Views\") * 10000) / 100) + \"%\", \"0%\")"}},
            "Commission": {"number": {"format": "dollar"}},
            "Commission Rate": {"number": {"format": "percent"}},
            "Estimated Earnings": {"formula": {"expression": "prop(\"Clicks\") * prop(\"Commission Rate\")"}},
            "Conversion Rate": {"formula": {"expression": "if(prop(\"Clicks\") > 0, prop(\"Conversions\") / prop(\"Clicks\"), 0)"}},
            "Platform": {"select": {"options": [
                {"name": "tiktok", "color": "purple"}, {"name": "instagram", "color": "pink"},
                {"name": "youtube", "color": "red"}, {"name": "shopee", "color": "orange"},
                {"name": "tokopedia", "color": "green"}, {"name": "lazada", "color": "blue"},
            ]}},
        },
    },
    "Affiliate Products": {
        "title": "Product Name",
        "properties": {
            "Name": {"title": {}},
            "Platform": {"select": {"options": [
                {"name": "shopee", "color": "orange"},
                {"name": "tokopedia", "color": "green"},
                {"name": "lazada", "color": "blue"},
                {"name": "tiktok", "color": "purple"},
                {"name": "sociolla", "color": "pink"},
                {"name": "blibli", "color": "red"},
            ]}},
            "Price": {"number": {"format": "dollar"}},
            "Commission Rate": {"number": {"format": "percent"}},
            "Commission Amount": {"formula": {"expression": "prop(\"Price\") * prop(\"Commission Rate\")"}},
            "Affiliate Link": {"url": {}},
            "Product URL": {"url": {}},
            "Image URL": {"url": {}},
            "Rating": {"number": {"format": "number"}},
            "Sold": {"number": {"format": "number"}},
            "Category": {"select": {"options": [
                {"name": "skincare", "color": "pink"},
                {"name": "makeup", "color": "purple"},
                {"name": "bodycare", "color": "yellow"},
                {"name": "haircare", "color": "green"},
                {"name": "fragrance", "color": "blue"},
                {"name": "supplements", "color": "orange"},
            ]}},
            "Status": {"select": {"options": [
                {"name": "active", "color": "green"},
                {"name": "inactive", "color": "gray"},
            ]}},
            "Notes": {"rich_text": {}},
            "Created": {"date": {}},
        },
    },
}


class NotionDashboard:
    def __init__(
        self,
        token: Optional[str] = None,
        campaign_db: Optional[str] = None,
        content_db: Optional[str] = None,
        analytics_db: Optional[str] = None,
    ):
        self.token = token or os.getenv("NOTION_TOKEN", "")
        self.campaign_db = campaign_db or os.getenv("NOTION_CAMPAIGN_DB", "")
        self.content_db = content_db or os.getenv("NOTION_CONTENT_DB", "")
        self.analytics_db = analytics_db or os.getenv("NOTION_ANALYTICS_DB", "")
        self.gallery_db = os.getenv("NOTION_GALLERY_DB", "")
        self.inbox_db = os.getenv("NOTION_INBOX_DB", "")
        self.brands_db = os.getenv("NOTION_BRANDS_DB", "")
        self.approvals_db = os.getenv("NOTION_APPROVALS_DB", "")
        self.products_db = os.getenv("NOTION_PRODUCTS_DB", "")
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        })

    # ── HTTP ──────────────────────────────────────────────────────────
    def _request(self, method: str, endpoint: str, data: Optional[dict] = None) -> dict:
        url = f"{NOTION_API}/{endpoint.lstrip('/')}"
        for attempt in range(5):
            try:
                r = self._session.request(method, url, json=data)
            except requests.exceptions.ConnectionError as e:
                print(f"[Notion] Connection error (attempt {attempt+1}): {e}")
                time.sleep(2 ** attempt)
                continue

            if r.status_code == 429:
                retry = int(r.headers.get("Retry-After", 2 ** attempt))
                print(f"[Notion] Rate limited, retrying in {retry}s...")
                time.sleep(retry)
                continue

            if r.status_code >= 500:
                print(f"[Notion] Server error {r.status_code} (attempt {attempt+1})")
                time.sleep(2 ** attempt)
                continue

            try:
                return r.json()
            except ValueError:
                return {"raw": r.text, "status": r.status_code}

        raise RuntimeError(f"[Notion] Request failed after 5 retries: {method} {endpoint}")

    # ── Helpers ───────────────────────────────────────────────────────
    @staticmethod
    def _iso_now() -> str:
        return datetime.datetime.utcnow().isoformat() + "Z"

    @staticmethod
    def _format_title(text: str) -> list:
        return [{"type": "text", "text": {"content": text}}]

    @staticmethod
    def _format_rich(text: str) -> list:
        return [{"type": "text", "text": {"content": text}}] if text else []

    @staticmethod
    def _date_obj(iso: Optional[str] = None) -> dict:
        return {"start": iso or datetime.date.today().isoformat()}

    @staticmethod
    def _num(val: Optional[float]) -> Optional[dict]:
        return {"number": val} if val is not None else None

    @property
    def ready(self) -> bool:
        return bool(self.token)

    # ── Auto-create databases ────────────────────────────────────────
    def auto_create_databases(self) -> dict:
        created = {}
        if not self.token:
            print("[Notion] No token configured. Set NOTION_TOKEN env var.")
            return created

        # Find parent page — first try env NOTION_PARENT_PAGE, else create as standalone
        parent_id = os.getenv("NOTION_PARENT_PAGE", "")
        if parent_id:
            parent = {"type": "page_id", "page_id": parent_id}
        else:
            print("[Notion] No NOTION_PARENT_PAGE set. Databases will be created at workspace root (may fail if integration lacks permissions).")
            print("[Notion] Set NOTION_PARENT_PAGE to a page ID that the integration can write to.")
            parent = None

        _SCHEMA_ATTR_MAP = {
            "Campaigns": "campaign_db",
            "Content": "content_db",
            "Analytics": "analytics_db",
            "Gallery": "gallery_db",
            "Inbox": "inbox_db",
            "Brands": "brands_db",
            "Approvals": "approvals_db",
            "Affiliate Products": "products_db",
        }

        # Dependency order: databases without relations FIRST
        DB_ORDER = ["Campaigns", "Gallery", "Inbox", "Brands", "Approvals", "Affiliate Products", "Content", "Analytics"]
        # Map relation property names to their target database keys
        RELATION_MAP = {
            "Content": {"Campaign": "Campaigns", "Affiliate Product": "Affiliate Products"},
            "Analytics": {"Content": "Content", "Campaign": "Campaigns"},
        }

        for name in DB_ORDER:
            schema = SCHEMAS.get(name)
            if not schema:
                continue

            attr = _SCHEMA_ATTR_MAP.get(name, f"{name.lower()}_db")
            db_id = getattr(self, attr, "")
            if db_id:
                print(f"[Notion] {name} DB already configured: {db_id}")
                created[name] = db_id
                continue

            if parent is None:
                print(f"[Notion] Cannot create {name} database — no parent page configured")
                continue

            # Inject data_source_id for relation fields
            properties = {}
            for prop_name, prop_def in schema["properties"].items():
                if "relation" in prop_def:
                    target = RELATION_MAP.get(name, {}).get(prop_name)
                    target_id = created.get(target) if target else None
                    if target_id:
                        properties[prop_name] = {
                            "relation": {
                                "database_id": target_id,
                                "type": "single_property",
                                "single_property": {}
                            }
                        }
                    else:
                        # Fallback: check if target was already created in a prior run
                        target_attr = _SCHEMA_ATTR_MAP.get(target, f"{target.lower()}_db")
                        existing_id = getattr(self, target_attr, "")
                        if existing_id:
                            properties[prop_name] = {
                                "relation": {
                                    "database_id": existing_id,
                                    "type": "single_property",
                                    "single_property": {}
                                }
                            }
                        else:
                            print(f"[Notion] Skipping relation {prop_name} for {name} — target {target} not yet created")
                            # Notion still rejects; will be retried next run
                            # Pass minimal valid relation so API doesn't reject
                            properties[prop_name] = {"relation": {"type": "single_property", "single_property": {}}}
                else:
                    properties[prop_name] = prop_def

            payload = {
                "parent": parent,
                "title": self._format_title(f"UGC — {name}"),
                "properties": properties,
            }

            result = self._request("POST", "databases", payload)
            db_id = result.get("id", "")

            if db_id:
                setattr(self, attr, db_id)
                created[name] = db_id
                # Also set env var so future runs find it
                env_key = attr.upper()
                os.environ[f"NOTION_{env_key}"] = db_id
                print(f"[Notion] Created {name} database: {db_id}")
            else:
                print(f"[Notion] Failed to create {name} database: {result.get('message', 'unknown')}")

        # Post-creation: ensure Affiliate Product relation in Content DB is linked
        products_db_id = created.get("Affiliate Products") or self.products_db
        content_db_id = created.get("Content") or self.content_db
        if products_db_id and content_db_id:
            patch_payload = {
                "properties": {
                    "Affiliate Product": {
                        "relation": {
                            "database_id": products_db_id,
                            "type": "single_property",
                            "single_property": {},
                        }
                    }
                }
            }
            self._request("PATCH", f"databases/{content_db_id}", patch_payload)
            print(f"[Notion] Updated Content DB Affiliate Product relation -> {products_db_id}")

        return created

    # ── Campaigns ─────────────────────────────────────────────────────
    def add_campaign(
        self,
        product: str,
        platforms: Optional[list] = None,
        triggers: str = "",
    ) -> Optional[str]:
        if not self.campaign_db:
            print("[Notion] Campaign DB not configured")
            return None

        now = self._iso_now()
        payload = {
            "parent": {"database_id": self.campaign_db},
            "properties": {
                "Name": {"title": self._format_title(product)},
                "Product": {"rich_text": self._format_rich(product)},
                "Status": {"select": {"name": "Active"}},
                "Target Platforms": {
                    "multi_select": [{"name": p} for p in (platforms or ["tiktok"])]
                },
                "Psychology Triggers": {"rich_text": self._format_rich(triggers)},
                "Total Content": {"number": 0},
                "Content Generated": {"number": 0},
                "Videos Generated": {"number": 0},
                "Posts Published": {"number": 0},
                "Created At": {"date": self._date_obj(now)},
                "Updated At": {"date": self._date_obj(now)},
            },
        }

        result = self._request("POST", "pages", payload)
        cid = result.get("id")
        if cid:
            print(f"[Notion] Campaign created: {product} -> {cid}")
        return cid

    def update_campaign(self, campaign_id: str, **kwargs) -> bool:
        props = {}
        field_map = {
            "status": ("Status", lambda v: {"select": {"name": v}}),
            "product": ("Product", lambda v: {"rich_text": self._format_rich(v)}),
            "triggers": ("Psychology Triggers", lambda v: {"rich_text": self._format_rich(v)}),
            "total_content": ("Total Content", lambda v: {"number": v}),
            "content_generated": ("Content Generated", lambda v: {"number": v}),
            "videos_generated": ("Videos Generated", lambda v: {"number": v}),
            "posts_published": ("Posts Published", lambda v: {"number": v}),
            "last_run": ("Last Run", lambda v: {"date": self._date_obj(v)}),
        }

        for key, val in kwargs.items():
            if key in field_map:
                notion_key, fmt = field_map[key]
                props[notion_key] = fmt(val)

        if not props:
            return False

        props["Updated At"] = {"date": self._date_obj(self._iso_now())}

        result = self._request("PATCH", f"pages/{campaign_id}", {"properties": props})
        return "object" in result and result.get("object") == "page"

    # ── Content ───────────────────────────────────────────────────────
    def add_content(
        self,
        campaign_id: str,
        hook: str,
        platform: str = "tiktok",
        script: str = "",
        status: str = "pending",
    ) -> Optional[str]:
        if not self.content_db:
            print("[Notion] Content DB not configured")
            return None

        now = self._iso_now()
        payload = {
            "parent": {"database_id": self.content_db},
            "properties": {
                "Hook": {"title": self._format_title(hook)},
                "Campaign": {"relation": [{"id": campaign_id}]},
                "Platform": {"select": {"name": platform}},
                "Status": {"select": {"name": status}},
                "Script": {"rich_text": self._format_rich(script)},
                "Created At": {"date": self._date_obj(now)},
                "Updated At": {"date": self._date_obj(now)},
            },
        }

        result = self._request("POST", "pages", payload)
        cid = result.get("id")
        if cid:
            print(f"[Notion] Content added: {hook[:40]}... -> {cid}")
        return cid

    def update_content(self, content_id: str, status: Optional[str] = None, post_url: Optional[str] = None, file_path: Optional[str] = None) -> bool:
        props = {}
        if status:
            props["Status"] = {"select": {"name": status}}
        if post_url:
            props["Post URL"] = {"url": post_url}
        if file_path:
            props["File Path"] = {"rich_text": self._format_rich(file_path)}

        if not props:
            return False

        props["Updated At"] = {"date": self._date_obj(self._iso_now())}
        result = self._request("PATCH", f"pages/{content_id}", {"properties": props})
        return result.get("object") == "page"

    # ── Analytics ─────────────────────────────────────────────────────
    def add_analytics(
        self,
        content_id: str,
        campaign_id: str = "",
        views: int = 0,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        clicks: int = 0,
        platform: str = "tiktok",
        post_url: str = "",
    ) -> Optional[str]:
        if not self.analytics_db:
            print("[Notion] Analytics DB not configured")
            return None

        total_engagement = likes + comments + shares + clicks
        engagement_rate = round(total_engagement / max(views, 1) * 100, 2)

        payload = {
            "parent": {"database_id": self.analytics_db},
            "properties": {
                "Post": {"title": self._format_title(post_url or f"Content {content_id[:8]}")},
                "Content": {"relation": [{"id": content_id}]},
                "Campaign": (
                    {"relation": [{"id": campaign_id}]} if campaign_id else {"relation": []}
                ),
                "Date": {"date": self._date_obj()},
                "Views": {"number": views},
                "Likes": {"number": likes},
                "Comments": {"number": comments},
                "Shares": {"number": shares},
                "Clicks": {"number": clicks},
                "Engagement Rate": {"number": engagement_rate},
                "Platform": {"select": {"name": platform}},
            },
        }

        result = self._request("POST", "pages", payload)
        aid = result.get("id")
        if aid:
            print(f"[Notion] Analytics recorded: {views}v/{likes}l/{comments}c/{shares}s")
        return aid

    # ── Daily Reports ─────────────────────────────────────────────────
    def create_daily_report(self, date_str: Optional[str] = None) -> Optional[str]:
        if not self.campaign_db or not self.analytics_db:
            print("[Notion] Campaign or Analytics DB not configured")
            return None

        date_str = date_str or datetime.date.today().isoformat()
        campaigns = self.get_all_campaigns()

        # Aggregate today's analytics
        total_views = total_likes = total_comments = total_shares = total_clicks = 0
        active_campaigns = 0

        for c in campaigns:
            if c.get("status") == "Active":
                active_campaigns += 1

        # Try querying analytics for this date
        query = {
            "filter": {
                "property": "Date",
                "date": {"equals": date_str},
            }
        }
        try:
            an_resp = self._request("POST", f"databases/{self.analytics_db}/query", query)
            for row in an_resp.get("results", []):
                p = row.get("properties", {})
                total_views += (p.get("Views", {}).get("number") or 0)
                total_likes += (p.get("Likes", {}).get("number") or 0)
                total_comments += (p.get("Comments", {}).get("number") or 0)
                total_shares += (p.get("Shares", {}).get("number") or 0)
                total_clicks += (p.get("Clicks", {}).get("number") or 0)
        except Exception as e:
            print(f"[Notion] Could not query analytics for daily report: {e}")

        total_engagement = total_likes + total_comments + total_shares + total_clicks
        engagement_rate = round(total_engagement / max(total_views, 1) * 100, 2)

        # Create report as a page in the Campaigns DB (or we could make a separate Reports DB)
        # For simplicity, add it to analytics DB with special marker
        report_title = f"📊 Daily Report — {date_str}"
        payload = {
            "parent": {"database_id": self.analytics_db},
            "properties": {
                "Post": {"title": self._format_title(report_title)},
                "Date": {"date": self._date_obj(date_str)},
                "Views": {"number": total_views},
                "Likes": {"number": total_likes},
                "Comments": {"number": total_comments},
                "Shares": {"number": total_shares},
                "Clicks": {"number": total_clicks},
                "Engagement Rate": {"number": engagement_rate},
                "Platform": {"select": {"name": "report"}},
            },
        }

        result = self._request("POST", "pages", payload)
        rid = result.get("id")
        if rid:
            print(f"[Notion] Daily report created: {report_title}")
        return rid

    # ── Queries ────────────────────────────────────────────────────────
    def get_all_campaigns(self) -> list:
        if not self.campaign_db:
            return []
        result = self._request("POST", f"databases/{self.campaign_db}/query", {})
        campaigns = []
        for row in result.get("results", []):
            p = row.get("properties", {})
            campaign = {
                "id": row["id"],
                "name": self._extract_title(p, "Name"),
                "product": self._extract_rich(p, "Product"),
                "status": p.get("Status", {}).get("select", {}).get("name", ""),
                "platforms": [
                    o["name"] for o in p.get("Target Platforms", {}).get("multi_select", [])
                ],
                "triggers": self._extract_rich(p, "Psychology Triggers"),
                "total_content": (p.get("Total Content", {}).get("number") or 0),
                "content_generated": (p.get("Content Generated", {}).get("number") or 0),
                "videos_generated": (p.get("Videos Generated", {}).get("number") or 0),
                "posts_published": (p.get("Posts Published", {}).get("number") or 0),
                "created_at": (p.get("Created At", {}).get("date", {}) or {}).get("start", ""),
            }
            campaigns.append(campaign)
        return campaigns

    def get_content_for_campaign(self, campaign_id: str) -> list:
        if not self.content_db:
            return []
        query = {
            "filter": {
                "property": "Campaign",
                "relation": {"contains": campaign_id},
            }
        }
        result = self._request("POST", f"databases/{self.content_db}/query", query)
        items = []
        for row in result.get("results", []):
            p = row.get("properties", {})
            items.append({
                "id": row["id"],
                "hook": self._extract_title(p, "Hook"),
                "platform": p.get("Platform", {}).get("select", {}).get("name", ""),
                "status": p.get("Status", {}).get("select", {}).get("name", ""),
                "post_url": p.get("Post URL", {}).get("url", ""),
            })
        return items

    @staticmethod
    def _extract_title(props: dict, key: str) -> str:
        items = props.get(key, {}).get("title", [])
        return "".join(t.get("plain_text", "") for t in items) if items else ""

    @staticmethod
    def _extract_rich(props: dict, key: str) -> str:
        items = props.get(key, {}).get("rich_text", [])
        return "".join(t.get("plain_text", "") for t in items) if items else ""

    # ── Gallery ────────────────────────────────────────────────────────
    def sync_gallery(self, videos: list) -> list:
        if not self.gallery_db:
            print("[Notion] Gallery DB not configured")
            return []
        synced = []
        for v in videos:
            tags = []
            raw_tags = v.get("tags", "")
            if raw_tags:
                tags = [{"name": t.strip()} for t in raw_tags.split(",") if t.strip()]
            payload = {
                "parent": {"database_id": self.gallery_db},
                "properties": {
                    "Title": {"title": self._format_title(v.get("title", "Untitled"))},
                    "Slug": {"rich_text": self._format_rich(v.get("slug", ""))},
                    "Description": {"rich_text": self._format_rich(v.get("description", "")[:200])},
                    "Niche": {"select": {"name": v.get("niche", "general")}},
                    "Platform": {"select": {"name": v.get("platform", "tiktok")}},
                    "Product": {"rich_text": self._format_rich(v.get("product", ""))},
                    "Tags": {"multi_select": tags} if tags else {"multi_select": []},
                    "Views": {"number": v.get("views", 0)},
                    "Likes": {"number": v.get("likes", 0)},
                    "SEO Page": {"url": f"https://ugc-empire.ai/gallery/{v.get('slug','')}"},
                    "Created At": {"date": self._date_obj(v.get("created_at", self._iso_now()))},
                },
            }
            result = self._request("POST", "pages", payload)
            pid = result.get("id")
            if pid:
                synced.append(pid)
        print(f"[Notion] Synced {len(synced)} videos to Gallery")
        return synced

    # ── Inbox ──────────────────────────────────────────────────────────
    def sync_inbox(self, messages: list) -> list:
        if not self.inbox_db:
            print("[Notion] Inbox DB not configured")
            return []
        synced = []
        for m in messages:
            if m.get("reply_sent"):
                continue
            payload = {
                "parent": {"database_id": self.inbox_db},
                "properties": {
                    "Content": {"title": self._format_title(m.get("content", "")[:100])},
                    "Platform": {"select": {"name": m.get("platform", "tiktok")}},
                    "Sender": {"rich_text": self._format_rich(m.get("sender_username", ""))},
                    "Account": {"rich_text": self._format_rich(m.get("account_id", ""))},
                    "Type": {"select": {"name": m.get("message_type", "comment")}},
                    "Sentiment": {"select": {"name": m.get("sentiment", "neutral")}},
                    "AI Reply": {"rich_text": self._format_rich(m.get("ai_suggested_reply", "")[:200])},
                    "Replied": {"checkbox": bool(m.get("reply_sent", False))},
                    "Is Read": {"checkbox": bool(m.get("is_read", False))},
                    "Created At": {"date": self._date_obj(m.get("created_at", self._iso_now()))},
                },
            }
            result = self._request("POST", "pages", payload)
            pid = result.get("id")
            if pid:
                synced.append(pid)
        print(f"[Notion] Synced {len(synced)} inbox messages")
        return synced

    # ── Brands ─────────────────────────────────────────────────────────
    def sync_brands(self, brands: list) -> list:
        if not self.brands_db:
            print("[Notion] Brands DB not configured")
            return []
        synced = []
        for b in brands:
            payload = {
                "parent": {"database_id": self.brands_db},
                "properties": {
                    "Name": {"title": self._format_title(b.get("name", ""))},
                    "Tone": {"select": {"name": b.get("tone", "casual")}},
                    "Voice": {"select": {"name": b.get("voice", "friendly")}},
                    "Language": {"select": {"name": b.get("language", "en")}},
                    "Target Audience": {"rich_text": self._format_rich(b.get("target_audience", ""))},
                    "Emoji Style": {"select": {"name": b.get("emoji_style", "moderate")}},
                    "Default CTA": {"rich_text": self._format_rich(b.get("default_cta", ""))},
                    "Active": {"checkbox": bool(b.get("is_active", False))},
                    "Created At": {"date": self._date_obj(b.get("created_at", self._iso_now()))},
                },
            }
            result = self._request("POST", "pages", payload)
            pid = result.get("id")
            if pid:
                synced.append(pid)
        print(f"[Notion] Synced {len(synced)} brand profiles")
        return synced

    # ── Approvals ──────────────────────────────────────────────────────
    def sync_approvals(self, approvals: list) -> list:
        if not self.approvals_db:
            print("[Notion] Approvals DB not configured")
            return []
        synced = []
        for a in approvals:
            payload = {
                "parent": {"database_id": self.approvals_db},
                "properties": {
                    "Preview": {"title": self._format_title(a.get("content_data", "")[:100])},
                    "Type": {"select": {"name": a.get("content_type", "script")}},
                    "Platform": {"select": {"name": a.get("platform", "tiktok")}},
                    "Product": {"rich_text": self._format_rich(a.get("product", ""))},
                    "Status": {"select": {"name": a.get("status", "pending_review")}},
                    "Reviewer": {"rich_text": self._format_rich(a.get("reviewer", ""))},
                    "Review Note": {"rich_text": self._format_rich((a.get("review_note") or "")[:200])},
                    "Urgent": {"checkbox": bool(a.get("is_urgent", False))},
                    "Created At": {"date": self._date_obj(a.get("created_at", self._iso_now()))},
                    "Reviewed At": {"date": self._date_obj(a.get("reviewed_at")) if a.get("reviewed_at") else None},
                },
            }
            result = self._request("POST", "pages", payload)
            pid = result.get("id")
            if pid:
                synced.append(pid)
        print(f"[Notion] Synced {len(synced)} approval items")
        return synced

    # ── Affiliate Products ─────────────────────────────────────────────
    def sync_products(self, products: list) -> list:
        if not self.products_db:
            print("[Notion] Products DB not configured")
            return []
        synced = []
        for p in products:
            properties = {
                "Name": {"title": self._format_title(p.get("name", ""))},
                "Platform": {"select": {"name": p.get("platform", "shopee")}},
                "Price": self._num(p.get("price")),
                "Commission Rate": self._num(p.get("commission_rate")),
                "Affiliate Link": {"url": p.get("affiliate_link") or None},
                "Product URL": {"url": p.get("product_url") or None},
                "Image URL": {"url": p.get("image_url") or None},
                "Rating": self._num(p.get("rating")),
                "Sold": self._num(p.get("sold")),
                "Category": {"select": {"name": p.get("category", "skincare")}},
                "Status": {"select": {"name": p.get("status", "active")}},
                "Notes": {"rich_text": self._format_rich(p.get("notes", ""))},
                "Created": {"date": self._date_obj(p.get("created_at", self._iso_now()))},
            }
            properties = {k: v for k, v in properties.items() if v is not None}
            payload = {
                "parent": {"database_id": self.products_db},
                "properties": properties,
            }
            result = self._request("POST", "pages", payload)
            pid = result.get("id")
            if pid:
                synced.append(pid)
        print(f"[Notion] Synced {len(synced)} affiliate products")
        return synced

    # ── Full Dashboard Sync ────────────────────────────────────────────
    def sync_all(self, gallery=None, inbox=None, brand_profile=None, approval_workflow=None) -> dict:
        """Sync all local data to Notion databases in one call."""
        results = {}
        if gallery:
            try:
                videos = gallery.list_videos(limit=50)
                if videos:
                    results["gallery"] = self.sync_gallery(videos)
            except Exception as e:
                print(f"[Notion] Gallery sync error: {e}")
        if inbox:
            try:
                msgs = inbox.list_messages(limit=50)
                if msgs:
                    results["inbox"] = self.sync_inbox(msgs)
            except Exception as e:
                print(f"[Notion] Inbox sync error: {e}")
        if brand_profile:
            try:
                brands = brand_profile.list_all()
                if brands:
                    results["brands"] = self.sync_brands(brands)
            except Exception as e:
                print(f"[Notion] Brands sync error: {e}")
        if approval_workflow:
            try:
                pending = approval_workflow.list_pending(limit=50)
                history = approval_workflow.list_history(limit=50)
                all_items = pending + [{"content_data": h.get("note",""), "content_type": "review", "status": h.get("action",""), "reviewer": h.get("reviewer",""), "review_note": h.get("note",""), "created_at": h.get("created_at","")} for h in history]
                if all_items:
                    results["approvals"] = self.sync_approvals(all_items)
            except Exception as e:
                print(f"[Notion] Approvals sync error: {e}")
        return results

    # ── Orchestrator Sync ──────────────────────────────────────────────
    def sync_orchestrator_result(self, result: dict, product: str) -> dict:
        if not self.ready:
            print("[Notion] Not configured. Set NOTION_TOKEN and DB IDs.")
            return {"synced": False, "reason": "no_token"}

        # Auto-create DBs if needed
        if not all([self.campaign_db, self.content_db, self.analytics_db]):
            created = self.auto_create_databases()
            if not created:
                return {"synced": False, "reason": "no_databases"}

        # Find or create campaign
        campaigns = self.get_all_campaigns()
        existing = [c for c in campaigns if c["product"].lower() == product.lower()]
        if existing:
            campaign_id = existing[0]["id"]
            self.update_campaign(campaign_id, last_run=self._iso_now())
            print(f"[Notion] Found existing campaign: {product}")
        else:
            campaign_id = self.add_campaign(product=product, platforms=result.get("platforms"), triggers=result.get("psychology_triggers", ""))
            if not campaign_id:
                return {"synced": False, "reason": "campaign_create_failed"}

        # Add content entries
        content_ids = []
        scripts = result.get("scripts", [])
        for s in scripts:
            cid = self.add_content(campaign_id, hook=s.get("hook", ""), platform=s.get("platform", "tiktok"), script=s.get("script", ""), status="scripted")
            if cid:
                content_ids.append(cid)

        # Update counts
        total = len(scripts)
        self.update_campaign(campaign_id, total_content=total, content_generated=total)

        return {
            "synced": True,
            "campaign_id": campaign_id,
            "content_ids": content_ids,
        }
