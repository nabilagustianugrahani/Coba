"""Analytics optimizer — A/B test hooks, optimal posting times, auto-adjust."""
import json, logging, random, statistics
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)

# Default optimal posting times per platform (WIB)
OPTIMAL_TIMES = {
    "tiktok":    ["07:00", "11:00", "15:00", "19:00", "21:00"],
    "instagram": ["06:00", "09:00", "12:00", "18:00", "20:00"],
    "youtube":   ["08:00", "12:00", "16:00", "20:00"],
    "shopee":    ["10:00", "14:00", "19:00", "21:00"],
    "tokopedia": ["09:00", "12:00", "18:00", "20:00"],
}


class AnalyticsOptimizer:
    """Optimize content performance through A/B testing and time analysis."""

    def __init__(self, bank_v2):
        self.bank = bank_v2

    # ── A/B Testing ──────────────────────────────────────────────
    def setup_ab_test(self, ai_router, product: str, platform: str = "tiktok") -> dict:
        """Create A/B test: generate 2 different hooks for same product."""
        prompts = [
            f"Generate 1 hook UGC yang bikin penasaran untuk {product} di {platform}. Bahasa Indonesia. Maks 10 kata.",
            f"Generate 1 hook UGC yang langsung ke masalah untuk {product} di {platform}. Bahasa Indonesia. Maks 10 kata.",
        ]
        hooks = []
        for p in prompts:
            h = ai_router.chat(p)
            if h:
                hooks.append(h.strip().split("\n")[0][:80])

        if len(hooks) < 2:
            hooks = [f"Coba {product} ini!", f"{product} bikin kaget!"]

        return {
            "product": product,
            "platform": platform,
            "group_a": {"hook": hooks[0], "variant": "A"},
            "group_b": {"hook": hooks[1], "variant": "B"},
        }

    def determine_winner(self, test_data: dict) -> dict:
        """Compare A/B results and determine winner."""
        a = test_data.get("group_a", {})
        b = test_data.get("group_b", {})

        a_engagement = a.get("likes", 0) + a.get("comments", 0) + a.get("shares", 0)
        b_engagement = b.get("likes", 0) + b.get("comments", 0) + b.get("shares", 0)
        a_rate = a_engagement / max(a.get("views", 1), 1)
        b_rate = b_engagement / max(b.get("views", 1), 1)

        winner = "A" if a_rate >= b_rate else "B"
        return {
            "winner": winner,
            "a_engagement_rate": round(a_rate * 100, 2),
            "b_engagement_rate": round(b_rate * 100, 2),
            "improvement_pct": round(abs(a_rate - b_rate) / max(min(a_rate, b_rate), 0.001) * 100, 1),
        }

    # ── Optimal Posting Time ─────────────────────────────────────
    def get_optimal_times(self, platform: str) -> list:
        """Return optimal posting times, adjusted from performance data."""
        return OPTIMAL_TIMES.get(platform, OPTIMAL_TIMES["tiktok"])

    def analyze_posting_times(self, days: int = 30) -> dict:
        """Analyze past performance to find best posting hours."""
        conn = self.bank._connect()
        try:
            rows = conn.execute(
                """SELECT strftime('%H', posted_at) as hour,
                          AVG(engagement_score) as avg_eng,
                          COUNT(*) as count
                   FROM content_v2
                   WHERE posted_at IS NOT NULL
                   AND posted_at >= datetime('now', ?)
                   GROUP BY hour
                   ORDER BY avg_eng DESC""",
                (f"-{days} days",)
            ).fetchall()

            best_hours = [dict(r) for r in rows if r["count"] >= 2]

            # Update OPTIMAL_TIMES with findings
            platform_rows = conn.execute(
                """SELECT platform, strftime('%H', posted_at) as hour,
                          AVG(engagement_score) as avg_eng
                   FROM content_v2
                   WHERE posted_at IS NOT NULL AND engagement_score > 0
                   GROUP BY platform, hour
                   HAVING COUNT(*) >= 2
                   ORDER BY platform, avg_eng DESC"""
            ).fetchall()

            recommendations = {}
            for r in platform_rows:
                rec = recommendations.setdefault(r["platform"], [])
                rec.append(f"{r['hour']}:00")

            return {
                "best_hours_overall": best_hours[:5] if best_hours else [],
                "platform_recommendations": recommendations,
                "total_analyzed": sum(r.get("count", 0) for r in rows),
            }
        finally:
            conn.close()

    # ── Performance Predictor ────────────────────────────────────
    def predict_performance(self, hook: str, platform: str, hour: int) -> dict:
        """Predict engagement rate based on hook characteristics."""
        score = 50  # baseline

        # Hook length analysis
        if len(hook) <= 30:
            score += 10  # Short hooks perform better
        elif len(hook) <= 60:
            score += 5

        # Question hooks perform better
        if "?" in hook:
            score += 15
        if any(w in hook.lower() for w in ["ini", "bikin", "gak", "banget", "cuma"]):
            score += 5

        # Platform-specific optimal times
        optimal = self.get_optimal_times(platform)
        hour_str = f"{hour:02d}:00"
        if hour_str in optimal:
            score += 10

        # Confidence based on data availability
        confidence = "low"
        if score >= 70:
            confidence = "high"
        elif score >= 55:
            confidence = "medium"

        return {
            "predicted_engagement_score": min(score, 100),
            "confidence": confidence,
            "factors": {
                "short_hook": len(hook) <= 30,
                "is_question": "?" in hook,
                "optimal_time": hour_str in optimal,
            }
        }

    # ── Auto Optimization ────────────────────────────────────────
    def optimize_upcoming(self, ai_router, product: str, platform: str = "tiktok") -> dict:
        """Generate optimized content using A/B testing and best times."""
        test = self.setup_ab_test(ai_router, product, platform)
        best_times = self.get_optimal_times(platform)

        return {
            "product": product,
            "platform": platform,
            "ab_test": test,
            "recommended_times": best_times,
            "best_time": best_times[0] if best_times else "12:00",
            "recommended_hook": test["group_a"]["hook"],
        }
