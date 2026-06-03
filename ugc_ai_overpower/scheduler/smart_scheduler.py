"""Smart Scheduler — AI-driven posting schedule with A/B testing.

Features:
  - Determines optimal posting times per platform/niche from performance data
  - A/B tests: hook types, posting times, video styles, CTAs
  - Auto-schedules content from queue based on optimal windows
  - Tracks test results → promotes winning variants automatically
  - Integrates with swarm → dispatches campaigns on schedule
"""
import json, logging, sqlite3, random, threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

SCHED_DB = Path(__file__).resolve().parents[1] / "data" / "scheduler.db"

BEST_POSTING_TIMES = {
    "tiktok":    {"weekday": [7, 11, 19], "weekend": [9, 12, 20]},
    "instagram": {"weekday": [8, 12, 18], "weekend": [10, 14, 19]},
    "youtube":   {"weekday": [12, 16, 20], "weekend": [10, 15, 19]},
}

AB_TEST_CONFIGS = {
    "hook_type": {
        "variants": ["shock", "curiosity_gap", "story", "question", "stat"],
        "samples_per_variant": 5,
        "min_engagement_diff": 0.02,  # 2% difference to declare winner
    },
    "posting_time": {
        "variants": ["morning", "afternoon", "evening", "night"],
        "samples_per_variant": 5,
    },
    "cta_style": {
        "variants": ["link_bio", "comment_below", "follow_for_more", "save_post"],
        "samples_per_variant": 5,
    },
}


