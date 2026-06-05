"""Enhanced Content Bank — search, tagging, versioning, full-text.
Replaces the original ContentBank with supercharged features."""

import sqlite3, json, os, re, logging, hashlib, threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)
DB_PATH = Path(__file__).resolve().parents[1] / "content_bank.db"

SCHEMA_V2 = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=10000;

-- Enhanced products
CREATE TABLE IF NOT EXISTS products_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT GENERATED ALWAYS AS (LOWER(REPLACE(name, ' ', '-'))) STORED,
    platform TEXT DEFAULT 'shopee',
    category TEXT,
    subcategory TEXT,
    commission REAL DEFAULT 0,
    price REAL DEFAULT 0,
    affiliate_link TEXT,
    image_url TEXT,
    tags TEXT DEFAULT '[]',          -- JSON array
    metadata TEXT DEFAULT '{}',      -- JSON blob
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Full-text search for products
CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
    name, category, tags, metadata,
    content='products_v2',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS products_ai AFTER INSERT ON products_v2 BEGIN
    INSERT INTO products_fts(rowid, name, category, tags, metadata)
    VALUES (new.id, new.name, new.category, new.tags, new.metadata);
END;
CREATE TRIGGER IF NOT EXISTS products_ad AFTER DELETE ON products_v2 BEGIN
    INSERT INTO products_fts(products_fts, rowid, name, category, tags, metadata)
    VALUES ('delete', old.id, old.name, old.category, old.tags, old.metadata);
END;
CREATE TRIGGER IF NOT EXISTS products_au AFTER UPDATE ON products_v2 BEGIN
    INSERT INTO products_fts(products_fts, rowid, name, category, tags, metadata)
    VALUES ('delete', old.id, old.name, old.category, old.tags, old.metadata);
    INSERT INTO products_fts(rowid, name, category, tags, metadata)
    VALUES (new.id, new.name, new.category, new.tags, new.metadata);
END;

-- Influencers (enhanced)
CREATE TABLE IF NOT EXISTS influencers_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    niche TEXT,
    gender TEXT,
    age INTEGER,
    personality TEXT,
    voice_style TEXT,
    visual_style TEXT,
    backstory TEXT,
    avatar_url TEXT,
    followers INTEGER DEFAULT 0,
    engagement_rate REAL DEFAULT 0,
    platforms TEXT DEFAULT '[]',     -- JSON array ["tiktok","instagram"]
    tags TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}',
    version INTEGER DEFAULT 1,
    performance_score REAL DEFAULT 0,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Content (with versioning)
CREATE TABLE IF NOT EXISTS content_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_group TEXT,              -- shared UUID for version tree
    version INTEGER DEFAULT 1,
    parent_version_id INTEGER REFERENCES content_v2(id),
    influencer_id INTEGER REFERENCES influencers_v2(id),
    product_id INTEGER REFERENCES products_v2(id),
    series_id INTEGER,
    episode_number INTEGER,
    platform TEXT,
    hook TEXT,
    script TEXT,
    script_hash TEXT,
    hashtags TEXT DEFAULT '[]',      -- JSON array
    status TEXT DEFAULT 'draft',
    video_path TEXT,
    thumbnail_path TEXT,
    tags TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}',
    -- Performance
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    engagement_score REAL DEFAULT 0,
    -- Scheduling
    scheduled_at TIMESTAMP,
    posted_at TIMESTAMP,
    post_url TEXT,
    -- Quality
    quality_score REAL DEFAULT 0,
    a_b_group TEXT,                  -- A/B test group
    is_recycle BOOLEAN DEFAULT 0,
    source_content_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_content_series ON content_v2(series_id);
CREATE INDEX IF NOT EXISTS idx_content_status ON content_v2(status);
CREATE INDEX IF NOT EXISTS idx_content_perf ON content_v2(engagement_score DESC);
CREATE INDEX IF NOT EXISTS idx_content_version ON content_v2(version_group);

