import os
import json
import time
import datetime
import requests
from typing import Optional, Any, Dict, cast

NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"

# ── ui-ux-pro-max Notion Dashboard Schema Design ──────────────────────
# Design system applied:
#   - Status colors: Red #E11D48, Yellow #F59E0B, Green #10B981, Blue #3B82F6
#   - Emoji prefix only for category tags (not visual decoration)
#   - Page icons use first letter of category, no emoji decoration
#   - Column types: Status (select with color), Date, Number (formatted), URL
#   - Card density: compact view, no decorative dividers
#   - Property order: Status first, then key info, then relations
#   8 databases: Campaigns, Content, Analytics, Brands, Influencers,
#                Products, ContentBank, Logs

SCHEMAS = {
    "Campaigns": {
        "title": "Campaign Name",
        "properties": {
            "Name": {"title": {}},
            "Status": {"select": {"options": [
                {"name": "Draft", "color": "gray"},
                {"name": "Active", "color": "green"},
                {"name": "Paused", "color": "yellow"},
                {"name": "Completed", "color": "blue"},
                {"name": "Archived", "color": "red"},
            ]}},
            "Priority": {"select": {"options": [
                {"name": "Low", "color": "gray"},
                {"name": "Med", "color": "yellow"},
                {"name": "High", "color": "red"},
                {"name": "Urgent", "color": "red"},
            ]}},
            "Niche": {"select": {"options": [
                {"name": "skincare", "color": "pink"}, {"name": "fashion", "color": "purple"},
                {"name": "food", "color": "orange"}, {"name": "tech", "color": "blue"},
                {"name": "lifestyle", "color": "green"}, {"name": "general", "color": "gray"},
            ]}},
            "Budget": {"number": {"format": "dollar"}},
            "Start Date": {"date": {}},
            "End Date": {"date": {}},
            "Brand": {"relation": {}},
            "Owner": {"people": {}},
            "Created At": {"date": {}},
            "Updated At": {"date": {}},
        },
    },
    "Content": {
        "title": "Content Hook",
        "properties": {
            "Hook": {"title": {}},
            "Status": {"select": {"options": [
                {"name": "Draft", "color": "gray"},
                {"name": "Review", "color": "yellow"},
                {"name": "Approved", "color": "green"},
                {"name": "Scheduled", "color": "blue"},
                {"name": "Posted", "color": "green"},
                {"name": "Rejected", "color": "red"},
            ]}},
            "Type": {"select": {"options": [
                {"name": "Image", "color": "blue"},
                {"name": "Video", "color": "purple"},
                {"name": "Carousel", "color": "green"},
                {"name": "Story", "color": "orange"},
            ]}},
            "Platform": {"select": {"options": [
                {"name": "tiktok", "color": "purple"}, {"name": "instagram", "color": "pink"},
                {"name": "youtube", "color": "red"}, {"name": "shopee", "color": "orange"},
                {"name": "tokopedia", "color": "green"}, {"name": "lazada", "color": "blue"},
            ]}},
            "Niche": {"select": {"options": [
                {"name": "skincare", "color": "pink"}, {"name": "fashion", "color": "purple"},
                {"name": "food", "color": "orange"}, {"name": "tech", "color": "blue"},
                {"name": "lifestyle", "color": "green"}, {"name": "general", "color": "gray"},
            ]}},
            "Engagement Rate": {"number": {"format": "percent"}},
            "Caption": {"rich_text": {}},
            "Hashtags": {"multi_select": {}},
            "Campaign": {"relation": {}},
            "Post URL": {"url": {}},
            "Created At": {"date": {}},
            "Updated At": {"date": {}},
        },
    },
    "Analytics": {
        "title": "Metric",
        "properties": {
            "Platform": {"select": {"options": [
                {"name": "tiktok", "color": "purple"}, {"name": "instagram", "color": "pink"},
                {"name": "youtube", "color": "red"}, {"name": "shopee", "color": "orange"},
                {"name": "tokopedia", "color": "green"}, {"name": "lazada", "color": "blue"},
            ]}},
            "Metric": {"select": {"options": [
                {"name": "views", "color": "blue"}, {"name": "likes", "color": "green"},
                {"name": "comments", "color": "yellow"}, {"name": "shares", "color": "purple"},
                {"name": "clicks", "color": "orange"}, {"name": "conversions", "color": "red"},
            ]}},
            "Value": {"number": {}},
            "Date": {"date": {}},
            "Campaign": {"relation": {}},
            "Post URL": {"url": {}},
            "Created At": {"date": {}},
        },
    },
    "Brands": {
        "title": "Brand Name",
        "properties": {
            "Name": {"title": {}},
            "Status": {"select": {"options": [
                {"name": "Active", "color": "green"},
                {"name": "Inactive", "color": "gray"},
                {"name": "Onboarding", "color": "yellow"},
            ]}},
            "Industry": {"select": {"options": [
                {"name": "skincare", "color": "pink"}, {"name": "fashion", "color": "purple"},
                {"name": "food", "color": "orange"}, {"name": "tech", "color": "blue"},
                {"name": "lifestyle", "color": "green"}, {"name": "beauty", "color": "red"},
            ]}},
            "Niche": {"select": {"options": [
                {"name": "skincare", "color": "pink"}, {"name": "fashion", "color": "purple"},
                {"name": "food", "color": "orange"}, {"name": "tech", "color": "blue"},
                {"name": "lifestyle", "color": "green"}, {"name": "general", "color": "gray"},
            ]}},
            "Contact Email": {"email": {}},
            "Tone": {"select": {"options": [
                {"name": "professional", "color": "blue"}, {"name": "casual", "color": "green"},
                {"name": "humorous", "color": "yellow"}, {"name": "luxury", "color": "purple"},
            ]}},
            "Language": {"select": {"options": [
                {"name": "en", "color": "blue"}, {"name": "id", "color": "red"},
                {"name": "mix", "color": "purple"},
            ]}},
            "Color Palette": {"rich_text": {}},
            "Target Audience": {"rich_text": {}},
            "Created At": {"date": {}},
        },
    },
    "Influencers": {
        "title": "Name",
        "properties": {
            "Name": {"title": {}},
            "Platform": {"select": {"options": [
                {"name": "tiktok", "color": "purple"}, {"name": "instagram", "color": "pink"},
                {"name": "youtube", "color": "red"},
            ]}},
            "Followers": {"number": {}},
            "Engagement Rate": {"number": {"format": "percent"}},
            "Niche": {"select": {"options": [
                {"name": "skincare", "color": "pink"}, {"name": "fashion", "color": "purple"},
                {"name": "food", "color": "orange"}, {"name": "tech", "color": "blue"},
                {"name": "lifestyle", "color": "green"}, {"name": "general", "color": "gray"},
            ]}},
            "Tier": {"select": {"options": [
                {"name": "Nano", "color": "gray"},
                {"name": "Micro", "color": "yellow"},
                {"name": "Mid", "color": "blue"},
                {"name": "Macro", "color": "purple"},
                {"name": "Mega", "color": "red"},
            ]}},
            "Contact Email": {"email": {}},
            "Created At": {"date": {}},
        },
    },
    "Products": {
        "title": "Product Name",
        "properties": {
            "Name": {"title": {}},
            "Status": {"select": {"options": [
                {"name": "Active", "color": "green"},
                {"name": "Inactive", "color": "gray"},
                {"name": "Discontinued", "color": "red"},
            ]}},
            "Category": {"select": {"options": [
                {"name": "skincare", "color": "pink"},
                {"name": "makeup", "color": "purple"},
                {"name": "bodycare", "color": "yellow"},
                {"name": "haircare", "color": "green"},
                {"name": "fragrance", "color": "blue"},
                {"name": "supplements", "color": "orange"},
            ]}},
            "Price": {"number": {"format": "dollar"}},
            "Platform": {"select": {"options": [
                {"name": "shopee", "color": "orange"},
                {"name": "tokopedia", "color": "green"},
                {"name": "lazada", "color": "blue"},
                {"name": "tiktok", "color": "purple"},
            ]}},
            "Brand": {"relation": {}},
            "Commission Rate": {"number": {"format": "percent"}},
            "Affiliate Link": {"url": {}},
            "Rating": {"number": {}},
            "Sold": {"number": {}},
            "Created At": {"date": {}},
        },
    },
    "ContentBank": {
        "title": "Title",
        "properties": {
            "Title": {"title": {}},
            "Type": {"select": {"options": [
                {"name": "Image", "color": "blue"},
                {"name": "Video", "color": "purple"},
                {"name": "Carousel", "color": "green"},
                {"name": "Story", "color": "orange"},
                {"name": "Audio", "color": "pink"},
            ]}},
            "Tags": {"multi_select": {}},
            "Created Date": {"date": {}},
            "Used Count": {"number": {}},
            "File URL": {"url": {}},
            "Description": {"rich_text": {}},
        },
    },
    "Logs": {
        "title": "Message",
        "properties": {
            "Level": {"select": {"options": [
                {"name": "DEBUG", "color": "gray"},
                {"name": "INFO", "color": "blue"},
                {"name": "WARN", "color": "yellow"},
                {"name": "ERROR", "color": "red"},
                {"name": "CRITICAL", "color": "red"},
            ]}},
            "Source": {"select": {"options": [
                {"name": "orchestrator", "color": "purple"},
                {"name": "notion_sync", "color": "blue"},
                {"name": "content_bank", "color": "green"},
                {"name": "main", "color": "orange"},
            ]}},
            "Message": {"rich_text": {}},
            "Timestamp": {"date": {}},
            "Traceback": {"rich_text": {}},
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

    def _query_database(self, db_id: str, filter_obj: dict) -> list:
        payload = {"filter": {"property": next(iter(filter_obj)), **next(iter(filter_obj.values()))}}
        results = []
        has_more = True
        start_cursor = None
        while has_more:
            if start_cursor:
                payload["start_cursor"] = start_cursor
            resp = self._request("POST", f"databases/{db_id}/query", payload)
            results.extend(resp.get("results", []))
            has_more = resp.get("has_more", False)
            start_cursor = resp.get("next_cursor")
        return results

    def _update_page(self, page_id: str, properties: dict) -> dict:
        return self._request("PATCH", f"pages/{page_id}", {"properties": properties})

    def get_database_info(self, db_id: str) -> dict:
        return self._request("GET", f"databases/{db_id}")

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

    # ── Visual Polish Helpers ──────────────────────────────────────────
    @staticmethod
    def pretty_status_color(status: str) -> str:
        """Return hex color for a status string (ui-ux-pro-max palette)."""
        palette = {
            "draft": "#6B7280", "active": "#10B981", "paused": "#F59E0B",
            "completed": "#3B82F6", "archived": "#E11D48", "failed": "#E11D48",
            "review": "#F59E0B", "approved": "#10B981", "scheduled": "#3B82F6",
            "posted": "#10B981", "rejected": "#E11D48", "pending": "#F59E0B",
            "inactive": "#6B7280", "onboarding": "#F59E0B", "discontinued": "#E11D48",
            "error": "#E11D48", "warn": "#F59E0B", "info": "#3B82F6", "debug": "#6B7280",
            "critical": "#E11D48",
        }
        return palette.get(status.lower(), "#6B7280")

    @staticmethod
    def format_number(value: float, currency: bool = False) -> str:
        """Format number: 1.2K, 3.4M, $5.2K etc."""
        if value is None:
            return "$0" if currency else "0"
        abs_val = abs(value)
        sign = "-" if value < 0 else ""
        if abs_val >= 1_000_000:
            formatted = f"{abs_val / 1_000_000:.1f}M"
        elif abs_val >= 1_000:
            formatted = f"{abs_val / 1_000:.1f}K"
        else:
            formatted = str(int(abs_val))
        if currency:
            return f"{sign}${formatted}"
        return f"{sign}{formatted}"

    @staticmethod
    def format_percentage(value: float) -> str:
        """Format decimal as percentage string (0.123 -> '12.3%')."""
        if value is None:
            return "0%"
        return f"{value * 100:.1f}%"

    @staticmethod
    def format_engagement_rate(likes: float, comments: float, shares: float, followers: float) -> str:
        """Compute and format engagement rate as percentage."""
        if not followers or followers <= 0:
            return "0%"
        rate = (likes + comments + shares) / followers
        return f"{rate * 100:.2f}%"

    @property
    def ready(self) -> bool:
        return bool(self.token)

    # ── Auto-create databases ────────────────────────────────────────
    def auto_create_databases(self) -> dict:
        created: Dict[str, str] = {}
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
            "Influencers": "gallery_db",
            "ContentBank": "inbox_db",
            "Brands": "brands_db",
            "Logs": "approvals_db",
            "Products": "products_db",
        }

        # Dependency order: databases without relations FIRST
        DB_ORDER = ["Campaigns", "Influencers", "ContentBank", "Brands", "Logs", "Products", "Content", "Analytics"]
        # Map relation property names to their target database keys
        RELATION_MAP = {
            "Content": {"Campaign": "Campaigns"},
            "Products": {"Brand": "Brands"},
            "Analytics": {"Campaign": "Campaigns"},
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
            properties: Dict[str, Any] = {}
            for prop_name, prop_def in cast(Dict[str, Any], schema["properties"]).items():
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
                        target_attr = _SCHEMA_ATTR_MAP.get(str(target), f"{str(target).lower()}_db")
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
            patch_payload: Dict[str, Any] = {
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
        name: str,
        platforms: Optional[list] = None,
        triggers: str = "",
        priority: str = "Med",
        niche: str = "general",
        budget: Optional[float] = None,
    ) -> Optional[str]:
        if not self.campaign_db:
            print("[Notion] Campaign DB not configured")
            return None

        now = self._iso_now()
        payload: Dict[str, Any] = {
            "parent": {"database_id": self.campaign_db},
            "properties": {
                "Name": {"title": self._format_title(name)},
                "Status": {"select": {"name": "Draft"}},
                "Priority": {"select": {"name": priority}},
                "Niche": {"select": {"name": niche}},
                "Budget": self._num(budget),
                "Start Date": {"date": self._date_obj(now)},
                "End Date": None,
                "Created At": {"date": self._date_obj(now)},
                "Updated At": {"date": self._date_obj(now)},
            },
        }
        payload["properties"] = {k: v for k, v in payload["properties"].items() if v is not None}

        result = self._request("POST", "pages", payload)
        cid = result.get("id")
        if cid:
            print(f"[Notion] Campaign created: {name} -> {cid}")
        return cid

    def update_campaign(self, campaign_id: str, **kwargs) -> bool:
        props = {}
        field_map = {
            "status": ("Status", lambda v: {"select": {"name": v}}),
            "priority": ("Priority", lambda v: {"select": {"name": v}}),
            "niche": ("Niche", lambda v: {"select": {"name": v}}),
            "budget": ("Budget", lambda v: {"number": v}),
            "start_date": ("Start Date", lambda v: {"date": self._date_obj(v)}),
            "end_date": ("End Date", lambda v: {"date": self._date_obj(v)}),
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

    def cleanup_duplicate_campaigns(self) -> dict:
        """Archive duplicate campaigns grouped by product, keeping the first."""
        if not self.campaign_db:
            print("[Notion] Campaign DB not configured")
            return {}

        campaigns = self.get_all_campaigns()
        from collections import defaultdict
        groups: dict = defaultdict(list)
        for c in campaigns:
            key = (c.get("product") or "").strip()
            if not key:
                continue
            groups[key].append(c)

        deleted: dict = {}
        for product, items in groups.items():
            if len(items) <= 1:
                continue
            ids_removed = []
            for dup in items[1:]:
                page_id = dup["id"]
                result = self._request("PATCH", f"pages/{page_id}", {"archived": True})
                if result.get("object") == "page" and result.get("archived"):
                    ids_removed.append(page_id)
                    print(f"[Notion] Archived duplicate campaign '{product}' -> {page_id}")
                else:
                    code = result.get("code", "unknown")
                    message = result.get("message", str(result))
                    print(f"[Notion] Archive failed for {page_id}: code={code} message={message}")
            if ids_removed:
                deleted[product] = ids_removed
        return deleted

    # ── Content ───────────────────────────────────────────────────────
    def add_content(
        self,
        campaign_id: str,
        hook: str,
        platform: str = "tiktok",
        content_type: str = "Video",
        caption: str = "",
        status: str = "Draft",
    ) -> Optional[str]:
        if not self.content_db:
            print("[Notion] Content DB not configured")
            return None

        now = self._iso_now()
        payload = {
            "parent": {"database_id": self.content_db},
            "properties": {
                "Hook": {"title": self._format_title(hook)},
                "Status": {"select": {"name": status}},
                "Type": {"select": {"name": content_type}},
                "Platform": {"select": {"name": platform}},
                "Caption": {"rich_text": self._format_rich(caption)},
                "Campaign": {"relation": [{"id": campaign_id}]},
                "Created At": {"date": self._date_obj(now)},
                "Updated At": {"date": self._date_obj(now)},
            },
        }

        result = self._request("POST", "pages", payload)
        cid = result.get("id")
        if cid:
            print(f"[Notion] Content added: {hook[:40]}... -> {cid}")
        return cid

    def update_content(self, content_id: str, status: Optional[str] = None, post_url: Optional[str] = None, caption: Optional[str] = None) -> bool:
        props: Dict[str, Any] = {}
        if status:
            props["Status"] = {"select": {"name": status}}
        if post_url:
            props["Post URL"] = {"url": post_url}
        if caption:
            props["Caption"] = {"rich_text": self._format_rich(caption)}

        if not props:
            return False

        props["Updated At"] = {"date": self._date_obj(self._iso_now())}
        result = self._request("PATCH", f"pages/{content_id}", {"properties": props})
        return result.get("object") == "page"

    # ── Analytics ─────────────────────────────────────────────────────
    def add_analytics(
        self,
        campaign_id: str = "",
        metric: str = "views",
        value: float = 0,
        platform: str = "tiktok",
        post_url: str = "",
    ) -> Optional[str]:
        if not self.analytics_db:
            print("[Notion] Analytics DB not configured")
            return None

        payload = {
            "parent": {"database_id": self.analytics_db},
            "properties": {
                "Platform": {"select": {"name": platform}},
                "Metric": {"select": {"name": metric}},
                "Value": {"number": value},
                "Date": {"date": self._date_obj()},
                "Campaign": (
                    {"relation": [{"id": campaign_id}]} if campaign_id else {"relation": []}
                ),
                "Post URL": {"url": post_url or None},
                "Created At": {"date": self._date_obj(self._iso_now())},
            },
        }
        payload["properties"] = {k: v for k, v in payload["properties"].items() if v is not None}

        result = self._request("POST", "pages", payload)
        aid = result.get("id")
        if aid:
            print(f"[Notion] Analytics recorded: {platform}/{metric}={value}")
        else:
            code = result.get("code", "unknown")
            message = result.get("message", str(result))
            print(f"[Notion] Analytics write failed: code={code} message={message}")
        return aid

    # ── Daily Reports ─────────────────────────────────────────────────
    def create_daily_report(self, date_str: Optional[str] = None) -> Optional[str]:
        if not self.campaign_db or not self.analytics_db:
            print("[Notion] Campaign or Analytics DB not configured")
            return None

        date_str = date_str or datetime.date.today().isoformat()
        campaigns = self.get_all_campaigns()

        # Aggregate today's analytics
        total_value = 0
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
                total_value += (p.get("Value", {}).get("number") or 0)
        except Exception as e:
            print(f"[Notion] Could not query analytics for daily report: {e}")

        report_title = f"Daily Report — {date_str}"
        payload = {
            "parent": {"database_id": self.analytics_db},
            "properties": {
                "Platform": {"select": {"name": "report"}},
                "Metric": {"select": {"name": "daily_summary"}},
                "Value": {"number": total_value},
                "Date": {"date": self._date_obj(date_str)},
                "Post URL": None,
                "Created At": {"date": self._date_obj(self._iso_now())},
            },
        }
        payload["properties"] = {k: v for k, v in payload["properties"].items() if v is not None}

        result = self._request("POST", "pages", payload)
        rid = result.get("id")
        if rid:
            print(f"[Notion] Daily report created: {report_title}")
        else:
            code = result.get("code", "unknown")
            message = result.get("message", str(result))
            print(f"[Notion] Daily report write failed: code={code} message={message}")
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
                "status": p.get("Status", {}).get("select", {}).get("name", ""),
                "priority": p.get("Priority", {}).get("select", {}).get("name", ""),
                "niche": p.get("Niche", {}).get("select", {}).get("name", ""),
                "budget": (p.get("Budget", {}).get("number") or 0),
                "start_date": (p.get("Start Date", {}).get("date", {}) or {}).get("start", ""),
                "end_date": (p.get("End Date", {}).get("date", {}) or {}).get("start", ""),
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

    def find_in_database(self, db_id: str, query_text: str) -> list:
        result = self._request("POST", f"databases/{db_id}/query", {})
        items = []
        for row in result.get("results", []):
            p = row.get("properties", {})
            name = self._extract_title(p, "Name") or self._extract_title(p, "Title") or self._extract_title(p, "Hook") or ""
            if query_text.lower() in name.lower():
                items.append({"id": row["id"], "name": name[:80]})
        return items

    @staticmethod
    def _extract_title(props: dict, key: str) -> str:
        items = props.get(key, {}).get("title", [])
        return "".join(t.get("plain_text", "") for t in items) if items else ""

    @staticmethod
    def _extract_rich(props: dict, key: str) -> str:
        items = props.get(key, {}).get("rich_text", [])
        return "".join(t.get("plain_text", "") for t in items) if items else ""

    # ── Influencers (formerly Gallery) ────────────────────────────────
    def sync_influencers(self, influencers: list) -> list:
        if not self.gallery_db:
            print("[Notion] Influencers DB not configured")
            return []
        synced = []
        for inf in influencers:
            name = inf.get("name", "Unknown")
            properties = {
                "Name": {"title": self._format_title(name)},
                "Platform": {"select": {"name": inf.get("platform", "tiktok")}},
                "Followers": {"number": inf.get("followers", 0)},
                "Engagement Rate": {"number": inf.get("engagement_rate", 0)},
                "Niche": {"select": {"name": inf.get("niche", "general")}},
                "Tier": {"select": {"name": inf.get("tier", "Micro")}},
                "Contact Email": {"email": inf.get("email") or None},
                "Created At": {"date": self._date_obj(inf.get("created_at", self._iso_now()))},
            }
            properties = {k: v for k, v in properties.items() if v is not None}
            existing = self._query_database(self.gallery_db, {"Name": {"title": {"equals": name}}})
            if existing:
                self._update_page(existing[0]["id"], properties)
                synced.append(existing[0]["id"])
            else:
                payload = {"parent": {"database_id": self.gallery_db}, "properties": properties}
                result = self._request("POST", "pages", payload)
                pid = result.get("id")
                if pid:
                    synced.append(pid)
        print(f"[Notion] Synced {len(synced)} influencers")
        return synced

    # ── ContentBank (formerly Inbox) ──────────────────────────────────
    def sync_contentbank(self, items: list) -> list:
        if not self.inbox_db:
            print("[Notion] ContentBank DB not configured")
            return []
        synced = []
        for item in items:
            title = item.get("title", "Untitled")
            tags = []
            raw_tags = item.get("tags", "")
            if raw_tags:
                tags = [{"name": t.strip()} for t in raw_tags.split(",") if t.strip()]
            properties = {
                "Title": {"title": self._format_title(title)},
                "Type": {"select": {"name": item.get("type", "Image")}},
                "Tags": {"multi_select": tags} if tags else {"multi_select": []},
                "Created Date": {"date": self._date_obj(item.get("created_at", self._iso_now()))},
                "Used Count": {"number": item.get("used_count", 0)},
                "File URL": {"url": item.get("file_url") or None},
                "Description": {"rich_text": self._format_rich(item.get("description", "")[:200])},
            }
            properties = {k: v for k, v in properties.items() if v is not None}
            existing = self._query_database(self.inbox_db, {"Title": {"title": {"equals": title}}})
            if existing:
                self._update_page(existing[0]["id"], properties)
                synced.append(existing[0]["id"])
            else:
                payload = {"parent": {"database_id": self.inbox_db}, "properties": properties}
                result = self._request("POST", "pages", payload)
                pid = result.get("id")
                if pid:
                    synced.append(pid)
        print(f"[Notion] Synced {len(synced)} content bank items")
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
                    "Status": {"select": {"name": b.get("status", "Active")}},
                    "Industry": {"select": {"name": b.get("industry", "lifestyle")}},
                    "Niche": {"select": {"name": b.get("niche", "general")}},
                    "Contact Email": {"email": b.get("email") or None},
                    "Tone": {"select": {"name": b.get("tone", "casual")}},
                    "Language": {"select": {"name": b.get("language", "en")}},
                    "Target Audience": {"rich_text": self._format_rich(b.get("target_audience", ""))},
                    "Created At": {"date": self._date_obj(b.get("created_at", self._iso_now()))},
                },
            }
            payload["properties"] = {k: v for k, v in payload["properties"].items() if v is not None}
            result = self._request("POST", "pages", payload)
            pid = result.get("id")
            if pid:
                synced.append(pid)
        print(f"[Notion] Synced {len(synced)} brand profiles")
        return synced

    # ── Logs (formerly Approvals) ─────────────────────────────────────
    def sync_logs(self, logs: list) -> list:
        if not self.approvals_db:
            print("[Notion] Logs DB not configured")
            return []
        synced = []
        for log_entry in logs:
            payload = {
                "parent": {"database_id": self.approvals_db},
                "properties": {
                    "Level": {"select": {"name": log_entry.get("level", "INFO")}},
                    "Source": {"select": {"name": log_entry.get("source", "main")}},
                    "Message": {"rich_text": self._format_rich(log_entry.get("message", "")[:500])},
                    "Timestamp": {"date": self._date_obj(log_entry.get("timestamp", self._iso_now()))},
                    "Traceback": {"rich_text": self._format_rich(log_entry.get("traceback", "")[:1000])},
                },
            }
            result = self._request("POST", "pages", payload)
            pid = result.get("id")
            if pid:
                synced.append(pid)
        print(f"[Notion] Synced {len(synced)} log entries")
        return synced

    # ── Products ───────────────────────────────────────────────────────
    def sync_products(self, products: list) -> list:
        if not self.products_db:
            print("[Notion] Products DB not configured")
            return []
        synced = []
        for p in products:
            name = p.get("name", "")
            properties = {
                "Name": {"title": self._format_title(name)},
                "Status": {"select": {"name": p.get("status", "Active")}},
                "Category": {"select": {"name": p.get("category", "skincare")}},
                "Price": self._num(p.get("price")),
                "Platform": {"select": {"name": p.get("platform", "shopee")}},
                "Commission Rate": self._num(p.get("commission_rate")),
                "Affiliate Link": {"url": p.get("affiliate_link") or None},
                "Rating": self._num(p.get("rating")),
                "Sold": self._num(p.get("sold")),
                "Created At": {"date": self._date_obj(p.get("created_at", self._iso_now()))},
            }
            properties = {k: v for k, v in properties.items() if v is not None}
            existing = self._query_database(self.products_db, {"Name": {"title": {"equals": name}}})
            if existing:
                page_id = existing[0]["id"]
                self._update_page(page_id, properties)
                synced.append(page_id)
            else:
                payload = {
                    "parent": {"database_id": self.products_db},
                    "properties": properties,
                }
                result = self._request("POST", "pages", payload)
                pid = result.get("id")
                if pid:
                    synced.append(pid)
        print(f"[Notion] Synced {len(synced)} products")
        return synced

    # ── Full Dashboard Sync ────────────────────────────────────────────
    def sync_all(self, influencers=None, contentbank=None, brand_profile=None, logs=None) -> dict:
        """Sync all local data to Notion databases in one call."""
        results = {}
        if influencers:
            try:
                results["influencers"] = self.sync_influencers(influencers)
            except Exception as e:
                print(f"[Notion] Influencers sync error: {e}")
        if contentbank:
            try:
                results["contentbank"] = self.sync_contentbank(contentbank)
            except Exception as e:
                print(f"[Notion] ContentBank sync error: {e}")
        if brand_profile:
            try:
                brands = brand_profile.list_all()
                if brands:
                    results["brands"] = self.sync_brands(brands)
            except Exception as e:
                print(f"[Notion] Brands sync error: {e}")
        if logs:
            try:
                results["logs"] = self.sync_logs(logs)
            except Exception as e:
                print(f"[Notion] Logs sync error: {e}")
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
        existing = [c for c in campaigns if c["name"].lower() == product.lower()]
        if existing:
            campaign_id = existing[0]["id"]
            self.update_campaign(campaign_id, start_date=self._iso_now())
            print(f"[Notion] Found existing campaign: {product}")
        else:
            campaign_id = self.add_campaign(name=product, platforms=result.get("platforms"), triggers=result.get("psychology_triggers", ""))
            if not campaign_id:
                return {"synced": False, "reason": "campaign_create_failed"}

        # Add content entries
        content_ids = []
        scripts = result.get("scripts", [])
        for s in scripts:
            cid = self.add_content(campaign_id, hook=s.get("hook", ""), platform=s.get("platform", "tiktok"), status="Review")
            if cid:
                content_ids.append(cid)

        return {
            "synced": True,
            "campaign_id": campaign_id,
            "content_ids": content_ids,
        }
