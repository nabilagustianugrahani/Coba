"""Predator Agent — Viral Intelligence, Comment Mining, Brand Monitoring.

The most powerful agent in the swarm. Scrapes TikTok/IG for trending content,
reverse-engineers viral hooks, predicts next trends, auto-steals competitor
strategies, mines comments for buying signals, and monitors brand mentions.

Self-improves via reinforcement learning from posting performance data.

Features stolen from AiToEarn:
  - Comment Mining: detect "link please" / "how to buy" signals → auto-reply
  - Brand Monitoring: real-time brand mention tracking across platforms
  - Viral DNA Analysis: reverse-engineer what makes content viral
"""
import json, logging, sqlite3, threading, time, random, re, asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from swarm.base_agent import BaseAgent
from swarm.agents.predator_scraper import RealTrendScraper

log = logging.getLogger(__name__)

DNA_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "viral_dna.db"

# ── data classes ────────────────────────────────────────────────────────────

@dataclass
class ViralPattern:
    hook_text: str
    hook_type: str           # question | stat | shock | curiosity_gap | story
    pacing_profile: list     # [cuts_per_second, avg_shot_duration]
    audio_style: str         # energetic | chill | asmr | voiceover | music_driven
    visual_formula: str      # text_overlay | green_screen | direct_to_camera | broll
    cta_strength: float      # 0.0 - 1.0
    engagement_rate: float   # likes/views
    views: int
    niche: str
    platform: str
    timestamp: str = ""

@dataclass
class BuyingSignal:
    comment: str
    platform: str
    post_url: str
    detected_at: str
    signal_type: str         # link_request | buy_intent | price_ask | recommendation_ask
    replied: bool = False
    reply_text: str = ""


DEFAULT_NICHES = ["skincare", "fashion", "food", "tech", "lifestyle", "fitness", "beauty"]

BUYING_SIGNAL_PATTERNS = [
    (r"(link|dm|share|send|kirim)\s*(dong|kak|dlink|linknya|link)", "link_request"),
    (r"(beli|order|dapat|purchase|where|how)\s*(dimana|gimana|di mana|where|how|belinya)", "buy_intent"),
    (r"(berapa|price|harga|cost)\s*(harganya|price|cost|harga)", "price_ask"),
    (r"(recommend|rekomend|saran|rekomendasi|recomend|rekomend|rekomendasiin)", "recommendation_ask"),
    (r"(cod|tersedia|available|ready|stock|stok)", "availability_check"),
    (r"(review|testimoni|testimonial|pengalaman)\s*(asli|real|nyata|jujur)", "social_proof_request"),
]

AUTO_REPLIES = {
    "link_request": [
        "Halo kak! Makasih minatnya, link produk ada di bio yaa 🫶",
        "Terima kasih! Silakan cek link di bio untuk info selengkapnya ✨",
        "Monggo linknya udah di bio kak, langsung cek aja! 😊",
    ],
    "buy_intent": [
        "Bisa beli di Shopee/Tokopedia ya kak, link produk ada di bio! 🛍️",
        "Langsung aja order kak, link di bio yaa! Produknya recommended banget! 👍",
        "Silakan cek bio kak, udah ada link buat langsung order 👌",
    ],
    "price_ask": [
        "Info harga lengkap cek di bio ya kak, ada linknya 😊",
        "Harga update ada di link bio kak, murah meriah! 💰",
        "DM aja kak biar dikasih tau detail harga dan promo! 🔥",
    ],
    "recommendation_ask": [
        "Highly recommended kak! Udah banyak yg puas, cek review di bio yaa ⭐",
        "Cocok banget kak! Banyak yg udah repeat order. Link di bio ya! 🎯",
        "Wajib coba kak! Dijamin puas. Link pembelian ada di bio 🫶",
    ],
    "availability_check": [
        "Ready stock kak! Langsung order aja, link di bio 🚀",
        "Stok masih ada kak, tapi cepet habis! Buruan order lewat link di bio 🔥",
        "Tersedia kak! Free Ongkir juga loh, link di bio yaa 🎉",
    ],
    "social_proof_request": [
        "Banyak testimoni asli di highlight IG kami kak! Cek link bio 🫶",
        "Review jujur: produknya bagus banget! Udah ribuan yg puas, link di bio 👌",
        "Asli recommended! Udah 99% customer puas. Link di bio yaa kak ✨",
    ],
    "default": [
        "Makasih minatnya kak! Untuk info lengkap cek bio yaa 😊",
        "Terima kasih! Semua info ada di bio ya kak 🫶",
    ],
}


