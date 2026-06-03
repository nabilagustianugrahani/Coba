"""Seed all 3 SQLite databases with realistic Indonesian skincare test data."""
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Gallery schema (from core/gallery.py) ──────────────────────────────────
GALLERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS gallery_videos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    slug          TEXT NOT NULL UNIQUE,
    description   TEXT,
    video_path    TEXT NOT NULL,
    thumbnail_path TEXT,
    duration_sec  INTEGER DEFAULT 0,
    platform      TEXT DEFAULT 'tiktok',
    niche         TEXT DEFAULT 'general',
    product       TEXT,
    tags          TEXT DEFAULT '',
    og_image      TEXT,
    views         INTEGER DEFAULT 0,
    likes         INTEGER DEFAULT 0,
    shares        INTEGER DEFAULT 0,
    seo_published INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_gallery_slug ON gallery_videos(slug);
CREATE INDEX IF NOT EXISTS idx_gallery_created ON gallery_videos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_gallery_niche ON gallery_videos(niche);
CREATE INDEX IF NOT EXISTS idx_gallery_product ON gallery_videos(product);
"""

gallery_seed = [
    {
        "title": "Review Scarlett Whitening Day Cream",
        "slug": "review-scarlett-whitening-day-cream-001",
        "description": "Aku udah pake Scarlett Whitening Day Cream selama 2 minggu, hasilnya cerah banget! Cocok buat kulit berminyak.",
        "video_path": "/output/scarlett_day_cream_review.mp4",
        "thumbnail_path": "/output/thumb_scarlett_day_cream.jpg",
        "duration_sec": 45,
        "platform": "tiktok",
        "niche": "skincare",
        "product": "Scarlett Whitening Day Cream",
        "tags": "scarlett,whitening,skincare,review,korea",
        "views": 15230,
        "likes": 2341,
        "shares": 567,
        "seo_published": 1,
    },
    {
        "title": "Somethinc Retinol Serum Hasilnya WOW",
        "slug": "somethinc-retinol-serum-wow-002",
        "description": "Beneran ni serum bikin muka mulus kayak baby skin. Somethinc Retinol 0.5% cocok buat pemula.",
        "video_path": "/output/somethinc_retinol.mp4",
        "thumbnail_path": "/output/thumb_somethinc_retinol.jpg",
        "duration_sec": 60,
        "platform": "instagram",
        "niche": "skincare",
        "product": "Somethinc Retinol 0.5%",
        "tags": "somethinc,retinol,antiaging,skincare,korea",
        "views": 28450,
        "likes": 4120,
        "shares": 1234,
        "seo_published": 1,
    },
    {
        "title": "Wardah Perfect Bright Moisturizer Tutorial",
        "slug": "wardah-perfect-bright-moisturizer-003",
        "description": "Cara pake Wardah Perfect Bright Moisturizer yang bener biar hasil maksimal. Cocok buat sahabat hijab!",
        "video_path": "/output/wardah_moisturizer.mp4",
        "thumbnail_path": "/output/thumb_wardah_moisturizer.jpg",
        "duration_sec": 55,
        "platform": "youtube",
        "niche": "skincare",
        "product": "Wardah Perfect Bright Moisturizer",
        "tags": "wardah,halal,skincare,moisturizer,hijab",
        "views": 8900,
        "likes": 1567,
        "shares": 345,
        "seo_published": 0,
    },
    {
        "title": "Avoskin Miraculous Oil vs Skincare Mahal",
        "slug": "avoskin-miraculous-oil-004",
        "description": "Aku bandingin Avoskin Miraculous Refining Oil sama serum import 500rb. Spoiler: Avoskin menang!",
        "video_path": "/output/avoskin_miraculous.mp4",
        "thumbnail_path": "/output/thumb_avoskin.jpg",
        "duration_sec": 75,
        "platform": "tiktok",
        "niche": "skincare",
        "product": "Avoskin Miraculous Refining Oil",
        "tags": "avoskin,localbrand,skincare,oil,bpjskinning",
        "views": 32100,
        "likes": 5230,
        "shares": 2100,
        "seo_published": 1,
    },
    {
        "title": "Dear Me Beauty Sunscreen SPF 50 Review",
        "slug": "dear-me-beauty-sunscreen-spf50-005",
        "description": "Sunscreen lokal yang ringan banget, no whitecast! Dear Me Beauty UV Shield SPF 50 PA+++.",
        "video_path": "/output/dearme_sunscreen.mp4",
        "thumbnail_path": "/output/thumb_dearme_sunscreen.jpg",
        "duration_sec": 50,
        "platform": "tiktok",
        "niche": "skincare",
        "product": "Dear Me Beauty UV Shield SPF 50",
        "tags": "dearmebeauty,sunscreen,spf,skincare,lokal",
        "views": 19800,
        "likes": 3100,
        "shares": 890,
        "seo_published": 1,
    },
]

# ── Inbox schema (from browser/social_inbox.py) ────────────────────────────
INBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS inbox_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL CHECK (platform IN ('tiktok','instagram','youtube','telegram','whatsapp','discord')),
    account_id      TEXT NOT NULL,
    sender_username TEXT NOT NULL,
    sender_name     TEXT DEFAULT '',
    message_type    TEXT NOT NULL DEFAULT 'comment' CHECK (message_type IN ('comment','dm','mention','reply')),
    content         TEXT NOT NULL,
    media_url       TEXT DEFAULT '',
    parent_id       INTEGER DEFAULT 0,
    is_read         INTEGER DEFAULT 0,
    is_urgent       INTEGER DEFAULT 0,
    sentiment       TEXT DEFAULT 'neutral' CHECK (sentiment IN ('positive','negative','neutral','urgent')),
    ai_suggested_reply TEXT DEFAULT '',
    ai_reply_approved  INTEGER DEFAULT 0,
    reply_sent      INTEGER DEFAULT 0,
    reply_text      TEXT DEFAULT '',
    replied_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS inbox_auto_reply_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL DEFAULT '*',
    keyword_pattern TEXT NOT NULL,
    reply_template  TEXT NOT NULL,
    sentiment_match TEXT DEFAULT '*',
    is_active       INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS inbox_muted_users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,
    username        TEXT NOT NULL,
    reason          TEXT DEFAULT '',
    muted_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, username)
);
"""

