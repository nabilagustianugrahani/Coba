"""Session manager for social/ecom platform credentials.

Stores auth tokens, cookies, and proxy configs for platforms.
Patterns from:
  - steadfast: anti-detect browser session persistence
  - social-cookie-jar: paste-and-send cookie sharing
  - social-auto-upload: 10K stars, 7 platforms
  - instagrapi: Instagram session handling

Backends: file (default), Redis (env REDIS_URL), Postgres (env DATABASE_URL).
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional

log = logging.getLogger(__name__)


DEFAULT_SESSION_DIR = Path.home() / ".9router" / "sessions"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class SessionBackend(str, Enum):
    FILE = "file"
    REDIS = "redis"
    POSTGRES = "postgres"
    SQLITE = "sqlite"


@dataclass
class Session:
    platform: str
    username: str
    user_id: str = ""
    cookies: dict[str, str] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    proxy: str = ""
    device_id: str = ""
    user_agent: str = ""
    fingerprint: dict[str, Any] = field(default_factory=dict)
    status: str = SessionStatus.ACTIVE.value
    last_used: str = ""
    created_at: str = ""
    expires_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""

    def __post_init__(self) -> None:
        if not self.session_id:
            self.session_id = secrets.token_urlsafe(16)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.last_used:
            self.last_used = self.created_at

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except Exception:
            return False

    def touch(self) -> None:
        self.last_used = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Session":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class SessionStore:
    """Pluggable session storage backend.

    File backend: JSON files in ~/.9router/sessions/{platform}/{username}.json
    SQLite backend: ~/.9router/sessions.db
    Redis backend: env REDIS_URL, key prefix ugc:session:
    Postgres backend: env DATABASE_URL, table ugc_sessions
    """

    def __init__(self, backend: Optional[str] = None,
                 path: Optional[Path] = None) -> None:
        env_backend = os.environ.get("UGC_SESSION_BACKEND", "sqlite").lower()
        self.backend = SessionBackend(backend or env_backend)
        self.path = path or Path(os.environ.get("UGC_SESSION_DIR", str(DEFAULT_SESSION_DIR)))
        self.path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._sqlite_path = self.path / "sessions.db"
        self._init_backend()

    def _init_backend(self) -> None:
        if self.backend == SessionBackend.SQLITE or self.backend == SessionBackend.FILE:
            with self._sqlite_conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        platform TEXT NOT NULL,
                        username TEXT NOT NULL,
                        data TEXT NOT NULL,
                        status TEXT NOT NULL,
                        last_used TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT,
                        UNIQUE(platform, username)
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_platform ON sessions(platform)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON sessions(status)")
                conn.commit()

    @contextmanager
    def _sqlite_conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._sqlite_path), timeout=30, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _redis(self) -> Any:
        if not hasattr(self, "_redis_client"):
            try:
                import redis
            except ImportError as e:
                raise RuntimeError("redis package not installed") from e
            url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            self._redis_client = redis.from_url(url)
        return self._redis_client

    def _pg(self) -> Any:
        if not hasattr(self, "_pg_conn"):
            try:
                import psycopg2
            except ImportError as e:
                raise RuntimeError("psycopg2 not installed") from e
            dsn = os.environ.get("DATABASE_URL")
            if not dsn:
                raise RuntimeError("DATABASE_URL not set")
            self._pg_conn = psycopg2.connect(dsn)
        return self._pg_conn

    def save(self, session: Session) -> None:
        with self._lock:
            session.touch()
            data = json.dumps(session.to_dict())
            if self.backend in (SessionBackend.SQLITE, SessionBackend.FILE):
                with self._sqlite_conn() as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sessions
                        (session_id, platform, username, data, status, last_used, created_at, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session.session_id, session.platform, session.username,
                            data, session.status, session.last_used,
                            session.created_at, session.expires_at,
                        ),
                    )
            elif self.backend == SessionBackend.REDIS:
                r = self._redis()
                key = f"ugc:session:{session.platform}:{session.username}"
                r.setex(key, 86400 * 30, data)
            elif self.backend == SessionBackend.POSTGRES:
                conn = self._pg()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO ugc_sessions (session_id, platform, username, data, status, last_used, created_at, expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (platform, username) DO UPDATE SET
                          data = EXCLUDED.data,
                          status = EXCLUDED.status,
                          last_used = EXCLUDED.last_used,
                          expires_at = EXCLUDED.expires_at
                        """,
                        (
                            session.session_id, session.platform, session.username,
                            data, session.status, session.last_used,
                            session.created_at, session.expires_at,
                        ),
                    )
                conn.commit()
            log.info("session.saved platform=%s username=%s", session.platform, session.username)

    def get(self, platform: str, username: str) -> Optional[Session]:
        with self._lock:
            if self.backend in (SessionBackend.SQLITE, SessionBackend.FILE):
                with self._sqlite_conn() as conn:
                    row = conn.execute(
                        "SELECT data FROM sessions WHERE platform=? AND username=?",
                        (platform, username),
                    ).fetchone()
                    if not row:
                        return None
                    return Session.from_dict(json.loads(row["data"]))
            elif self.backend == SessionBackend.REDIS:
                r = self._redis()
                key = f"ugc:session:{platform}:{username}"
                raw = r.get(key)
                if not raw:
                    return None
                return Session.from_dict(json.loads(raw))
            elif self.backend == SessionBackend.POSTGRES:
                conn = self._pg()
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT data FROM ugc_sessions WHERE platform=%s AND username=%s",
                        (platform, username),
                    )
                    row = cur.fetchone()
                if not row:
                    return None
                return Session.from_dict(json.loads(row[0]))
        return None

    def delete(self, platform: str, username: str) -> bool:
        with self._lock:
            if self.backend in (SessionBackend.SQLITE, SessionBackend.FILE):
                with self._sqlite_conn() as conn:
                    cur = conn.execute(
                        "DELETE FROM sessions WHERE platform=? AND username=?",
                        (platform, username),
                    )
                    return cur.rowcount > 0
            elif self.backend == SessionBackend.REDIS:
                r = self._redis()
                return bool(r.delete(f"ugc:session:{platform}:{username}"))
            elif self.backend == SessionBackend.POSTGRES:
                conn = self._pg()
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM ugc_sessions WHERE platform=%s AND username=%s",
                        (platform, username),
                    )
                conn.commit()
                return cur.rowcount > 0
        return False

    def list_all(self, platform: Optional[str] = None,
                 status: Optional[str] = None) -> list[Session]:
        out: list[Session] = []
        with self._lock:
            if self.backend in (SessionBackend.SQLITE, SessionBackend.FILE):
                with self._sqlite_conn() as conn:
                    sql = "SELECT data FROM sessions"
                    params: list[Any] = []
                    if platform:
                        sql += " WHERE platform=?"
                        params.append(platform)
                    if status:
                        sql += " AND status=?" if platform else " WHERE status=?"
                        params.append(status)
                    for row in conn.execute(sql, params).fetchall():
                        try:
                            out.append(Session.from_dict(json.loads(row["data"])))
                        except Exception as e:
                            log.warning("Failed to parse session: %s", e)
            elif self.backend == SessionBackend.REDIS:
                r = self._redis()
                pattern = f"ugc:session:{platform}:*" if platform else "ugc:session:*"
                for key in r.scan_iter(match=pattern, count=200):
                    raw = r.get(key)
                    if raw:
                        try:
                            out.append(Session.from_dict(json.loads(raw)))
                        except Exception:
                            pass
        return out

    def cleanup_expired(self) -> int:
        count = 0
        for s in self.list_all():
            if s.is_expired():
                self.delete(s.platform, s.username)
                count += 1
        log.info("session.cleanup removed %d expired", count)
        return count

    def stats(self) -> dict[str, Any]:
        all_sessions = self.list_all()
        by_platform: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for s in all_sessions:
            by_platform[s.platform] = by_platform.get(s.platform, 0) + 1
            by_status[s.status] = by_status.get(s.status, 0) + 1
        return {
            "backend": self.backend.value,
            "total": len(all_sessions),
            "by_platform": by_platform,
            "by_status": by_status,
        }