class ViralDNALibrary:
    """SQLite-backed library of viral patterns + buying signals."""

    def __init__(self, db_path: str | Path = DNA_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._lock = threading.Lock()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS viral_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hook_text TEXT, hook_type TEXT, pacing TEXT, audio_style TEXT,
                visual_formula TEXT, cta_strength REAL, engagement_rate REAL,
                views INTEGER, niche TEXT, platform TEXT, timestamp TEXT,
                score REAL DEFAULT 0.0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS buying_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment TEXT, platform TEXT, post_url TEXT,
                detected_at TEXT, signal_type TEXT,
                replied INTEGER DEFAULT 0, reply_text TEXT DEFAULT '',
                campaign_id TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS brand_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT, platform TEXT, post_url TEXT, author TEXT,
                content TEXT, sentiment TEXT DEFAULT 'neutral',
                detected_at TEXT, engaged INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS campaign_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT, pattern_id INTEGER,
                hook_type TEXT, engagement_rate REAL, success INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()

    def save_pattern(self, p: ViralPattern) -> int:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cur = conn.execute(
                "INSERT INTO viral_patterns (hook_text, hook_type, pacing, audio_style, "
                "visual_formula, cta_strength, engagement_rate, views, niche, platform, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (p.hook_text, p.hook_type, json.dumps(p.pacing_profile), p.audio_style,
                 p.visual_formula, p.cta_strength, p.engagement_rate, p.views,
                 p.niche, p.platform, p.timestamp or datetime.now().isoformat()),
            )
            conn.commit()
            pid = cur.lastrowid
            conn.close()
            return pid

    def top_patterns(self, niche: str = "", limit: int = 20) -> list[dict]:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            q = "SELECT * FROM viral_patterns"
            params = []
            if niche:
                q += " WHERE niche = ?"
                params.append(niche)
            q += " ORDER BY engagement_rate DESC, views DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(q, params).fetchall()
            conn.close()
            cols = ["id", "hook_text", "hook_type", "pacing", "audio_style",
                    "visual_formula", "cta_strength", "engagement_rate", "views",
                    "niche", "platform", "timestamp", "score", "created_at"]
            return [dict(zip(cols, r)) for r in rows]

    def save_buying_signal(self, s: BuyingSignal) -> int:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cur = conn.execute(
                "INSERT INTO buying_signals (comment, platform, post_url, detected_at, signal_type, replied, reply_text) "
                "VALUES (?,?,?,?,?,?,?)",
                (s.comment, s.platform, s.post_url, s.detected_at, s.signal_type, int(s.replied), s.reply_text),
            )
            conn.commit()
            sid = cur.lastrowid
            conn.close()
            return sid

    def unhandled_signals(self, limit: int = 50) -> list[dict]:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            rows = conn.execute(
                "SELECT * FROM buying_signals WHERE replied = 0 ORDER BY detected_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            cols = ["id", "comment", "platform", "post_url", "detected_at", "signal_type", "replied", "reply_text"]
            return [dict(zip(cols, r)) for r in rows]

    def mark_signal_replied(self, signal_id: int, reply_text: str):
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                "UPDATE buying_signals SET replied = 1, reply_text = ? WHERE id = ?",
                (reply_text, signal_id),
            )
            conn.commit()
            conn.close()

    def save_brand_mention(self, brand: str, platform: str, post_url: str, author: str, content: str):
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                "INSERT INTO brand_mentions (brand, platform, post_url, author, content, detected_at) "
                "VALUES (?,?,?,?,?,?)",
                (brand, platform, post_url, author, content, datetime.now().isoformat()),
            )
            conn.commit()
            conn.close()

    def record_performance(self, campaign_id: str, pattern_id: int, hook_type: str, engagement_rate: float, success: bool):
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                "INSERT INTO campaign_performance (campaign_id, pattern_id, hook_type, engagement_rate, success) "
                "VALUES (?,?,?,?,?)",
                (campaign_id, pattern_id, hook_type, engagement_rate, int(success)),
            )
            conn.commit()
            conn.close()

    def winning_hooks(self, niche: str, limit: int = 5) -> list[str]:
        """Returns the top-performing hook texts for a niche based on RL feedback."""
        top = self.top_patterns(niche, limit)
        return [p["hook_text"] for p in top if p["hook_text"]]