inbox_messages_seed = [
    {
        "platform": "tiktok",
        "account_id": "skincare_id_01",
        "sender_username": "beauty_lover92",
        "sender_name": "Sari Dewi",
        "message_type": "comment",
        "content": "Kak Scarlett day cream nya cocok gak buat kulit berminyak? Aku takut jerawatan.",
        "is_read": 0,
        "sentiment": "neutral",
    },
    {
        "platform": "instagram",
        "account_id": "skincare_id_02",
        "sender_username": "ratih_skincare",
        "sender_name": "Ratih",
        "message_type": "dm",
        "content": "Mau order Somethinc retinol serum 3 botol, ada stok? urgent banget ya kak",
        "is_read": 0,
        "is_urgent": 1,
        "sentiment": "urgent",
    },
    {
        "platform": "tiktok",
        "account_id": "skincare_id_01",
        "sender_username": "ayobeliskincare",
        "sender_name": "Fajar",
        "message_type": "comment",
        "content": "Avoskin miraculous oil emang sebagus itu? Aku udah pake 2 minggu kok belum ada perubahan",
        "is_read": 1,
        "sentiment": "negative",
        "reply_sent": 1,
        "reply_text": "Hai kak! Coba dipake rutin pagi-malam ya, biasanya hasil keliatan di minggu ke-3/4 😊",
        "replied_at": "2026-06-02T10:30:00",
    },
    {
        "platform": "youtube",
        "account_id": "skincare_id_03",
        "sender_username": "hijab_beauty",
        "sender_name": "Aisyah",
        "message_type": "comment",
        "content": "Wardah moisturizer emang terbaik! Udah pake 3 tahun gak ganti-ganti",
        "is_read": 0,
        "sentiment": "positive",
    },
    {
        "platform": "instagram",
        "account_id": "skincare_id_02",
        "sender_username": "dian_skincareroutine",
        "sender_name": "Dian",
        "message_type": "mention",
        "content": "Cobain deh @skincare_id pake Dear Me sunscreen, enak banget teksturnya ringan",
        "is_read": 0,
        "sentiment": "positive",
    },
]

