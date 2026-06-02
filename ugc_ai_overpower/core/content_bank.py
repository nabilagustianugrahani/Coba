import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "content_bank.db")

class ContentBank:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                platform TEXT DEFAULT 'shopee',
                category TEXT,
                commission REAL DEFAULT 0,
                price REAL DEFAULT 0,
                affiliate_link TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS influencers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                niche TEXT,
                gender TEXT,
                age INTEGER,
                personality TEXT,
                voice_style TEXT,
                visual_style TEXT,
                backstory TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                influencer_id INTEGER,
                product_id INTEGER,
                platform TEXT,
                hook TEXT,
                script TEXT,
                hashtags TEXT,
                status TEXT DEFAULT 'draft',
                video_path TEXT,
                scheduled_at TIMESTAMP,
                posted_at TIMESTAMP,
                engagement_score REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (influencer_id) REFERENCES influencers(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                product_id INTEGER,
                status TEXT DEFAULT 'planning',
                total_content INTEGER DEFAULT 0,
                posted_count INTEGER DEFAULT 0,
                total_commission REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id INTEGER,
                platform TEXT,
                scheduled_at TIMESTAMP,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (content_id) REFERENCES content(id)
            );
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id INTEGER,
                platform TEXT,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                conversions INTEGER DEFAULT 0,
                commission REAL DEFAULT 0,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

    def add_product(self, name, platform="shopee", category=None, commission=0, price=0, affiliate_link=None):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO products (name, platform, category, commission, price, affiliate_link) VALUES (?,?,?,?,?,?)",
                  (name, platform, category, commission, price, affiliate_link))
        conn.commit()
        pid = c.lastrowid
        conn.close()
        return pid

    def add_influencer(self, name, niche, gender, age, personality, voice_style, visual_style, backstory):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO influencers (name, niche, gender, age, personality, voice_style, visual_style, backstory)
                     VALUES (?,?,?,?,?,?,?,?)""",
                  (name, niche, gender, age, personality, voice_style, visual_style, backstory))
        conn.commit()
        iid = c.lastrowid
        conn.close()
        return iid

    def add_content(self, influencer_id, product_id, platform, hook, script, hashtags, scheduled_at=None):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO content (influencer_id, product_id, platform, hook, script, hashtags, scheduled_at)
                     VALUES (?,?,?,?,?,?,?)""",
                  (influencer_id, product_id, platform, hook, script, json.dumps(hashtags), scheduled_at))
        conn.commit()
        cid = c.lastrowid
        conn.close()
        return cid

    def add_schedule(self, persona, platform, product, waktu):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO content (influencer_id, platform, status, scheduled_at) VALUES (?,?,?,?)",
                  (persona, platform, "scheduled", waktu))
        conn.commit()
        cid = c.lastrowid
        conn.close()
        return f"Scheduled #{cid}: {persona} → {platform} at {waktu}"

    def get_all(self):
        conn = self._get_conn()
        c = conn.cursor()
        rows = c.execute("SELECT id, name, status, created_at FROM campaigns ORDER BY created_at DESC LIMIT 20").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def create_campaign(self, name, product_id=None):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO campaigns (name, product_id) VALUES (?,?)", (name, product_id))
        conn.commit()
        cid = c.lastrowid
        conn.close()
        return cid

    def update_content_status(self, content_id, status, video_path=None):
        conn = self._get_conn()
        c = conn.cursor()
        if video_path:
            c.execute("UPDATE content SET status=?, video_path=? WHERE id=?", (status, video_path, content_id))
        else:
            c.execute("UPDATE content SET status=? WHERE id=?", (status, content_id))
        conn.commit()
        conn.close()

    def get_pending_posts(self):
        conn = self._get_conn()
        c = conn.cursor()
        rows = c.execute("""SELECT c.*, i.name as influencer_name, p.name as product_name
                           FROM content c
                           LEFT JOIN influencers i ON c.influencer_id = i.id
                           LEFT JOIN products p ON c.product_id = p.id
                           WHERE c.status = 'scheduled' AND c.scheduled_at <= datetime('now')
                           ORDER BY c.scheduled_at""").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def log_analytics(self, content_id, platform, views=0, likes=0, comments=0, shares=0, clicks=0, conversions=0, commission=0):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO analytics (content_id, platform, views, likes, comments, shares, clicks, conversions, commission)
                     VALUES (?,?,?,?,?,?,?,?,?)""",
                  (content_id, platform, views, likes, comments, shares, clicks, conversions, commission))
        conn.commit()
        conn.close()