-- Full-text search for content
CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
    hook, script, hashtags, tags,
    content='content_v2',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS content_ai AFTER INSERT ON content_v2 BEGIN
    INSERT INTO content_fts(rowid, hook, script, hashtags, tags)
    VALUES (new.id, new.hook, new.script, new.hashtags, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS content_ad AFTER DELETE ON content_v2 BEGIN
    INSERT INTO content_fts(content_fts, rowid, hook, script, hashtags, tags)
    VALUES ('delete', old.id, old.hook, old.script, old.hashtags, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS content_au AFTER UPDATE ON content_v2 BEGIN
    INSERT INTO content_fts(content_fts, rowid, hook, script, hashtags, tags)
    VALUES ('delete', old.id, old.hook, old.script, old.hashtags, old.tags);
    INSERT INTO content_fts(rowid, hook, script, hashtags, tags)
    VALUES (new.id, new.hook, new.script, new.hashtags, new.tags);
END;

-- Content series
CREATE TABLE IF NOT EXISTS content_series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    product_id INTEGER REFERENCES products_v2(id),
    platform TEXT,
    total_episodes INTEGER DEFAULT 0,
    episode_interval_hours INTEGER DEFAULT 24,
    status TEXT DEFAULT 'active',
    tags TEXT DEFAULT '[]',
    template_json TEXT DEFAULT '{}',  -- Episode template
    schedule_cron TEXT,               -- Cron expression for auto-posting
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tag system
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT,
    category TEXT,
    usage_count INTEGER DEFAULT 0
);

-- A/B test results
CREATE TABLE IF NOT EXISTS ab_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER REFERENCES content_v2(id),
    group_name TEXT,
    variant TEXT,                     -- 'A' or 'B'
    hook TEXT,
    thumbnail_path TEXT,
    scheduled_at TIMESTAMP,
    posted_at TIMESTAMP,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    winner BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class ContentBankV2:
    def __init__(self, db_path: str = ""):
        self.db_path = db_path or str(DB_PATH)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _init_db(self):
        conn = self._connect()
        try:
            conn.executescript(SCHEMA_V2)
            conn.commit()
            log.info("ContentBankV2 initialized")
        finally:
            conn.close()

    # ── Products ─────────────────────────────────────────────────
    def add_product(self, name: str, **kw) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """INSERT INTO products_v2 (name, platform, category, subcategory, commission, price,
                       affiliate_link, image_url, tags, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, kw.get("platform", "shopee"), kw.get("category", ""),
                     kw.get("subcategory", ""), kw.get("commission", 0), kw.get("price", 0),
                     kw.get("affiliate_link", ""), kw.get("image_url", ""),
                     json.dumps(kw.get("tags", [])), json.dumps(kw.get("metadata", {})))
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def get_all_products(self, limit: int = 100, offset: int = 0) -> list:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, platform, price, commission AS commission_rate, affiliate_link, category, image_url, created_at FROM products_v2 ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def search_products(self, query: str, limit: int = 20) -> list:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT rowid, * FROM products_fts WHERE products_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Content with versioning ──────────────────────────────────
    def add_content(self, hook: str, script: str, **kw) -> int:
        with self._lock:
            conn = self._connect()
            try:
                product_id = kw.get("product_id")
                if product_id is not None:
                    exists = conn.execute(
                        "SELECT 1 FROM products_v2 WHERE id=?", (product_id,)
                    ).fetchone()
                    if not exists:
                        product_id = None
                version_group = kw.get("version_group") or hashlib.md5(
                    (hook + script[:50]).encode()
                ).hexdigest()[:16]
                script_hash = hashlib.sha256(script.encode()).hexdigest()
                cur = conn.execute(
                    """INSERT INTO content_v2 (version_group, version, parent_version_id,
                       influencer_id, product_id, series_id, episode_number,
                       platform, hook, script, script_hash, hashtags, status,
                       tags, metadata, a_b_group, is_recycle, source_content_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (version_group, kw.get("version", 1), kw.get("parent_version_id"),
                     kw.get("influencer_id"), product_id, kw.get("series_id"),
                     kw.get("episode_number"), kw.get("platform", "tiktok"),
                     hook, script, script_hash,
                     json.dumps(kw.get("hashtags", [])), kw.get("status", "draft"),
                     json.dumps(kw.get("tags", [])), json.dumps(kw.get("metadata", {})),
                     kw.get("a_b_group"), int(kw.get("is_recycle", False)),
                     kw.get("source_content_id"))
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def create_version(self, content_id: int, new_script: str, **kw) -> int:
        """Create a new version of existing content."""
        conn = self._connect()
        try:
            orig = conn.execute("SELECT * FROM content_v2 WHERE id=?", (content_id,)).fetchone()
            if not orig:
                raise ValueError(f"Content {content_id} not found")
            new_kw = dict(kw)
            new_kw.pop("hook", None)
            new_kw.pop("script", None)
            new_kw.setdefault("version_group", orig["version_group"])
            new_kw.setdefault("version", orig["version"] + 1)
            new_kw.setdefault("parent_version_id", content_id)
            new_kw.setdefault("influencer_id", orig["influencer_id"])
            new_kw.setdefault("product_id", orig["product_id"])
            new_kw.setdefault("series_id", orig["series_id"])
            new_kw.setdefault("platform", orig["platform"])
            new_kw.setdefault("hashtags", json.loads(orig["hashtags"]))
            new_kw.setdefault("tags", json.loads(orig["tags"]))
            return self.add_content(
                hook=kw.get("hook", orig["hook"]),
                script=new_script,
                **new_kw
            )
        finally:
            conn.close()

    def get_version_tree(self, content_id: int) -> list:
        """Get all versions of a content piece."""
        conn = self._connect()
        try:
            orig = conn.execute("SELECT version_group FROM content_v2 WHERE id=?", (content_id,)).fetchone()
            if not orig:
                return []
            rows = conn.execute(
                "SELECT * FROM content_v2 WHERE version_group=? ORDER BY version ASC",
                (orig["version_group"],)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def search_content(self, query: str, limit: int = 20) -> list:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT rowid, * FROM content_fts WHERE content_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Tag system ───────────────────────────────────────────────
    def add_tag(self, name: str, color: str = "", category: str = "") -> int:
        with self._lock:
            conn = self._connect()
            try:
                name_lower = name.lower()
                cur = conn.execute(
                    "INSERT OR IGNORE INTO tags (name, color, category) VALUES (?, ?, ?)",
                    (name_lower, color, category)
                )
                conn.commit()
                if cur.lastrowid:
                    return cur.lastrowid
                row = conn.execute(
                    "SELECT id FROM tags WHERE name=?", (name_lower,)
                ).fetchone()
                return row["id"] if row else 0
            finally:
                conn.close()

    # ── Influencers ──────────────────────────────────────────────
    def add_influencer(self, name: str, **kw) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """INSERT INTO influencers_v2 (name, niche, gender, age, personality,
                       voice_style, visual_style, backstory, avatar_url, followers,
                       engagement_rate, platforms, tags, metadata, performance_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, kw.get("niche", ""), kw.get("gender", ""), kw.get("age"),
                     kw.get("personality", ""), kw.get("voice_style", ""),
                     kw.get("visual_style", ""), kw.get("backstory", ""),
                     kw.get("avatar_url", ""), kw.get("followers", 0),
                     kw.get("engagement_rate", 0),
                     json.dumps(kw.get("platforms", [])), json.dumps(kw.get("tags", [])),
                     json.dumps(kw.get("metadata", {})), kw.get("performance_score", 0))
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def get_tags_by_category(self, category: str) -> list:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM tags WHERE category=? ORDER BY usage_count DESC", (category,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Content series ────────────────────────────────────────────
    def create_series(self, name: str, **kw) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """INSERT INTO content_series (name, description, product_id, platform,
                       total_episodes, episode_interval_hours, tags, template_json, schedule_cron)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, kw.get("description", ""), kw.get("product_id"),
                     kw.get("platform", "tiktok"), kw.get("total_episodes", 10),
                     kw.get("episode_interval_hours", 24),
                     json.dumps(kw.get("tags", [])),
                     json.dumps(kw.get("template_json", {})),
                     kw.get("schedule_cron"))
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def get_series(self, series_id: int) -> dict:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM content_series WHERE id=?", (series_id,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def get_series_episodes(self, series_id: int) -> list:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM content_v2 WHERE series_id=? ORDER BY episode_number ASC",
                (series_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Analytics & Performance ──────────────────────────────────
    def update_performance(self, content_id: int, views: int = 0, likes: int = 0,
                           comments: int = 0, shares: int = 0, clicks: int = 0,
                           engagement_score: float = None):
        with self._lock:
            conn = self._connect()
            try:
                if engagement_score is not None:
                    score = engagement_score
                elif views == 0:
                    score = 0
                else:
                    total_eng = likes + comments + shares + clicks
                    score = round(total_eng / views * 100, 2)
                conn.execute(
                    """UPDATE content_v2 SET views=?, likes=?, comments=?, shares=?, clicks=?,
                       engagement_score=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (views, likes, comments, shares, clicks, score, content_id)
                )
                conn.commit()
            finally:
                conn.close()

    def get_top_performing(self, platform: str = "", days: int = 7, limit: int = 20) -> list:
        conn = self._connect()
        try:
            where = "WHERE engagement_score > 0"
            params = []
            if platform:
                where += " AND platform=?"
                params.append(platform)
            if days:
                where += " AND (posted_at IS NULL OR posted_at >= datetime('now', ?))"
                params.append(f"-{days} days")
            rows = conn.execute(
                f"SELECT * FROM content_v2 {where} ORDER BY engagement_score DESC LIMIT ?",
                params + [limit]
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_underperforming(self, threshold: float = 1.0, limit: int = 20) -> list:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT * FROM content_v2 WHERE views > 100
                   AND engagement_score < ? ORDER BY engagement_score ASC LIMIT ?""",
                (threshold, limit)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Stats ────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        conn = self._connect()
        try:
            return {
                "products": conn.execute("SELECT COUNT(*) FROM products_v2").fetchone()[0],
                "influencers": conn.execute("SELECT COUNT(*) FROM influencers_v2").fetchone()[0],
                "content": conn.execute("SELECT COUNT(*) FROM content_v2").fetchone()[0],
                "series": conn.execute("SELECT COUNT(*) FROM content_series").fetchone()[0],
                "versions": conn.execute("SELECT SUM(version) FROM content_v2").fetchone()[0] or 0,
                "tags": conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0],
                "avg_engagement": round(
                    conn.execute("SELECT AVG(engagement_score) FROM content_v2 WHERE engagement_score>0").fetchone()[0] or 0, 2
                ),
            }
        finally:
            conn.close()