inbox_rules_seed = [
    {
        "platform": "tiktok",
        "keyword_pattern": r"\b(harga|price|berapa|cost)\b",
        "reply_template": "Hai kak! Untuk info harga bisa cek link di bio kami ya 😊",
        "sentiment_match": "*",
    },
    {
        "platform": "instagram",
        "keyword_pattern": r"\b(urgent|cepet|cito|butuh)\b",
        "reply_template": "Halo kak! Kami akan proses secepatnya. Tim CS akan menghubungi kakak dalam 15 menit.",
        "sentiment_match": "urgent",
    },
    {
        "platform": "*",
        "keyword_pattern": r"\b(thank|thanks|makasih|terima kasih)\b",
        "reply_template": "Sama-sama kak! Semoga skincarenya cocok ya 🫶",
        "sentiment_match": "positive",
    },
]

inbox_muted_seed = [
    {"platform": "tiktok", "username": "spam_bot_01", "reason": "Promosi produk ilegal"},
    {"platform": "instagram", "username": "haterskul", "reason": "Hate speech repeated"},
]

# ── Approval schema (from core/approval_workflow.py) ───────────────────────
APPROVAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id      INTEGER NOT NULL,
    content_type    TEXT NOT NULL DEFAULT 'script' CHECK (content_type IN ('script','caption','video','image','hashtag_set')),
    platform        TEXT DEFAULT 'tiktok',
    content_data    TEXT NOT NULL,
    preview_url     TEXT DEFAULT '',
    product         TEXT DEFAULT '',
    campaign_id     TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending_review'
                    CHECK (status IN ('pending_review','approved','rejected','auto_approved')),
    reviewer        TEXT DEFAULT '',
    review_note     TEXT DEFAULT '',
    reviewed_at     TIMESTAMP,
    auto_approve    INTEGER DEFAULT 0,
    is_urgent       INTEGER DEFAULT 0,
    priority        INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS auto_approve_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    content_type    TEXT DEFAULT '*',
    platform        TEXT DEFAULT '*',
    condition_field TEXT NOT NULL DEFAULT 'content_data',
    condition_op    TEXT NOT NULL DEFAULT 'contains' CHECK (condition_op IN ('contains','equals','matches','length_lt','length_gt')),
    condition_value TEXT NOT NULL,
    is_active       INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS approval_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id      INTEGER NOT NULL,
    action          TEXT NOT NULL CHECK (action IN ('submitted','approved','rejected','auto_approved','modified','regenerated')),
    reviewer        TEXT DEFAULT 'system',
    note            TEXT DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

approval_queue_seed = [
    {
        "content_id": 101,
        "content_type": "caption",
        "platform": "tiktok",
        "content_data": '{"text": "Rating 5/5 buat Avoskin Miraculous Oil! ✨ Wajah jadi lebih kenyal dan glowing alami. Wajib coba! #avoskin #skincareindonesia #ugc"}',
        "product": "Avoskin Miraculous Refining Oil",
        "campaign_id": "camp_avoskin_q2",
        "status": "pending_review",
        "priority": 1,
    },
    {
        "content_id": 102,
        "content_type": "video",
        "platform": "instagram",
        "content_data": '{"video_path": "/output/scarlett_body_lotion_promo.mp4", "duration_sec": 45, "hook": "Ini body lotion termurah yang bikin putih dalam seminggu!"}',
        "preview_url": "/output/scarlett_body_lotion_preview.mp4",
        "product": "Scarlett Whitening Body Lotion",
        "campaign_id": "camp_scarlett_june",
        "status": "approved",
        "priority": 2,
        "reviewer": "admin_rina",
        "review_note": "Looks good, tambahin CTA di akhir",
        "reviewed_at": "2026-06-02T14:00:00",
    },
    {
        "content_id": 103,
        "content_type": "script",
        "platform": "tiktok",
        "content_data": '{"script": "Hari minggu gini enaknya pake Somethinc Vitamin C biar glowing seharian. Cara pakenya: tetesin 3 tetes, ratain ke wajah, lalu tepok-tepok lembut."}',
        "product": "Somethinc Vitamin C Serum",
        "campaign_id": "camp_somethinc_june",
        "status": "rejected",
        "priority": 0,
        "reviewer": "admin_rina",
        "review_note": "Hook kurang kuat, ganti opening biar lebih engaging",
        "reviewed_at": "2026-06-01T09:30:00",
    },
    {
        "content_id": 104,
        "content_type": "hashtag_set",
        "platform": "tiktok",
        "content_data": '{"hashtags": ["skincareindonesia", "skincareroutine", "wardah", "halalskincare", "fyp", "ugc", "reviewskincare"]}',
        "product": "Wardah Perfect Bright Moisturizer",
        "campaign_id": "camp_wardah_june",
        "status": "auto_approved",
        "auto_approve": 1,
        "priority": 0,
    },
    {
        "content_id": 105,
        "content_type": "caption",
        "platform": "tiktok",
        "content_data": '{"text": "Review jujur Dear Me Beauty UV Shield SPF 50! No whitecast, ringan, dan harga murah meriah. Rekomendasi banget buat daily use. #dearmebeauty #sunscreen #skincarelokal"}',
        "product": "Dear Me Beauty UV Shield SPF 50",
        "campaign_id": "camp_dearme_june",
        "status": "pending_review",
        "priority": 1,
        "is_urgent": 1,
    },
]

