"""Brand Profile — consistent tone, voice, language, and style for all content.

Every generated script, caption, and video respects the active brand profile.
Supports:
  - Multiple brand profiles (switch per campaign)
  - Tone (professional, casual, humorous, aspirational, urgent)
  - Voice characteristics (formal, friendly, authoritative, playful)
  - Language preferences (English, Indonesian, mix)
  - Color palette for thumbnails/templates
  - Target audience description
  - Hashtag bank
  - CTA preferences

Inspired by TryPost brand profiles.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

log = logging.getLogger(__name__)

_BRAND_DB_PATH = Path(__file__).parents[1] / "data" / "brand_profiles.db"

_BRAND_SCHEMA = """
CREATE TABLE IF NOT EXISTS brand_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    tone            TEXT NOT NULL DEFAULT 'casual' CHECK (tone IN ('professional','casual','humorous','aspirational','urgent','luxury','educational')),
    voice           TEXT NOT NULL DEFAULT 'friendly' CHECK (voice IN ('formal','friendly','authoritative','playful','empathetic','bold')),
    language        TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en','id','mix')),
    target_audience TEXT DEFAULT '',
    color_palette   TEXT DEFAULT '["#7b2ff7","#00d4ff","#ffffff"]',
    emoji_style     TEXT DEFAULT 'moderate' CHECK (emoji_style IN ('none','minimal','moderate','heavy')),
    hashtag_bank    TEXT DEFAULT '',
    default_cta     TEXT DEFAULT 'Link in bio!',
    description     TEXT DEFAULT '',
    is_active       INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS brand_scripts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id      INTEGER NOT NULL,
    hook_type       TEXT NOT NULL DEFAULT 'problem',
    template        TEXT NOT NULL,
    variable_slots  TEXT DEFAULT '[]',
    platform        TEXT DEFAULT '*',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class BrandProfile:
    """Manage brand profiles for consistent content generation."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or str(_BRAND_DB_PATH)
        self._lock = threading.Lock()
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_BRAND_SCHEMA)
            conn.commit()
            if not conn.execute("SELECT id FROM brand_profiles LIMIT 1").fetchone():
                self._seed_default()

    def _seed_default(self) -> None:
        defaults = [
            {
                "name": "Default Casual",
                "tone": "casual", "voice": "friendly", "language": "en",
                "target_audience": "Gen Z and Millennials interested in lifestyle products",
                "color_palette": json.dumps(["#7b2ff7", "#00d4ff", "#ffffff"]),
                "emoji_style": "moderate",
                "hashtag_bank": "#ugc #productreview #musttry",
                "default_cta": "Link in bio!",
                "description": "Default casual UGC brand voice",
                "is_active": 1,
            },
            {
                "name": "Professional",
                "tone": "professional", "voice": "authoritative", "language": "en",
                "target_audience": "Business professionals aged 25-45",
                "color_palette": json.dumps(["#1a1a2e", "#16213e", "#0f3460"]),
                "emoji_style": "none",
                "hashtag_bank": "#business #professional #innovation",
                "default_cta": "Learn more at the link above",
                "description": "Professional authoritative tone for B2B content",
                "is_active": 0,
            },
            {
                "name": "Indonesia Casual",
                "tone": "casual", "voice": "playful", "language": "id",
                "target_audience": "Pengguna TikTok dan IG usia 18-35 di Indonesia",
                "color_palette": json.dumps(["#ff6b6b", "#feca57", "#48dbfb"]),
                "emoji_style": "heavy",
                "hashtag_bank": "#fyp #viral #produkindonesia #recommended",
                "default_cta": "Klik link di bio yuk!",
                "description": "Indonesian casual playful voice for local audience",
                "is_active": 0,
            },
        ]
        for bp in defaults:
            self.create(bp)

    def create(self, data: Dict[str, Any]) -> int:
        now = datetime.utcnow().isoformat()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """INSERT INTO brand_profiles
                       (name, tone, voice, language, target_audience,
                        color_palette, emoji_style, hashtag_bank,
                        default_cta, description, is_active, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (data["name"], data.get("tone", "casual"),
                     data.get("voice", "friendly"), data.get("language", "en"),
                     data.get("target_audience", ""),
                     json.dumps(data.get("color_palette", ["#7b2ff7", "#00d4ff", "#ffffff"])),
                     data.get("emoji_style", "moderate"),
                     data.get("hashtag_bank", ""), data.get("default_cta", "Link in bio!"),
                     data.get("description", ""), data.get("is_active", 0), now, now),
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def get(self, profile_id: int) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM brand_profiles WHERE id=?", (profile_id,)).fetchone()
            if row:
                d = dict(row)
                try:
                    d["color_palette"] = json.loads(d.get("color_palette", "[]"))
                except (json.JSONDecodeError, TypeError):
                    d["color_palette"] = ["#7b2ff7", "#00d4ff", "#ffffff"]
                return d
            return None
        finally:
            conn.close()

    def get_active(self) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM brand_profiles WHERE is_active=1 LIMIT 1").fetchone()
            if row:
                d = dict(row)
                try:
                    d["color_palette"] = json.loads(d.get("color_palette", "[]"))
                except (json.JSONDecodeError, TypeError):
                    d["color_palette"] = ["#7b2ff7", "#00d4ff", "#ffffff"]
                return d
            return None
        finally:
            conn.close()

    def set_active(self, profile_id: int) -> bool:
        conn = self._connect()
        try:
            conn.execute("UPDATE brand_profiles SET is_active=0")
            conn.execute("UPDATE brand_profiles SET is_active=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (profile_id,))
            conn.commit()
            return True
        except Exception as e:
            log.error("[brand] set_active failed: %s", e)
            return False
        finally:
            conn.close()

    def update(self, profile_id: int, data: Dict[str, Any]) -> bool:
        fields = []
        params = []
        for key in ("name", "tone", "voice", "language", "target_audience",
                     "emoji_style", "hashtag_bank", "default_cta", "description"):
            if key in data:
                fields.append(f"{key}=?")
                params.append(data[key])
        if "color_palette" in data:
            fields.append("color_palette=?")
            params.append(json.dumps(data["color_palette"]))
        if not fields:
            return False
        fields.append("updated_at=CURRENT_TIMESTAMP")
        params.append(profile_id)
        conn = self._connect()
        try:
            conn.execute(f"UPDATE brand_profiles SET {', '.join(fields)} WHERE id=?", params)
            conn.commit()
            return True
        finally:
            conn.close()

    def list_all(self) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM brand_profiles ORDER BY is_active DESC, name ASC").fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["color_palette"] = json.loads(d.get("color_palette", "[]"))
                except (json.JSONDecodeError, TypeError):
                    d["color_palette"] = ["#7b2ff7", "#00d4ff", "#ffffff"]
                result.append(d)
            return result
        finally:
            conn.close()

    def delete(self, profile_id: int) -> bool:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM brand_profiles WHERE id=?", (profile_id,))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    def get_system_prompt(self) -> str:
        """Get an AI system prompt for the active brand profile."""
        bp = self.get_active()
        if not bp:
            return ""
        palette_str = ", ".join(bp.get("color_palette", []))
        return (
            f"Brand Voice: {bp['voice']}\n"
            f"Tone: {bp['tone']}\n"
            f"Language: {bp['language']}\n"
            f"Target Audience: {bp.get('target_audience', 'General')}\n"
            f"Emoji Style: {bp.get('emoji_style', 'moderate')}\n"
            f"Color Palette: {palette_str}\n"
            f"Default CTA: {bp.get('default_cta', 'Link in bio!')}\n"
            f"Hashtag Bank: {bp.get('hashtag_bank', '')}"
        )
