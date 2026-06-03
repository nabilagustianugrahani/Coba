"""Unified Social Inbox — all comments, DMs, mentions across platforms in one place.

Features:
  - SQLite-backed inbox collecting from all farm accounts
  - AI-powered reply suggestions (sentiment-aware)
  - Bulk reply, auto-reply rules, mute/block
  - Engagement analytics per account/platform

Inspired by BrightBean Studio (1.7k stars) unified social inbox.
"""

import json
import logging
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

log = logging.getLogger(__name__)

_INBOX_DB_PATH = Path(__file__).parents[1] / "data" / "social_inbox.db"

_INBOX_SCHEMA = """
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
CREATE INDEX IF NOT EXISTS idx_inbox_platform ON inbox_messages(platform);
CREATE INDEX IF NOT EXISTS idx_inbox_account ON inbox_messages(account_id);
CREATE INDEX IF NOT EXISTS idx_inbox_unread ON inbox_messages(is_read) WHERE is_read=0;
CREATE INDEX IF NOT EXISTS idx_inbox_urgent ON inbox_messages(is_urgent) WHERE is_urgent=1;
CREATE INDEX IF NOT EXISTS idx_inbox_sentiment ON inbox_messages(sentiment);
CREATE INDEX IF NOT EXISTS idx_inbox_created ON inbox_messages(created_at DESC);

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


class SocialInbox:
    """Unified social inbox pulling messages from all platforms."""

    def __init__(self, db_path: Optional[str] = None, ai_router=None):
        self._db_path = db_path or str(_INBOX_DB_PATH)
        self._lock = threading.Lock()
        self._ai = ai_router
        self._init_db()

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_INBOX_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def ingest(self, platform: str, account_id: str, sender_username: str,
               content: str, message_type: str = "comment",
               sender_name: str = "", media_url: str = "",
               parent_id: int = 0, sentiment: str = "neutral") -> int:
        now = datetime.now(timezone.utc).isoformat()
        is_urgent = 1 if sentiment == "urgent" else 0

        if self._is_muted(platform, sender_username):
            log.info("[inbox] Skipping muted user %s on %s", sender_username, platform)
            return 0

        ai_reply = ""
        if self._ai:
            try:
                ai_reply = self._generate_reply(content, sentiment, platform)
            except Exception as e:
                log.warning("[inbox] AI reply gen failed: %s", e)

        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """INSERT INTO inbox_messages
                       (platform, account_id, sender_username, sender_name,
                        message_type, content, media_url, parent_id,
                        is_urgent, sentiment, ai_suggested_reply, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (platform, account_id, sender_username, sender_name,
                     message_type, content, media_url, parent_id,
                     is_urgent, sentiment, ai_reply, now, now),
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def _is_muted(self, platform: str, username: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id FROM inbox_muted_users WHERE platform=? AND username=?",
                (platform, username),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def _generate_reply(self, content: str, sentiment: str, platform: str) -> str:
        if not self._ai:
            return ""

        sentiments = {
            "positive": "enthusiastic and grateful",
            "negative": "apologetic and helpful",
            "urgent": "immediate and helpful",
            "neutral": "friendly and engaging",
        }
        tone = sentiments.get(sentiment, "friendly")
        prompt = (
            f"You are a social media manager. Generate a short, natural reply (max 200 chars) "
            f"to this {platform} {sentiment} comment. Tone: {tone}. "
            f"Comment: \"{content}\"\n\nReply:"
        )
        try:
            result = self._ai.chat_structured(prompt)
            if isinstance(result, dict) and "reply" in result:
                return result["reply"][:200]
            if isinstance(result, str):
                return result.strip()[:200]
            return str(result)[:200]
        except Exception:
            return ""

    def get_unread_count(self, platform: str = "") -> int:
        conn = self._connect()
        try:
            conditions = ["is_read = 0"]
            params = []
            if platform:
                conditions.append("platform = ?")
                params.append(platform)
            row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM inbox_messages WHERE {' AND '.join(conditions)}",
                params,
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def list_messages(self, platform: str = "", status: str = "all",
                      limit: int = 50, offset: int = 0) -> List[dict]:
        conn = self._connect()
        try:
            conditions = []
            params = []
            if platform:
                conditions.append("platform = ?")
                params.append(platform)
            if status == "unread":
                conditions.append("is_read = 0")
            elif status == "urgent":
                conditions.append("is_urgent = 1")
            elif status == "unreplied":
                conditions.append("reply_sent = 0")

            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            rows = conn.execute(
                f"""SELECT id, platform, account_id, sender_username, sender_name,
                           message_type, content, media_url, is_read, is_urgent,
                           sentiment, ai_suggested_reply, reply_sent, reply_text,
                           replied_at, created_at
                    FROM inbox_messages {where}
                    ORDER BY is_urgent DESC, created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [limit, offset],
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def mark_read(self, message_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("UPDATE inbox_messages SET is_read=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (message_id,))
            conn.commit()
        finally:
            conn.close()

    def send_reply(self, message_id: int, reply_text: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                """UPDATE inbox_messages
                   SET reply_text=?, reply_sent=1, replied_at=?, updated_at=?
                   WHERE id=?""",
                (reply_text, now, now, message_id),
            )
            conn.commit()
            return True
        except Exception as e:
            log.error("[inbox] Send reply failed: %s", e)
            return False
        finally:
            conn.close()

    def approve_ai_reply(self, message_id: int) -> Optional[str]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT ai_suggested_reply FROM inbox_messages WHERE id=?",
                (message_id,),
            ).fetchone()
            if not row or not row["ai_suggested_reply"]:
                return None
            reply = row["ai_suggested_reply"]
            conn.execute(
                "UPDATE inbox_messages SET ai_reply_approved=1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (message_id,),
            )
            conn.commit()
            return reply
        finally:
            conn.close()

    def add_auto_reply_rule(self, platform: str, keyword_pattern: str,
                            reply_template: str, sentiment_match: str = "*") -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO inbox_auto_reply_rules
                   (platform, keyword_pattern, reply_template, sentiment_match)
                   VALUES (?, ?, ?, ?)""",
                (platform, keyword_pattern, reply_template, sentiment_match),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_auto_reply_rules(self) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM inbox_auto_reply_rules WHERE is_active=1 ORDER BY id").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def mute_user(self, platform: str, username: str, reason: str = "") -> bool:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO inbox_muted_users (platform, username, reason) VALUES (?, ?, ?)",
                (platform, username, reason),
            )
            conn.commit()
            return True
        except Exception as e:
            log.error("[inbox] Mute failed: %s", e)
            return False
        finally:
            conn.close()

    def unmute_user(self, platform: str, username: str) -> bool:
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM inbox_muted_users WHERE platform=? AND username=?",
                (platform, username),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) as c FROM inbox_messages").fetchone()["c"]
            unread = conn.execute("SELECT COUNT(*) as c FROM inbox_messages WHERE is_read=0").fetchone()["c"]
            urgent = conn.execute("SELECT COUNT(*) as c FROM inbox_messages WHERE is_urgent=1").fetchone()["c"]
            unreplied = conn.execute("SELECT COUNT(*) as c FROM inbox_messages WHERE reply_sent=0").fetchone()["c"]
            by_platform = conn.execute(
                "SELECT platform, COUNT(*) as cnt FROM inbox_messages GROUP BY platform ORDER BY cnt DESC"
            ).fetchall()
            by_sentiment = conn.execute(
                "SELECT sentiment, COUNT(*) as cnt FROM inbox_messages GROUP BY sentiment"
            ).fetchall()
            return {
                "total": total,
                "unread": unread,
                "urgent": urgent,
                "unreplied": unreplied,
                "by_platform": [dict(r) for r in by_platform],
                "by_sentiment": [dict(r) for r in by_sentiment],
            }
        finally:
            conn.close()

    def bulk_auto_reply(self, limit: int = 10) -> dict:
        replied = 0
        skipped = 0
        rules = self.list_auto_reply_rules()

        messages = self.list_messages(status="unreplied", limit=limit)
        for msg in messages:
            for rule in rules:
                if rule["platform"] != "*" and rule["platform"] != msg["platform"]:
                    continue
                if rule["sentiment_match"] != "*" and rule["sentiment_match"] != msg.get("sentiment", ""):
                    continue
                if re.search(rule["keyword_pattern"], msg["content"], re.IGNORECASE):
                    self.send_reply(msg["id"], rule["reply_template"])
                    replied += 1
                    break
            else:
                skipped += 1

        return {"replied": replied, "skipped": skipped}