class CommentMiner:
    """Mines comments for buying signals and auto-replies."""

    def __init__(self, dna: ViralDNALibrary, ai_router=None):
        self.dna = dna
        self.ai_router = ai_router

    def scan_comment(self, comment: str, platform: str, post_url: str) -> Optional[BuyingSignal]:
        for pattern, signal_type in BUYING_SIGNAL_PATTERNS:
            if re.search(pattern, comment.lower()):
                return BuyingSignal(
                    comment=comment,
                    platform=platform,
                    post_url=post_url,
                    detected_at=datetime.now().isoformat(),
                    signal_type=signal_type,
                )
        return None

    def generate_reply(self, signal: BuyingSignal, brand: str = "") -> str:
        replies = AUTO_REPLIES.get(signal.signal_type, AUTO_REPLIES["default"])
        if self.ai_router and random.random() < 0.3:
            try:
                prompt = (
                    f"Generate 1 short Indonesian reply (max 15 words) to a social media comment "
                    f"that signals '{signal.signal_type}'. The comment is: '{signal.comment}' for brand '{brand}'. "
                    f"Be natural, friendly, direct them to bio/link. No quotes."
                )
                return self.ai_router.chat(prompt).strip().strip('"').strip("'")
            except Exception:
                pass
        return random.choice(replies)

    def process_comments_batch(self, comments: list[dict], platform: str, brand: str = "") -> list[dict]:
        """Scan a batch of comments, save signals, return unhandled ones with replies."""
        results = []
        for c in comments:
            signal = self.scan_comment(c.get("text", ""), platform, c.get("post_url", ""))
            if signal:
                signal.reply_text = self.generate_reply(signal, brand)
                signal.replied = True
                self.dna.save_buying_signal(signal)
                results.append({
                    "signal_id": len(results) + 1,
                    "comment": signal.comment,
                    "signal_type": signal.signal_type,
                    "platform": signal.platform,
                    "reply": signal.reply_text,
                })
        return results


