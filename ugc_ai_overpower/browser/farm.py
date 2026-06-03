"""Multi-account farm — rotate multiple accounts, detect bans, manage sessions."""
import os, json, time, random, logging, threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)
FARM_DIR = Path(__file__).resolve().parents[1] / "data" / "farm"

class AccountProfile:
    def __init__(self, name: str, platform: str, cookies: dict = None):
        self.name = name
        self.platform = platform
        self.cookies = cookies or {}
        self.health = 100          # 0 = banned/dead
        self.post_count = 0
        self.daily_post_count = 0
        self.last_post_time = None
        self.daily_reset = datetime.now().date()
        self.cooldown_until = None
        self.banned = False
        self.notes = ""

    def can_post(self) -> tuple[bool, str]:
        if self.banned:
            return False, "banned"
        if self.health < 20:
            return False, "health too low"
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False, f"cooldown until {self.cooldown_until}"
        # Daily limit check (per platform default)
        limits = {"tiktok": 10, "instagram": 15, "youtube": 20, "shopee": 30, "tokopedia": 30}
        if self.daily_post_count >= limits.get(self.platform, 10):
            return False, "daily limit reached"
        # Reset daily counter if new day
        if self.daily_reset != datetime.now().date():
            self.daily_post_count = 0
            self.daily_reset = datetime.now().date()
        return True, "ok"

    def record_post(self, success: bool):
        self.daily_post_count += 1
        self.post_count += 1
        self.last_post_time = datetime.now()
        if not success:
            self.health -= 10
        if success and self.health < 100:
            self.health = min(100, self.health + 2)

    def mark_banned(self):
        self.banned = True
        self.health = 0

    def cooldown(self, minutes: int = 30):
        self.cooldown_until = datetime.now() + timedelta(minutes=minutes)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "platform": self.platform,
            "health": self.health, "post_count": self.post_count,
            "daily_post_count": self.daily_post_count,
            "last_post_time": str(self.last_post_time) if self.last_post_time else None,
            "daily_reset": str(self.daily_reset),
            "cooldown_until": str(self.cooldown_until) if self.cooldown_until else None,
            "banned": self.banned, "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict):
        p = cls(data["name"], data["platform"])
        p.health = data.get("health", 100)
        p.post_count = data.get("post_count", 0)
        p.daily_post_count = data.get("daily_post_count", 0)
        p.last_post_time = datetime.fromisoformat(data["last_post_time"]) if data.get("last_post_time") else None
        p.daily_reset = datetime.fromisoformat(data["daily_reset"]).date() if data.get("daily_reset") else datetime.now().date()
        p.cooldown_until = datetime.fromisoformat(data["cooldown_until"]) if data.get("cooldown_until") else None
        p.banned = data.get("banned", False)
        p.notes = data.get("notes", "")
        return p


class AccountFarm:
    def __init__(self):
        self._lock = threading.RLock()
        self._profiles: dict[str, dict[str, AccountProfile]] = {}  # {platform: {name: profile}}
        self._load_all()

    def _path(self, platform: str) -> Path:
        p = FARM_DIR / platform
        p.mkdir(parents=True, exist_ok=True)
        return p / "profiles.json"

    def _load_all(self):
        for plat_dir in FARM_DIR.iterdir():
            if plat_dir.is_dir():
                f = plat_dir / "profiles.json"
                if f.exists():
                    try:
                        data = json.loads(f.read_text())
                        plat = plat_dir.name
                        self._profiles[plat] = {}
                        for name, pd in data.items():
                            self._profiles[plat][name] = AccountProfile.from_dict(pd)
                        log.info("Loaded %d %s profiles", len(data), plat)
                    except Exception as e:
                        log.warning("Failed loading %s profiles: %s", plat_dir.name, e)

    def _save_platform(self, platform: str):
        p = self._path(platform)
        profiles = self._profiles.get(platform, {})
        data = {name: prof.to_dict() for name, prof in profiles.items()}
        p.write_text(json.dumps(data, indent=2))

    # ── Public API ───────────────────────────────────────────────
    def register(self, platform: str, name: str, cookies: dict = None) -> AccountProfile:
        with self._lock:
            self._profiles.setdefault(platform, {})
            if name in self._profiles[platform]:
                raise ValueError(f"Profile '{name}' already exists for {platform}")
            prof = AccountProfile(name, platform, cookies)
            self._profiles[platform][name] = prof
            self._save_platform(platform)
            log.info("Registered %s profile: %s", platform, name)
            # Also save cookies
            if cookies:
                self._save_cookies(platform, name, cookies)
            return prof

    def get_profile(self, platform: str, name: str) -> Optional[AccountProfile]:
        return self._profiles.get(platform, {}).get(name)

    def get_available(self, platform: str) -> list[AccountProfile]:
        """Get profiles that can post right now, sorted by health."""
        with self._lock:
            profiles = self._profiles.get(platform, {}).values()
            available = [p for p in profiles if p.can_post()[0]]
            available.sort(key=lambda p: (-p.health, p.daily_post_count))
            return available

    def rotate(self, platform: str) -> Optional[AccountProfile]:
        """Get the best available account, with randomization."""
        available = self.get_available(platform)
        if not available:
            log.warning("No available profiles for %s", platform)
            return None
        # Random top 3
        candidates = available[:min(3, len(available))]
        chosen = random.choice(candidates)
        log.info("Rotated to %s profile: %s (health=%d, posted=%d)",
                 platform, chosen.name, chosen.health, chosen.daily_post_count)
        return chosen

    def record_result(self, platform: str, name: str, success: bool):
        with self._lock:
            prof = self.get_profile(platform, name)
            if prof:
                prof.record_post(success)
                if not success:
                    prof.cooldown(random.randint(15, 60))
                self._save_platform(platform)

    def mark_banned(self, platform: str, name: str):
        with self._lock:
            prof = self.get_profile(platform, name)
            if prof:
                prof.mark_banned()
                self._save_platform(platform)
                log.warning("Marked %s/%s as BANNED", platform, name)

    def get_all(self, platform: str = "") -> list[dict]:
        with self._lock:
            results = []
            for plat, profiles in self._profiles.items():
                if platform and plat != platform:
                    continue
                for name, prof in profiles.items():
                    d = prof.to_dict()
                    d["platform"] = plat
                    d["name"] = name
                    results.append(d)
            return results

    def get_stats(self) -> dict:
        with self._lock:
            total = 0
            healthy = 0
            banned = 0
            for plat, profiles in self._profiles.items():
                for prof in profiles.values():
                    total += 1
                    if prof.banned:
                        banned += 1
                    elif prof.health > 50:
                        healthy += 1
            return {
                "total_profiles": total,
                "healthy": healthy,
                "banned": banned,
                "dead": total - healthy - banned,
                "platforms": list(self._profiles.keys()),
            }

    # ── Cookie management ────────────────────────────────────────
    def _cookies_path(self, platform: str, name: str) -> Path:
        p = FARM_DIR / platform / name
        p.mkdir(parents=True, exist_ok=True)
        return p / "cookies.json"

    def _save_cookies(self, platform: str, name: str, cookies: dict):
        p = self._cookies_path(platform, name)
        p.write_text(json.dumps(cookies, indent=2))

    def load_cookies(self, platform: str, name: str) -> Optional[dict]:
        p = self._cookies_path(platform, name)
        if p.exists():
            return json.loads(p.read_text())
        return None

    def delete(self, platform: str, name: str):
        with self._lock:
            self._profiles.get(platform, {}).pop(name, None)
            p = self._cookies_path(platform, name)
            if p.exists():
                p.unlink()
            self._save_platform(platform)
