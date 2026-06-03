"""Approval Workflow — Human-in-the-Loop approval before posting.

When approval is enabled, generated content goes into a review queue:
  1. Content generated → status = "pending_review"
  2. Human (or auto-approve rule) reviews → approves/rejects/modifies
  3. Approved content → moves to posting queue
  4. Rejected content → gets feedback for regeneration

Inspired by SocialBlast approval workflows.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

log = logging.getLogger(__name__)

_APPROVAL_DB_PATH = Path(__file__).parents[1] / "data" / "approval.db"

_APPROVAL_SCHEMA = """
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
CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_queue(status);
CREATE INDEX IF NOT EXISTS idx_approval_created ON approval_queue(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_urgent ON approval_queue(is_urgent) WHERE is_urgent=1;

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


class ApprovalWorkflow:
    """Human-in-the-Loop approval before content goes live."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or str(_APPROVAL_DB_PATH)
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
            conn.executescript(_APPROVAL_SCHEMA)
            conn.commit()

    def submit(self, content_id: int, content_type: str, content_data: str,
               platform: str = "tiktok", preview_url: str = "",
               product: str = "", campaign_id: str = "",
               auto_approve: bool = False, priority: int = 0) -> int:
        now = datetime.now(timezone.utc).isoformat()
        status = "pending_review"

        if auto_approve:
            status = "auto_approved"

        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """INSERT INTO approval_queue
                       (content_id, content_type, platform, content_data,
                        preview_url, product, campaign_id, status,
                        auto_approve, priority, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (content_id, content_type, platform, content_data,
                     preview_url, product, campaign_id, status,
                     1 if auto_approve else 0, priority, now, now),
                )
                conn.commit()
                aw_id = cur.lastrowid
                self._log_action(content_id, "auto_approved" if auto_approve else "submitted")
                return aw_id
            finally:
                conn.close()

    def approve(self, approval_id: int, reviewer: str = "admin",
                note: str = "") -> bool:
        conn = self._connect()
        try:
            row = conn.execute("SELECT content_id FROM approval_queue WHERE id=?", (approval_id,)).fetchone()
            if not row:
                return False
            conn.execute(
                """UPDATE approval_queue
                   SET status='approved', reviewer=?, review_note=?,
                       reviewed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (reviewer, note, approval_id),
            )
            conn.commit()
            self._log_action(row["content_id"], "approved", reviewer, note)
            return True
        finally:
            conn.close()

    def reject(self, approval_id: int, reviewer: str = "admin",
               note: str = "") -> bool:
        conn = self._connect()
        try:
            row = conn.execute("SELECT content_id FROM approval_queue WHERE id=?", (approval_id,)).fetchone()
            if not row:
                return False
            conn.execute(
                """UPDATE approval_queue
                   SET status='rejected', reviewer=?, review_note=?,
                       reviewed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (reviewer, note, approval_id),
            )
            conn.commit()
            self._log_action(row["content_id"], "rejected", reviewer, note)
            return True
        finally:
            conn.close()

    def list_pending(self, content_type: str = "", platform: str = "",
                     limit: int = 50) -> List[dict]:
        conn = self._connect()
        try:
            conditions = ["status = 'pending_review'"]
            params = []
            if content_type:
                conditions.append("content_type = ?")
                params.append(content_type)
            if platform:
                conditions.append("platform = ?")
                params.append(platform)

            rows = conn.execute(
                f"""SELECT * FROM approval_queue
                    WHERE {' AND '.join(conditions)}
                    ORDER BY priority DESC, is_urgent DESC, created_at ASC
                    LIMIT ?""",
                params + [limit],
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_history(self, limit: int = 20) -> List[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM approval_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = self._connect()
        try:
            pending = conn.execute("SELECT COUNT(*) as c FROM approval_queue WHERE status='pending_review'").fetchone()["c"]
            approved = conn.execute("SELECT COUNT(*) as c FROM approval_queue WHERE status='approved'").fetchone()["c"]
            rejected = conn.execute("SELECT COUNT(*) as c FROM approval_queue WHERE status='rejected'").fetchone()["c"]
            auto = conn.execute("SELECT COUNT(*) as c FROM approval_queue WHERE status='auto_approved'").fetchone()["c"]
            by_type = conn.execute(
                "SELECT content_type, COUNT(*) as cnt FROM approval_queue GROUP BY content_type"
            ).fetchall()
            return {
                "pending_review": pending,
                "approved": approved,
                "rejected": rejected,
                "auto_approved": auto,
                "total": pending + approved + rejected + auto,
                "by_type": [dict(r) for r in by_type],
            }
        finally:
            conn.close()

    def add_auto_approve_rule(self, name: str, condition_field: str = "content_data",
                              condition_op: str = "contains", condition_value: str = "",
                              content_type: str = "*", platform: str = "*") -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO auto_approve_rules
                   (name, content_type, platform, condition_field, condition_op, condition_value)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, content_type, platform, condition_field, condition_op, condition_value),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def _log_action(self, content_id: int, action: str,
                    reviewer: str = "system", note: str = "") -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO approval_log (content_id, action, reviewer, note) VALUES (?, ?, ?, ?)",
                (content_id, action, reviewer, note),
            )
            conn.commit()
        finally:
            conn.close()