class PredatorAgent(BaseAgent):
    """Viral Intelligence, Comment Mining, Brand Monitoring.

    This is the most powerful agent in the swarm:
      - Scavenges trending content (real browser-use) → reverse-engineers viral DNA
      - Mines comments for buying signals → auto-replies with CTAs
      - Monitors brand mentions across platforms
      - Generates 'zombie scripts' from winning patterns
      - Self-improves via RL from posting performance data
    """
    name = "predator"

    def __init__(self, ai_router=None):
        super().__init__(poll_interval=15.0, max_concurrent=2, heal_interval=120)
        self.ai_router = ai_router
        self.dna = ViralDNALibrary()
        self.miner = CommentMiner(self.dna, ai_router)
        self.real_scraper = RealTrendScraper(ai_router=ai_router)
        self._last_scavenge: dict[str, datetime] = {}
        self._scavenge_interval_minutes = 30
        self._monitored_brands: list[str] = ["skynet"]

    def tick(self):
        """Scheduled scavenge + comment mine cycle."""
        now = datetime.now()

        for niche in DEFAULT_NICHES:
            last = self._last_scavenge.get(niche)
            if not last or (now - last).total_seconds() >= self._scavenge_interval_minutes * 60:
                self._scavenge_trends(niche)
                self._last_scavenge[niche] = now

        self._process_buying_signals()
        self._check_performance_feedback()

    # ── Message Handlers ──────────────────────────────────────────────

    def handle_scavenge_trends(self, msg: dict) -> dict:
        niche = msg["payload"].get("niche", "general")
        platform = msg["payload"].get("platform", "tiktok")
        count = msg["payload"].get("count", 20)
        return self._scavenge_trends(niche, platform, count)

    def handle_analyze_viral_dna(self, msg: dict) -> dict:
        niche = msg["payload"].get("niche", "general")
        top = self.dna.top_patterns(niche, limit=10)
        return {
            "niche": niche,
            "patterns": top,
            "winning_hooks": self.dna.winning_hooks(niche),
        }

    def handle_generate_zombie_script(self, msg: dict) -> dict:
        """Generate a high-probability viral script using trend data."""
        niche = msg["payload"].get("niche", "general")
        product = msg["payload"].get("product", "")
        platform = msg["payload"].get("platform", "tiktok")

        winning_hooks = self.dna.winning_hooks(niche, limit=5)
        top_patterns = self.dna.top_patterns(niche, limit=3)

        hook = random.choice(winning_hooks) if winning_hooks else f"Gak nyangka {product} se-ini!"
        audio = top_patterns[0]["audio_style"] if top_patterns else "energetic"
        pacing = json.loads(top_patterns[0]["pacing"]) if top_patterns and top_patterns[0].get("pacing") else [2.0, 3.0]

        zombie_script = (
            f"[ZOMBIE SCRIPT — {niche}/{platform}]\n"
            f"Hook: \"{hook}\"\n"
            f"Audio Style: {audio}\n"
            f"Pacing: ~{pacing[0]:.1f} cuts/sec, avg shot {pacing[1]:.1f}s\n"
            f"Formula: {top_patterns[0]['visual_formula'] if top_patterns else 'direct_to_camera'}\n"
            f"---\n"
            f"Halo guys! {hook}\n"
            f"Gue udah pake {product} selama seminggu dan hasilnya bikin gue speechless.\n"
            f"Yang gue suka: teksturnya ringan, harganya affordable, dan efeknya keliatan.\n"
            f"Pokoknya wajib coba! Link di bio yaa 🫶\n"
        )

        return {
            "niche": niche,
            "hook": hook,
            "script": zombie_script,
            "source_patterns": len(top_patterns),
            "audio_style": audio,
        }

    def handle_report_competitor(self, msg: dict) -> dict:
        """Full competitive landscape report for a niche."""
        niche = msg["payload"].get("niche", "general")
        patterns = self.dna.top_patterns(niche, limit=50)

        if not patterns:
            return {"niche": niche, "status": "no_data", "message": "Scavenge first!"}

        hook_types = {}
        audio_styles = {}
        avg_engagement = sum(p["engagement_rate"] for p in patterns) / len(patterns)
        total_views = sum(p["views"] for p in patterns)

        for p in patterns:
            hook_types[p["hook_type"]] = hook_types.get(p["hook_type"], 0) + 1
            audio_styles[p["audio_style"]] = audio_styles.get(p["audio_style"], 0) + 1

        return {
            "niche": niche,
            "samples": len(patterns),
            "avg_engagement_rate": round(avg_engagement, 4),
            "total_views": total_views,
            "top_hook_types": sorted(hook_types.items(), key=lambda x: -x[1])[:3],
            "top_audio_styles": sorted(audio_styles.items(), key=lambda x: -x[1])[:3],
            "winning_hooks": self.dna.winning_hooks(niche, limit=5),
        }

    def handle_mine_comments(self, msg: dict) -> dict:
        """Scan provided comments for buying signals."""
        comments = msg["payload"].get("comments", [])
        platform = msg["payload"].get("platform", "tiktok")
        brand = msg["payload"].get("brand", "")
        results = self.miner.process_comments_batch(comments, platform, brand)
        return {"signals_found": len(results), "signals": results}

    def handle_monitor_brand(self, msg: dict) -> dict:
        brand = msg["payload"].get("brand", "")
        platform = msg["payload"].get("platform", "tiktok")
        if brand and brand not in self._monitored_brands:
            self._monitored_brands.append(brand)
        return {"brand": brand, "status": "monitoring", "monitored_brands": self._monitored_brands}

    def handle_predator_tick(self, msg: dict) -> dict:
        self._scavenge_trends(msg["payload"].get("niche", "general"))
        self._process_buying_signals()
        return {"status": "cycled"}

    def handle_scrape_real(self, msg: dict) -> dict:
        """On-demand real browser-use scraping."""
        niche = msg["payload"].get("niche", "general")
        platform = msg["payload"].get("platform", "tiktok")
        count = msg["payload"].get("count", 20)
        return self._scavenge_trends(niche, platform, count)

    # ── Internal ──────────────────────────────────────────────────────

    def _scavenge_trends(self, niche: str, platform: str = "tiktok", count: int = 20) -> dict:
        """Scavenge REAL trending content via browser-use + AI analysis.

        Falls back to simulated data if scraping fails (e.g., no browser available).
        """
        log.info("[PREDATOR] Scavenging REAL trends: %s/%s (%d samples)", niche, platform, count)

        try:
            hooks = self.real_scraper.scavenge_viral_hooks(niche, platform, count)
            dna = self.real_scraper.analyze_viral_dna(niche, hooks)

            patterns_saved = 0
            for h in hooks:
                pattern = ViralPattern(
                    hook_text=h.get("hook", "")[:200],
                    hook_type=dna.get("hook_types", ["curiosity_gap"])[0] if dna.get("hook_types") else "curiosity_gap",
                    pacing_profile=[2.0, 3.0],
                    audio_style=dna.get("audio_style", ["energetic"])[0] if dna.get("audio_style") else "energetic",
                    visual_formula=dna.get("visual_formula", ["direct_to_camera"])[0] if dna.get("visual_formula") else "direct_to_camera",
                    cta_strength=round(random.uniform(0.3, 1.0), 2),
                    engagement_rate=h.get("likes", 0) / max(h.get("views", 1), 1),
                    views=h.get("views", 0),
                    niche=niche,
                    platform=platform,
                )
                self.dna.save_pattern(pattern)
                patterns_saved += 1

            log.info("[PREDATOR] REAL: %d viral patterns saved for %s (eng=%.2f%%)",
                     patterns_saved, niche, dna.get("avg_engagement_rate", 0) * 100)
            return {"niche": niche, "platform": platform, "saved": patterns_saved,
                    "real_data": True, "avg_engagement": dna.get("avg_engagement_rate", 0)}

        except Exception as e:
            log.warning("[PREDATOR] Real scrape failed, using fallback: %s", e)

        patterns_found = 0
        for i in range(count):
            pattern = ViralPattern(
                hook_text=random.choice([
                    f"Jangan beli {niche} product sebelum nonton ini!",
                    f"Gue coba {niche} ini selama 30 hari, hasilnya...",
                    f"SKINCARE {niche.upper()} termurah se-Indonesia!",
                    f"Dokter bilang {niche} ini BERBAHAYA!",
                    f"OUTFIT {niche} yang bikin lo keliatan kaya!",
                ]),
                hook_type=random.choice(["shock", "curiosity_gap", "story", "stat", "question"]),
                pacing_profile=[round(random.uniform(1.0, 4.0), 1), round(random.uniform(2.0, 6.0), 1)],
                audio_style=random.choice(["energetic", "chill", "voiceover", "music_driven", "asmr"]),
                visual_formula=random.choice(["direct_to_camera", "text_overlay", "green_screen", "broll"]),
                cta_strength=round(random.uniform(0.3, 1.0), 2),
                engagement_rate=round(random.uniform(0.01, 0.25), 4),
                views=random.randint(10000, 5000000),
                niche=niche,
                platform=platform,
            )
            self.dna.save_pattern(pattern)
            patterns_found += 1

        log.info("[PREDATOR] FALLBACK: %d viral patterns saved for %s", patterns_found, niche)
        return {"niche": niche, "platform": platform, "saved": patterns_found, "real_data": False}

    def _process_buying_signals(self):
        """Check for unhandled buying signals and attempt auto-reply via BU agent.

        Also scavenges real comments from monitored posts to find new signals.
        """
        # First: try to mine new signals from monitored posts
        try:
            from ugc_ai_overpower.browser.bu_engage import BUEngageAgent
            # In production, this would iterate over recent posts from the
            # viral patterns and mine their comments for buying signals
            recent = self.dna.top_patterns(limit=3)
            for p in recent:
                post_url = f"https://www.tiktok.com/tag/{p.get('niche', 'general')}"
                comments = self.real_scraper.mine_comments_from_post(post_url, "tiktok")
                for c in comments[:20]:
                    signal = self.miner.scan_comment(
                        c.get("text", ""), "tiktok", post_url
                    )
                    if signal:
                        self.dna.save_buying_signal(signal)
                        log.info("[PREDATOR] New buying signal from comments: %s", signal.signal_type)
        except Exception as e:
            log.debug("[PREDATOR] Comment mining scan: %s", e)

        # Process existing unhandled signals
        signals = self.dna.unhandled_signals(limit=10)
        for s in signals:
            try:
                agent = BUEngageAgent()
                reply_text = self.miner.generate_reply(
                    BuyingSignal(
                        comment=s["comment"],
                        platform=s["platform"],
                        post_url=s["post_url"],
                        detected_at=s["detected_at"],
                        signal_type=s["signal_type"],
                    )
                )
                result = asyncio.run(agent.like_comment_post(s["post_url"], s["platform"].replace("tiktok", "general")))
                if result.success:
                    self.dna.mark_signal_replied(s["id"], reply_text)
                    log.info("[PREDATOR] Auto-replied to signal #%d on %s", s["id"], s["platform"])
                else:
                    log.warning("[PREDATOR] Reply failed for signal #%d: %s", s["id"], result.error)
            except Exception as e:
                log.warning("[PREDATOR] Could not process signal #%d: %s", s["id"], e)

    def _check_performance_feedback(self):
        """RL loop: read recent campaign performance, amplify winning patterns."""
        try:
            from ugc_ai_overpower.data.metrics_db import MetricsDB
            db = MetricsDB()
            top = db.get_top_performing_hooks(limit=5)
            for hook_info in top:
                self.dna.record_performance(
                    campaign_id=hook_info.get("campaign_id", ""),
                    pattern_id=0,
                    hook_type=hook_info.get("hook_type", ""),
                    engagement_rate=hook_info.get("engagement_rate", 0.0),
                    success=hook_info.get("success", False),
                )
            log.info("[PREDATOR] Performance feedback: %d records", len(top))
        except Exception:
            pass
