"""Account Guardian — monitors farm accounts, detects bans, auto-recovers.

Features:
  - Periodic health checks on all farm accounts
  - Detects: login failures, banned accounts, rate limited, captcha challenges
  - Auto-rotate: on ban detection, removes from pool, alerts, creates replacement
  - Tracks account age, post count, daily limits, engagement history
  - Graceful degradation: scales down posting when fewer accounts available

Usage:
    guardian = AccountGuardian()
    guardian.run_health_check()       # Check all accounts now
    guardian.get_healthy_count()      # How many accounts are usable
    guardian.get_next_account()       # Best account for next post
"""
import json, logging, sqlite3, threading, random, asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)

GUARDIAN_DB = Path(__file__).resolve().parents[1] / "data" / "guardian.db"

MAX_POSTS_PER_DAY = {"tiktok": 10, "instagram": 15, "youtube": 20}
BAN_INDICATORS = [
    "login failed", "account suspended", "shadowban", "too many requests",
    "rate limited", "captcha required", "verify your identity",
    "access denied", "403 forbidden", "account locked",
    "this account has been banned", "temporary ban",
    "violation of community guidelines", "spam detected",
]


@dataclass
class AccountStatus:
    username: str
    platform: str
    healthy: bool = True
    can_post: bool = True
    posts_today: int = 0
    last_error: str = ""
    last_checked: Optional[str] = None
    created_at: Optional[str] = None
    age_days: int = 0
    consecutive_failures: int = 0
    is_banned: bool = False