auto_approve_rules_seed = [
    {
        "name": "Auto approve hashtag sets",
        "content_type": "hashtag_set",
        "platform": "*",
        "condition_field": "content_data",
        "condition_op": "contains",
        "condition_value": "hashtags",
    },
    {
        "name": "Approve known product mentions",
        "content_type": "caption",
        "platform": "tiktok",
        "condition_field": "content_data",
        "condition_op": "contains",
        "condition_value": "avoskin",
    },
]

approval_log_seed = [
    {"content_id": 101, "action": "submitted", "reviewer": "system", "note": "Caption auto-generated for Avoskin campaign"},
    {"content_id": 102, "action": "submitted", "reviewer": "system", "note": "Video uploaded for Scarlett campaign"},
    {"content_id": 102, "action": "approved", "reviewer": "admin_rina", "note": "Looks good, tambahin CTA di akhir"},
    {"content_id": 103, "action": "submitted", "reviewer": "system", "note": "Script generated for Somethinc"},
    {"content_id": 103, "action": "rejected", "reviewer": "admin_rina", "note": "Hook kurang kuat"},
    {"content_id": 104, "action": "auto_approved", "reviewer": "system", "note": "Auto-approved by rule: hashtag_set"},
    {"content_id": 105, "action": "submitted", "reviewer": "system", "note": "Urgent caption for Dear Me campaign"},
]


def seed_db(db_path: str, schema: str, inserts: list[tuple[str, list[tuple]]]) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(schema)
    for sql, rows in inserts:
        for row in rows:
            conn.execute(sql, row)
    conn.commit()
    conn.close()


def seed_gallery():
    cols = ("title", "slug", "description", "video_path", "thumbnail_path",
            "duration_sec", "platform", "niche", "product", "tags", "og_image",
            "views", "likes", "shares", "seo_published")
    placeholders = ",".join("?" for _ in cols)
    sql = f"INSERT OR IGNORE INTO gallery_videos {cols} VALUES ({placeholders})"
    rows = [
        tuple(v.get(c, "") for c in cols)
        for v in gallery_seed
    ]
    seed_db(str(DATA_DIR / "gallery.db"), GALLERY_SCHEMA, [(sql, rows)])
    print("✓ Gallery seeded: gallery.db")


def seed_inbox():
    msg_cols = ("platform", "account_id", "sender_username", "sender_name",
                "message_type", "content", "media_url", "parent_id",
                "is_read", "is_urgent", "sentiment", "ai_suggested_reply",
                "ai_reply_approved", "reply_sent", "reply_text", "replied_at")
    msg_ph = ",".join("?" for _ in msg_cols)
    msg_sql = f"INSERT INTO inbox_messages {msg_cols} VALUES ({msg_ph})"
    msg_rows = [
        tuple(m.get(c, "") if c not in ("is_read", "is_urgent", "ai_reply_approved", "reply_sent") else m.get(c, 0)
              for c in msg_cols)
        for m in inbox_messages_seed
    ]
    # Convert booleans correctly
    msg_rows_fixed = []
    for m in inbox_messages_seed:
        row = tuple(
            m.get(c, "" if m.get(c) is not None else "")
            for c in msg_cols
        )
        msg_rows_fixed.append(row)

    rule_cols = ("platform", "keyword_pattern", "reply_template", "sentiment_match")
    rule_ph = ",".join("?" for _ in rule_cols)
    rule_sql = f"INSERT INTO inbox_auto_reply_rules {rule_cols} VALUES ({rule_ph})"
    rule_rows = [tuple(r[c] for c in rule_cols) for r in inbox_rules_seed]

    muted_cols = ("platform", "username", "reason")
    muted_ph = ",".join("?" for _ in muted_cols)
    muted_sql = f"INSERT INTO inbox_muted_users {muted_cols} VALUES ({muted_ph})"
    muted_rows = [tuple(m[c] for c in muted_cols) for m in inbox_muted_seed]

    seed_db(str(DATA_DIR / "inbox.db"), INBOX_SCHEMA, [
        (msg_sql, msg_rows_fixed),
        (rule_sql, rule_rows),
        (muted_sql, muted_rows),
    ])
    print("✓ Inbox seeded: inbox.db")