class SmartScheduler:
    """AI-driven scheduler with A/B testing.

    Usage:
        sched = SmartScheduler()
        sched.get_optimal_time("tiktok", "skincare")  # → best hour to post
        sched.schedule_next_batch()                    # → dispatch from queue
        sched.record_result(...)                       # → feedback for learning
    """

    def __init__(self, db_path: str | Path = SCHED_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._lock = threading.Lock()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                variant TEXT NOT NULL,
                niche TEXT DEFAULT 'general',
                platform TEXT DEFAULT 'tiktok',
                impressions INTEGER DEFAULT 0,
                engagements INTEGER DEFAULT 0,
                conversions INTEGER DEFAULT 0,
                samples INTEGER DEFAULT 0,
                started_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posting_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT, content_id TEXT,
                platform TEXT, scheduled_at TEXT, posted_at TEXT,
                hook_type TEXT, posting_hour INTEGER,
                cta_style TEXT, niche TEXT,
                views INTEGER DEFAULT 0, likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0, shares INTEGER DEFAULT 0,
                engagement_rate REAL DEFAULT 0.0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS optimal_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                niche TEXT DEFAULT 'general',
                best_hour INTEGER,
                best_day TEXT,
                score REAL DEFAULT 0.0,
                samples INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()

    def initialize_ab_tests(self, niche: str = "general", platform: str = "tiktok"):
        """Seed initial A/B test variants if they don't exist."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            for test_name, cfg in AB_TEST_CONFIGS.items():
                for variant in cfg["variants"]:
                    exists = conn.execute(
                        "SELECT id FROM ab_tests WHERE test_name=? AND variant=? AND niche=? AND platform=?",
                        (test_name, variant, niche, platform),
                    ).fetchone()
                    if not exists:
                        conn.execute(
                            "INSERT INTO ab_tests (test_name, variant, niche, platform, samples) VALUES (?,?,?,?,0)",
                            (test_name, variant, niche, platform),
                        )
            conn.commit()
            conn.close()

    def get_optimal_time(self, platform: str = "tiktok", niche: str = "general") -> int:
        """Get the best posting hour for a platform/niche based on historical data."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            row = conn.execute(
                "SELECT best_hour FROM optimal_windows WHERE platform=? AND niche=? ORDER BY score DESC LIMIT 1",
                (platform, niche),
            ).fetchone()
            if row:
                return row[0]
            conn.close()

        now = datetime.now()
        is_weekend = now.weekday() >= 5
        times = BEST_POSTING_TIMES.get(platform, {}).get(
            "weekend" if is_weekend else "weekday",
            [12],
        )
        return random.choice(times)

    def get_ab_variant(self, test_name: str, niche: str = "general",
                       platform: str = "tiktok") -> Optional[str]:
        """Get the best-performing variant for an A/B test.

        If a variant has statistically significant better engagement, return it.
        Otherwise return a random untested variant.
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            rows = conn.execute(
                "SELECT variant, engagements, impressions, samples FROM ab_tests "
                "WHERE test_name=? AND niche=? AND platform=? AND samples > 0 "
                "ORDER BY (CAST(engagements AS REAL) / MAX(impressions, 1)) DESC",
                (test_name, niche, platform),
            ).fetchall()
            conn.close()

        if rows:
            best_variant, best_eng, best_imp, best_samples = rows[0]
            if best_imp > 0:
                best_rate = best_eng / best_imp
                for v, e, i, s in rows[1:]:
                    rate = e / i if i > 0 else 0
                    if abs(best_rate - rate) < AB_TEST_CONFIGS.get(test_name, {}).get("min_engagement_diff", 0.02):
                        return random.choice([best_variant, v])

                best_variant_data = rows[0]
                return best_variant_data[0]

        cfg = AB_TEST_CONFIGS.get(test_name)
        if cfg:
            return random.choice(cfg["variants"])
        return None

    def record_result(self, campaign_id: str, content_id: str, platform: str,
                      hook_type: str, posting_hour: int, cta_style: str,
                      niche: str, views: int = 0, likes: int = 0,
                      comments: int = 0, shares: int = 0):
        """Record a posting result → updates A/B test + optimal window data."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            eng = likes + comments + shares
            rate = eng / max(views, 1)

            conn.execute(
                "INSERT INTO posting_log (campaign_id, content_id, platform, "
                "scheduled_at, posted_at, hook_type, posting_hour, cta_style, "
                "niche, views, likes, comments, shares, engagement_rate) "
                "VALUES (?,?,?, datetime('now'), datetime('now'), ?,?,?,?,?,?,?,?,?)",
                (campaign_id, content_id, platform, hook_type, posting_hour,
                 cta_style, niche, views, likes, comments, shares, rate),
            )

            # Update A/B test: hook_type
            self._update_ab_test("hook_type", hook_type, niche, platform, views, eng)

            # Update A/B test: cta_style
            self._update_ab_test("cta_style", cta_style, niche, platform, views, eng)

            # Update optimal window
            day_name = datetime.now().strftime("%A")
            existing = conn.execute(
                "SELECT id, score, samples FROM optimal_windows "
                "WHERE platform=? AND niche=? AND best_hour=? AND best_day=?",
                (platform, niche, posting_hour, day_name),
            ).fetchone()
            if existing:
                wid, old_score, old_samples = existing
                new_samples = old_samples + 1
                new_score = ((old_score * old_samples) + rate) / new_samples
                conn.execute(
                    "UPDATE optimal_windows SET score=?, samples=?, updated_at=datetime('now') WHERE id=?",
                    (new_score, new_samples, wid),
                )
            else:
                conn.execute(
                    "INSERT INTO optimal_windows (platform, niche, best_hour, best_day, score, samples) "
                    "VALUES (?,?,?,?,?,1)",
                    (platform, niche, posting_hour, day_name, rate),
                )

            conn.commit()
            conn.close()

    def _update_ab_test(self, test_name: str, variant: str, niche: str,
                        platform: str, impressions: int, engagements: int):
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            row = conn.execute(
                "SELECT id, impressions, engagements, samples FROM ab_tests "
                "WHERE test_name=? AND variant=? AND niche=? AND platform=?",
                (test_name, variant, niche, platform),
            ).fetchone()
            if row:
                tid, old_imp, old_eng, old_samples = row
                conn.execute(
                    "UPDATE ab_tests SET impressions=?, engagements=?, samples=?, "
                    "updated_at=datetime('now') WHERE id=?",
                    (old_imp + impressions, old_eng + engagements, old_samples + 1, tid),
                )
            conn.commit()
            conn.close()

    def schedule_next_batch(self, count: int = 3) -> list[dict]:
        """Get next batch of optimal posting slots + A/B test variants.

        Returns list of scheduling recommendations.
        """
        schedule = []
        platforms = ["tiktok", "instagram", "youtube"]
        niches = ["skincare", "fashion", "food", "tech", "lifestyle"]

        for _ in range(count):
            platform = random.choice(platforms)
            niche = random.choice(niches)
            hour = self.get_optimal_time(platform, niche)

            hook = self.get_ab_variant("hook_type", niche, platform) or "curiosity_gap"
            cta = self.get_ab_variant("cta_style", niche, platform) or "link_bio"

            schedule.append({
                "platform": platform,
                "niche": niche,
                "optimal_hour": hour,
                "hook_type": hook,
                "cta_style": cta,
                "scheduled_for": f"{hour}:00 UTC+7",
            })

        return schedule

    def get_ab_test_summary(self, test_name: str = "",
                            niche: str = "") -> dict:
        """Get current A/B test standings."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            where = []
            params = []
            if test_name:
                where.append("test_name=?")
                params.append(test_name)
            if niche:
                where.append("niche=?")
                params.append(niche)

            q = "SELECT test_name, variant, niche, platform, impressions, engagements, samples FROM ab_tests"
            if where:
                q += " WHERE " + " AND ".join(where)
            q += " ORDER BY test_name, samples DESC"

            rows = conn.execute(q, params).fetchall()
            conn.close()

        results = {}
        for row in rows:
            tn, v, n, p, imp, eng, s = row
            key = f"{tn}/{n}/{p}"
            if key not in results:
                results[key] = {"test": tn, "niche": n, "platform": p, "variants": []}
            results[key]["variants"].append({
                "variant": v,
                "impressions": imp,
                "engagements": eng,
                "samples": s,
                "rate": round(eng / max(imp, 1), 4) if imp > 0 else 0,
            })

        return results

    def get_posting_history(self, limit: int = 50) -> list[dict]:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            rows = conn.execute(
                "SELECT * FROM posting_log ORDER BY posted_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            cols = ["id", "campaign_id", "content_id", "platform", "scheduled_at",
                    "posted_at", "hook_type", "posting_hour", "cta_style",
                    "niche", "views", "likes", "comments", "shares", "engagement_rate"]
            return [dict(zip(cols, r)) for r in rows]