class SessionManager:
    """High-level session management facade.

    Combines SessionStore with platform-specific loaders and validators.
    Provides import-from-cookies-jar pattern from social-cookie-jar lib.
    """

    SUPPORTED_PLATFORMS: list[str] = [
        "tiktok", "instagram", "youtube", "twitter", "x",
        "facebook", "threads", "linkedin", "reddit", "pinterest",
        "xiaohongshu", "douyin", "bilibili", "weibo",
        "shopee", "tiktokshop", "lazada", "tokopedia",
    ]

    def __init__(self, store: Optional[SessionStore] = None) -> None:
        self.store = store or SessionStore()

    def import_cookies(self, platform: str, username: str,
                       cookies: dict[str, str],
                       headers: Optional[dict[str, str]] = None,
                       proxy: str = "",
                       user_agent: str = "",
                       fingerprint: Optional[dict[str, Any]] = None) -> Session:
        s = Session(
            platform=platform,
            username=username,
            cookies=cookies,
            headers=headers or {},
            proxy=proxy,
            user_agent=user_agent or self._default_ua(platform),
            fingerprint=fingerprint or {},
        )
        self.store.save(s)
        return s

    def import_from_browser(self, platform: str, username: str,
                            browser: str = "chrome",
                            profile: str = "Default") -> Optional[Session]:
        try:
            import browser_cookie3
        except ImportError as e:
            raise RuntimeError(
                "browser_cookie3 not installed. Run: pip install browser-cookie3"
            ) from e
        loader = getattr(browser_cookie3, browser, None) if browser else None
        if loader is None:
            raise ValueError(f"Unknown browser: {browser}")
        try:
            cj = loader(domain_name=self._cookie_domain(platform))
        except Exception as e:
            log.warning("browser_cookie3 failed for %s: %s", platform, e)
            return None
        cookies = {c.name: c.value for c in cj}
        if not cookies:
            return None
        return self.import_cookies(platform, username, cookies=cookies)

    def get(self, platform: str, username: str) -> Optional[Session]:
        s = self.store.get(platform, username)
        if s and s.is_expired():
            s.status = SessionStatus.EXPIRED.value
            self.store.save(s)
        return s

    def revoke(self, platform: str, username: str) -> bool:
        s = self.store.get(platform, username)
        if not s:
            return False
        s.status = SessionStatus.REVOKED.value
        self.store.save(s)
        return True

    def health_check(self, platform: str, username: str) -> dict[str, Any]:
        s = self.get(platform, username)
        if not s:
            return {"platform": platform, "username": username, "status": "missing"}
        return {
            "platform": platform,
            "username": username,
            "status": s.status,
            "expired": s.is_expired(),
            "last_used": s.last_used,
            "has_cookies": bool(s.cookies),
            "has_tokens": bool(s.tokens),
        }

    def _cookie_domain(self, platform: str) -> str:
        return {
            "tiktok": "tiktok.com",
            "instagram": "instagram.com",
            "youtube": "youtube.com",
            "twitter": "twitter.com",
            "x": "x.com",
            "facebook": "facebook.com",
            "threads": "threads.net",
            "linkedin": "linkedin.com",
            "reddit": "reddit.com",
            "pinterest": "pinterest.com",
            "xiaohongshu": "xiaohongshu.com",
            "douyin": "douyin.com",
            "bilibili": "bilibili.com",
            "weibo": "weibo.com",
            "shopee": "shopee.co.id",
            "tiktokshop": "tiktok.com",
            "lazada": "lazada.co.id",
            "tokopedia": "tokopedia.com",
        }.get(platform, "")

    def _default_ua(self, platform: str) -> str:
        if platform in ("tiktok", "tiktokshop", "douyin"):
            return "com.zhiliaoapp.musically/2023400040 (Linux; U; Android 13; id; SM-G998B; Build/RP1A.200720.012; Cronet/TTNetVersion:5f9b4e23 2023-08-15 QuicVersion:2bac2e2b 2023-07-12)"
        if platform in ("instagram", "threads"):
            return "Instagram 317.0.0.34.109 Android (33/13; 420dpi; 1080x2400; samsung; SM-G991B; o1s; exynos2100; en_US; 545229118)"
        if platform in ("twitter", "x"):
            return "TwitterAndroid/10.65.0-release.0 (110090000-4500) Google Pixel 7 (Android 13)"
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


__all__ = [
    "Session",
    "SessionBackend",
    "SessionStatus",
    "SessionStore",
    "SessionManager",
    "DEFAULT_SESSION_DIR",
]