def seed_approval():
    queue_cols = ("content_id", "content_type", "platform", "content_data",
                  "preview_url", "product", "campaign_id", "status",
                  "reviewer", "review_note", "reviewed_at",
                  "auto_approve", "is_urgent", "priority")
    queue_ph = ",".join("?" for _ in queue_cols)
    queue_sql = f"INSERT INTO approval_queue {queue_cols} VALUES ({queue_ph})"
    queue_rows = []
    for q in approval_queue_seed:
        row = tuple(q.get(c, "") if c not in ("auto_approve", "is_urgent", "priority") else q.get(c, 0)
                    for c in queue_cols)
        queue_rows.append(row)

    rule_cols = ("name", "content_type", "platform", "condition_field", "condition_op", "condition_value")
    rule_ph = ",".join("?" for _ in rule_cols)
    rule_sql = f"INSERT INTO auto_approve_rules {rule_cols} VALUES ({rule_ph})"
    rule_rows = [tuple(r[c] for c in rule_cols) for r in auto_approve_rules_seed]

    log_cols = ("content_id", "action", "reviewer", "note")
    log_ph = ",".join("?" for _ in log_cols)
    log_sql = f"INSERT INTO approval_log {log_cols} VALUES ({log_ph})"
    log_rows = [tuple(l[c] for c in log_cols) for l in approval_log_seed]

    seed_db(str(DATA_DIR / "approval.db"), APPROVAL_SCHEMA, [
        (queue_sql, queue_rows),
        (rule_sql, rule_rows),
        (log_sql, log_rows),
    ])
    print("✓ Approval seeded: approval.db")


def verify():
    print("\n── Gallery ──")
    conn = sqlite3.connect(str(DATA_DIR / "gallery.db"))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, title, product, views, likes, niche FROM gallery_videos").fetchall()
    for r in rows:
        print(f"  [{r['id']}] {r['title']} | {r['product']} | {r['views']} views, {r['likes']} likes")
    conn.close()

    print("\n── Inbox Messages ──")
    conn = sqlite3.connect(str(DATA_DIR / "inbox.db"))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, platform, sender_username, sentiment, substr(content,1,50) AS snippet FROM inbox_messages").fetchall()
    for r in rows:
        print(f"  [{r['id']}] {r['platform']} @{r['sender_username']} [{r['sentiment']}] {r['snippet']}...")
    rules = conn.execute("SELECT id, keyword_pattern, substr(reply_template,1,40) AS tpl FROM inbox_auto_reply_rules").fetchall()
    print("  Auto-reply rules:", len(rules))
    muted = conn.execute("SELECT username, reason FROM inbox_muted_users").fetchall()
    print("  Muted users:", len(muted))
    conn.close()

    print("\n── Approval Queue ──")
    conn = sqlite3.connect(str(DATA_DIR / "approval.db"))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, content_id, content_type, status, product FROM approval_queue").fetchall()
    for r in rows:
        print(f"  [{r['id']}] #{r['content_id']} {r['content_type']} | {r['status']} | {r['product']}")
    log = conn.execute("SELECT id, action, reviewer, substr(note,1,40) AS note FROM approval_log").fetchall()
    print(f"  Approval log entries: {len(log)}")
    conn.close()


if __name__ == "__main__":
    seed_gallery()
    seed_inbox()
    seed_approval()
    verify()