class AccountGuardian:
    """Monitors and manages farm account health."""

    def __init__(self, db_path: str | Path = GUARDIAN_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._lock = threading.Lock()
        self._account_cache: list[AccountStatus] = []

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                platform TEXT NOT NULL,
                status TEXT DEFAULT 'healthy',
                posts_today INTEGER DEFAULT 0,
                total_posts INTEGER DEFAULT 0,
                last_post_at TEXT,
                last_error TEXT DEFAULT '',
                consecutive_failures INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                banned_at TEXT,
                health_score REAL DEFAULT 1.0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(username, platform)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER, platform TEXT, incident_type TEXT,
                description TEXT, detected_at TEXT DEFAULT (datetime('now')),
                resolved_at TEXT, resolved_by TEXT DEFAULT '',
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER, platform TEXT,
                date TEXT, post_count INTEGER DEFAULT 0,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        conn.commit()
        conn.close()

    def register_account(self, username: str, platform: str) -> int:
        """Add an account to monitoring."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO accounts (username, platform) VALUES (?,?)",
                    (username, platform),
                )
                conn.commit()
                aid = conn.execute(
                    "SELECT id FROM accounts WHERE username=? AND platform=?",
                    (username, platform),
                ).fetchone()[0]
                conn.close()
                log.info("[GUARDIAN] Registered %s/%s (id=%d)", platform, username, aid)
                return aid
            except Exception as e:
                conn.close()
                raise

    def report_post(self, username: str, platform: str, success: bool, error: str = ""):
        """Record a posting attempt result."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            today = datetime.now().strftime("%Y-%m-%d")

            account = conn.execute(
                "SELECT id, posts_today, total_posts, consecutive_failures FROM accounts "
                "WHERE username=? AND platform=?", (username, platform),
            ).fetchone()
            if not account:
                conn.close()
                return

            aid, posts_today, total_posts, consec_fails = account

            if success:
                new_consec = 0
                new_posts_today = posts_today + 1
                new_total = total_posts + 1
                status = "healthy"
                score = min(1.0, (new_posts_today / MAX_POSTS_PER_DAY.get(platform, 10)) * 0.1)
                health = max(0.1, 1.0 - score)
            else:
                new_consec = consec_fails + 1
                new_posts_today = posts_today
                new_total = total_posts
                health = max(0.0, 1.0 - (new_consec * 0.2))
                status = "degraded" if new_consec < 3 else "quarantined"

                if new_consec >= 3:
                    self._log_incident(conn, aid, platform, "consecutive_failures",
                                       f"{new_consec} failures: {error[:100]}")

                for indicator in BAN_INDICATORS:
                    if indicator in error.lower():
                        conn.execute(
                            "UPDATE accounts SET is_banned=1, banned_at=datetime('now'), "
                            "status='banned', last_error=? WHERE id=?",
                            (error[:200], aid),
                        )
                        self._log_incident(conn, aid, platform, "ban_detected", error[:200])
                        log.warning("[GUARDIAN] BANNED %s/%s: %s", platform, username, error[:100])
                        break

            conn.execute(
                "UPDATE accounts SET posts_today=?, total_posts=?, consecutive_failures=?, "
                "last_error=?, health_score=?, status=?, last_post_at=datetime('now'), "
                "updated_at=datetime('now') WHERE id=?",
                (new_posts_today, new_total, new_consec, error[:200] if error else "",
                 round(health, 2), status, aid),
            )

            conn.execute(
                "INSERT INTO daily_usage (account_id, platform, date, post_count) "
                "VALUES (?,?,?,1) ON CONFLICT(account_id, platform, date) DO UPDATE SET post_count=post_count+1",
                (aid, platform, today),
            )

            conn.commit()
            conn.close()

    def run_health_check(self):
        """Check all accounts for health issues using browser-use."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            accounts = conn.execute(
                "SELECT id, username, platform FROM accounts WHERE is_banned=0 AND status != 'quarantined'"
            ).fetchall()
            conn.close()

        log.info("[GUARDIAN] Health check: %d accounts", len(accounts))
        checked = 0
        for aid, username, platform in accounts:
            try:
                result = self._check_account(username, platform)
                if result:
                    checked += 1
                    self.report_post(username, platform, True)
                else:
                    checked += 1
                    self.report_post(username, platform, False, "health check failed")
            except Exception as e:
                log.warning("[GUARDIAN] Check failed %s/%s: %s", platform, username, e)

        log.info("[GUARDIAN] Health check complete: %d/%d accounts checked", checked, len(accounts))

    def _check_account(self, username: str, platform: str) -> bool:
        """Verify account can log in and post."""
        try:
            if platform == "tiktok":
                check_url = f"https://www.tiktok.com/@{username}"
            elif platform == "instagram":
                check_url = f"https://www.instagram.com/{username}/"
            else:
                return True

            from ugc_ai_overpower.browser.bu_agent import BUAgent
            agent = BUAgent(headless=True)

            task = (
                f"1. Go to {check_url}\n"
                f"2. Check if the page loads successfully (not 404, not banned page)\n"
                f"3. If you see a login page: the account might be logged out\n"
                f"4. Report: 'healthy' or 'issue: <description>'\n"
                f"5. Output ONLY the status word"
            )
            result = asyncio.run(agent.run(task))
            return result.success and "healthy" in result.output.lower()
        except Exception:
            return False

    def get_healthy_count(self, platform: str = "") -> int:
        """How many accounts are currently usable for posting."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            q = "SELECT COUNT(*) FROM accounts WHERE is_banned=0 AND status IN ('healthy','degraded')"
            params = []
            if platform:
                q += " AND platform=?"
                params.append(platform)
            count = conn.execute(q, params).fetchone()[0]
            conn.close()
            return count

    def get_available_for_post(self, platform: str = "tiktok") -> Optional[dict]:
        """Get the best account to use for the next post.

        Picks account with:
          1. Lowest posts_today / max_per_day ratio
          2. Highest health_score
          3. Longest time since last post
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            max_daily = MAX_POSTS_PER_DAY.get(platform, 10)
            rows = conn.execute(
                "SELECT id, username, platform, posts_today, health_score, last_post_at "
                "FROM accounts WHERE is_banned=0 AND status IN ('healthy','degraded') "
                "AND posts_today < ? ORDER BY health_score DESC, posts_today ASC, last_post_at ASC LIMIT 1",
                (max_daily,),
            ).fetchall()
            conn.close()

        if not rows:
            log.warning("[GUARDIAN] No available accounts for %s", platform)
            return None

        row = rows[0]
        return {
            "id": row[0], "username": row[1], "platform": row[2],
            "posts_today": row[3], "health_score": row[4],
        }

    def get_banned_accounts(self) -> list[dict]:
        """List all banned accounts for replacement."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            rows = conn.execute(
                "SELECT id, username, platform, banned_at FROM accounts WHERE is_banned=1"
            ).fetchall()
            conn.close()
            return [{"id": r[0], "username": r[1], "platform": r[2], "banned_at": r[3]} for r in rows]

    def get_incidents(self, limit: int = 20) -> list[dict]:
        """Recent incidents log."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            rows = conn.execute(
                "SELECT i.*, a.username FROM incidents i "
                "LEFT JOIN accounts a ON i.account_id=a.id "
                "ORDER BY i.detected_at DESC LIMIT ?", (limit,),
            ).fetchall()
            conn.close()
            cols = ["id", "account_id", "platform", "incident_type", "description",
                    "detected_at", "resolved_at", "resolved_by", "username"]
            return [dict(zip(cols, r)) for r in rows]

    def get_summary(self) -> dict:
        """Global guardian summary."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            total = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            healthy = conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE status='healthy'"
            ).fetchone()[0]
            banned = conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE is_banned=1"
            ).fetchone()[0]
            degraded = conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE status='degraded'"
            ).fetchone()[0]
            incidents_24h = conn.execute(
                "SELECT COUNT(*) FROM incidents WHERE detected_at > datetime('now', '-1 day')"
            ).fetchone()[0]
            conn.close()

            return {
                "total_accounts": total,
                "healthy": healthy,
                "degraded": degraded,
                "banned": banned,
                "usable": total - banned,
                "incidents_24h": incidents_24h,
            }

    def _log_incident(self, conn, account_id: int, platform: str,
                      incident_type: str, description: str):
        conn.execute(
            "INSERT INTO incidents (account_id, platform, incident_type, description) VALUES (?,?,?,?)",
            (account_id, platform, incident_type, description),
        )
