"""Character Agent — niche-based consistent persona system.

A UGC persona must be CONSISTENT across content (no shifting voice/values)
but ADAPT to the niche (beauty influencer != tech reviewer).

For each niche, this agent:
  1. Defines a stable persona (name, age, tone, values, vocabulary)
  2. Adapts surface details (fashion, references, slang) to the niche
  3. Generates on-brand content via the persona
  4. Locks the persona once — never drifts mid-campaign

Concept: 3 layers
  - L0  Identity:   name, age, gender, location, background (LOCKED)
  - L1  Personality: tone, values, humor, formality (LOCKED per persona)
  - L2  Niche adaptation: vocabulary, references, visual style (per niche)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional

log = logging.getLogger(__name__)


DEFAULT_DB_PATH = Path.home() / ".9router" / "characters.db"


class ContentTone(str, Enum):
    CASUAL = "casual"
    PROFESSIONAL = "professional"
    WITTY = "witty"
    EDUCATIONAL = "educational"
    ASPIRATIONAL = "aspirational"
    AUTHENTIC = "authentic"
    SARCASTIC = "sarcastic"
    WARM = "warm"
    ENERGETIC = "energetic"
    CALM = "calm"


class ContentLanguage(str, Enum):
    ID = "id"
    EN = "en"
    MIXED = "mixed"


@dataclass
class PersonaIdentity:
    name: str
    age: int
    gender: str
    location: str
    background: str
    languages: list[str] = field(default_factory=lambda: ["id"])

    def fingerprint(self) -> str:
        data = f"{self.name}|{self.age}|{self.gender}|{self.location}|{self.background}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


@dataclass
class PersonalityTraits:
    tone: str = ContentTone.AUTHENTIC.value
    formality: float = 0.5
    humor: float = 0.5
    energy: float = 0.5
    warmth: float = 0.7
    confidence: float = 0.6
    curiosity: float = 0.7
    values: list[str] = field(default_factory=list)
    personality_tags: list[str] = field(default_factory=list)


@dataclass
class NicheAdaptation:
    niche: str
    vocabulary: list[str] = field(default_factory=list)
    forbidden_words: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    visual_style: str = ""
    cta_patterns: list[str] = field(default_factory=list)
    emoji_set: list[str] = field(default_factory=list)
    hook_patterns: list[str] = field(default_factory=list)


@dataclass
class Character:
    """A UGC persona locked to a niche.

    Once created, the identity + personality are FROZEN. Only the
    niche_adaptation can vary (and only when the niche changes).
    """
    character_id: str
    identity: PersonaIdentity
    personality: PersonalityTraits
    niche: str
    niche_adaptation: NicheAdaptation
    language: str = ContentLanguage.ID.value
    locked: bool = True
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def switch_niche(self, new_niche: str,
                     new_adaptation: NicheAdaptation) -> "Character":
        if not self.locked:
            raise ValueError("Character must be locked before niche switch")
        if new_niche == self.niche:
            log.debug("character.switch_niche same niche, no-op")
            return self
        base_id = self.character_id.rsplit("_", 1)[0] if "_" in self.character_id else self.identity.name.lower()
        new_char = Character(
            character_id=f"{base_id}_{new_niche}",
            identity=self.identity,
            personality=self.personality,
            niche=new_niche,
            niche_adaptation=new_adaptation,
            language=self.language,
        )
        log.info("character.switch_niche %s -> %s", self.niche, new_niche)
        return new_char

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Character":
        return cls(
            character_id=d["character_id"],
            identity=PersonaIdentity(**d["identity"]),
            personality=PersonalityTraits(**d["personality"]),
            niche=d["niche"],
            niche_adaptation=NicheAdaptation(**d["niche_adaptation"]),
            language=d.get("language", ContentLanguage.ID.value),
            locked=d.get("locked", True),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )

    def fingerprint(self) -> str:
        id_fp = self.identity.fingerprint()
        pers_fp = hashlib.sha256(
            json.dumps(asdict(self.personality), sort_keys=True).encode()
        ).hexdigest()[:8]
        return f"{id_fp}-{pers_fp}"


NICHE_PRESETS: dict[str, NicheAdaptation] = {
    "beauty": NicheAdaptation(
        niche="beauty",
        vocabulary=["skincare", "makeup", "glow", "routine", "tutorial", "review",
                    "swatches", "pigmented", "blendable", "long-lasting"],
        forbidden_words=["cheap", "boring", "overrated"],
        references=["Sephora", "Sociolla", "MUA reviews", "TikTok beauty trends"],
        visual_style="Bright, well-lit close-ups, before/after, soft pinks/golds",
        cta_patterns=["Save this for your next haul", "DM me for the link",
                      "Comment your skin type below"],
        emoji_set=["✨", "💄", "🌸", "💅", "🪞", "💋"],
        hook_patterns=["POV: you just found your holy grail", "The girlies need to see this",
                       "I tried it so you don't have to"],
    ),
    "tech": NicheAdaptation(
        niche="tech",
        vocabulary=["specs", "benchmark", "review", "unboxing", "value", "performance",
                    "battery life", "camera", "display", "review"],
        forbidden_words=["meh", "it's fine", "whatever"],
        references=["MKBHD", "Linus Tech Tips", "Dave2D", "GSMArena"],
        visual_style="Clean desk setup, dark mode, side-by-side comparisons",
        cta_patterns=["Full review in bio", "Drop your questions below",
                      "Which one would you pick?"],
        emoji_set=["🔥", "⚡", "🚀", "📱", "💻", "🖥️"],
        hook_patterns=["I switched from iPhone for 30 days", "The hidden spec nobody talks about",
                       "This $500 phone beats the $1500 one"],
    ),
    "fashion": NicheAdaptation(
        niche="fashion",
        vocabulary=["outfit", "lookbook", "styling", "capsule", "essentials",
                    "thrifted", "OOTD", "fit", "vibe"],
        forbidden_words=["basic", "trying too hard"],
        references=["Zara", "H&M", "local thrift stores", "Pinterest fits"],
        visual_style="Mirror selfies, OOTD grids, color-coordinated backgrounds",
        cta_patterns=["Outfit details in comments", "Tag a friend who needs this",
                      "Would you wear this?"],
        emoji_set=["👗", "👠", "👜", "🕶️", "💃", "✨"],
        hook_patterns=["3 ways to style one piece", "My honest review of the viral outfit",
                       "Get ready with me for less"],
    ),
    "food": NicheAdaptation(
        niche="food",
        vocabulary=["recipe", "taste test", "homemade", "umami", "crispy", "savory",
                    "review", "ingredients", "cooking"],
        forbidden_words=["gross", "inedible"],
        references=["MasterChef", "food vloggers", "local warungs"],
        visual_style="Close-up food shots, steam shots, color-popping plates",
        cta_patterns=["Recipe in comments", "Try this and tag me",
                      "Where should I eat next?"],
        emoji_set=["🍜", "🍔", "😋", "🔥", "👨‍🍳", "🥢"],
        hook_patterns=["I made viral TikTok pasta", "Trying the most aesthetic cafe in Jakarta",
                       "Budget meal under 20K"],
    ),
    "fitness": NicheAdaptation(
        niche="fitness",
        vocabulary=["workout", "routine", "PR", "form", "reps", "sets",
                    "recovery", "gains", "cardio", "strength"],
        forbidden_words=["lazy", "skip leg day"],
        references=["Athlean-X", "Jeff Nippard", "local gyms"],
        visual_style="Gym mirror shots, sweat details, before/after progress",
        cta_patterns=["Save this workout", "Tag your gym buddy",
                      "Drop your PR in comments"],
        emoji_set=["💪", "🏋️", "🔥", "⚡", "🏃", "🥵"],
        hook_patterns=["30-day transformation", "I tried the 5x5 program for 90 days",
                       "Stop making this gym mistake"],
    ),
    "finance": NicheAdaptation(
        niche="finance",
        vocabulary=["investing", "saving", "budget", "passive income", "diversified",
                    "yield", "portfolio", "review", "tips"],
        forbidden_words=["get rich quick", "guaranteed"],
        references=["Investopedia", "Bukalapak saham", "Bareksa"],
        visual_style="Charts, calculator, minimal desk setup",
        cta_patterns=["Full breakdown in carousel", "Save for later",
                      "What's your biggest financial goal?"],
        emoji_set=["💰", "📈", "🏦", "💳", "📊", "🪙"],
        hook_patterns=["How I saved my first 100 juta", "Stop doing this with your money",
                       "Side hustle that actually works"],
    ),
    "parenting": NicheAdaptation(
        niche="parenting",
        vocabulary=["mom life", "parenting hack", "toddler", "milestone",
                    "review", "tips", "honest", "real talk"],
        forbidden_words=["perfect parent", "I have it all figured out"],
        references=["local mom communities", "TikTok parenting"],
        visual_style="Candid family moments, soft tones, toys in background",
        cta_patterns=["Tag a new mom who needs this", "Comment your tip below",
                      "Save for nap time reading"],
        emoji_set=["👶", "🍼", "💕", "🏡", "👨‍👩‍👧", "🧸"],
        hook_patterns=["Things nobody tells new moms", "Honest review of the viral baby product",
                       "Surviving the first year"],
    ),
    "travel": NicheAdaptation(
        niche="travel",
        vocabulary=["itinerary", "hidden gem", "guide", "review", "tips",
                    "budget", "backpacking", "vlog"],
        forbidden_words=["tourist trap"],
        references=["TripAdvisor", "local travel groups", "TikTok travel"],
        visual_style="Drone shots, golden hour, scenic landscapes, food close-ups",
        cta_patterns=["Full itinerary in bio", "Save this for your next trip",
                      "Where should I go next?"],
        emoji_set=["✈️", "🏝️", "🗺️", "🏔️", "🌅", "🎒"],
        hook_patterns=["3 days in Bali for under 3 juta", "Hidden gem in Yogyakarta",
                       "I traveled Indonesia for 30 days"],
    ),
}


PERSONA_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Sari",
        "age": 27,
        "gender": "female",
        "location": "Jakarta",
        "background": "Working professional, beauty & lifestyle enthusiast",
        "personality": {
            "tone": "warm",
            "formality": 0.3,
            "humor": 0.6,
            "energy": 0.7,
            "warmth": 0.9,
            "confidence": 0.6,
            "curiosity": 0.7,
            "values": ["authenticity", "self-care", "community"],
            "personality_tags": ["relatable", "honest", "supportive"],
        },
    },
    {
        "name": "Rizky",
        "age": 30,
        "gender": "male",
        "location": "Bandung",
        "background": "Tech reviewer and gadget enthusiast",
        "personality": {
            "tone": "witty",
            "formality": 0.4,
            "humor": 0.8,
            "energy": 0.8,
            "warmth": 0.5,
            "confidence": 0.9,
            "curiosity": 0.9,
            "values": ["honesty", "depth", "evidence"],
            "personality_tags": ["analytical", "sarcastic", "knowledgeable"],
        },
    },
    {
        "name": "Mbak Ani",
        "age": 35,
        "gender": "female",
        "location": "Surabaya",
        "background": "Mom of two, home cook and frugal living advocate",
        "personality": {
            "tone": "warm",
            "formality": 0.2,
            "humor": 0.4,
            "energy": 0.5,
            "warmth": 0.95,
            "confidence": 0.7,
            "curiosity": 0.5,
            "values": ["family", "saving", "tradition"],
            "personality_tags": ["nurturing", "practical", "wise"],
        },
    },
    {
        "name": "Dimas",
        "age": 24,
        "gender": "male",
        "location": "Yogyakarta",
        "background": "Student and food vlogger exploring local warungs",
        "personality": {
            "tone": "energetic",
            "formality": 0.2,
            "humor": 0.7,
            "energy": 0.95,
            "warmth": 0.7,
            "confidence": 0.6,
            "curiosity": 0.95,
            "values": ["authenticity", "local culture", "affordability"],
            "personality_tags": ["enthusiastic", "curious", "down-to-earth"],
        },
    },
]


class CharacterStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        env_path = os.environ.get("UGC_CHARACTER_DB", "")
        self.path = path or (Path(env_path) if env_path else DEFAULT_DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS characters (
                    character_id TEXT PRIMARY KEY,
                    niche TEXT NOT NULL,
                    data TEXT NOT NULL,
                    locked INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    fingerprint TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_niche ON characters(niche)")
            conn.commit()

    def save(self, character: Character) -> None:
        with self._lock:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO characters
                    (character_id, niche, data, locked, created_at, updated_at, fingerprint)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        character.character_id, character.niche,
                        json.dumps(character.to_dict()),
                        1 if character.locked else 0,
                        character.created_at, character.updated_at,
                        character.fingerprint(),
                    ),
                )
                conn.commit()

    def get(self, character_id: str) -> Optional[Character]:
        with self._lock:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT data FROM characters WHERE character_id=?",
                    (character_id,),
                ).fetchone()
                if not row:
                    return None
                return Character.from_dict(json.loads(row["data"]))

    def list_by_niche(self, niche: str) -> list[Character]:
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT data FROM characters WHERE niche=?", (niche,)
                ).fetchall()
                return [Character.from_dict(json.loads(r["data"])) for r in rows]

    def list_all(self) -> list[Character]:
        with self._lock:
            with self._conn() as conn:
                rows = conn.execute("SELECT data FROM characters").fetchall()
                return [Character.from_dict(json.loads(r["data"])) for r in rows]

    def delete(self, character_id: str) -> bool:
        with self._lock:
            with self._conn() as conn:
                cur = conn.execute(
                    "DELETE FROM characters WHERE character_id=?", (character_id,)
                )
                return cur.rowcount > 0


@dataclass
class CharacterAgent:
    """High-level agent for creating, retrieving, and adapting characters.

    Use cases:
      - New campaign: create_persona(template, niche) -> Character
      - Same persona, new niche: switch_niche(character, new_niche) -> Character
      - Get persona: get(character_id) -> Character
      - Voice consistency: get_voice(character) -> dict
    """
    store: CharacterStore = field(default_factory=CharacterStore)
    niche_presets: dict[str, NicheAdaptation] = field(default_factory=lambda: NICHE_PRESETS.copy())
    templates: list[dict[str, Any]] = field(default_factory=lambda: PERSONA_TEMPLATES.copy())

    def __post_init__(self) -> None:
        pass

    def list_niches(self) -> list[str]:
        return sorted(self.niche_presets.keys())

    def get_niche_preset(self, niche: str) -> NicheAdaptation:
        if niche not in self.niche_presets:
            raise ValueError(
                f"Unknown niche: {niche}. Available: {self.list_niches()}"
            )
        return self.niche_presets[niche]

    def add_niche(self, niche: str, adaptation: NicheAdaptation) -> None:
        self.niche_presets[niche] = adaptation
        log.info("character.add_niche %s", niche)

    def create_persona(
        self,
        template_name: str,
        niche: str,
        custom_identity: Optional[PersonaIdentity] = None,
        custom_personality: Optional[PersonalityTraits] = None,
        language: str = ContentLanguage.ID.value,
    ) -> Character:
        template = next((t for t in self.templates if t["name"] == template_name), None)
        if not template:
            raise ValueError(
                f"Template {template_name} not found. Available: "
                f"{[t['name'] for t in self.templates]}"
            )
        if niche not in self.niche_presets:
            raise ValueError(f"Niche {niche} not in presets")
        identity = custom_identity or PersonaIdentity(
            name=template["name"],
            age=template["age"],
            gender=template["gender"],
            location=template["location"],
            background=template["background"],
            languages=["id"],
        )
        personality = custom_personality or PersonalityTraits(
            **template["personality"],
        )
        adaptation = self.niche_presets[niche]
        char_id = f"{identity.name.lower()}_{niche}"
        character = Character(
            character_id=char_id,
            identity=identity,
            personality=personality,
            niche=niche,
            niche_adaptation=adaptation,
            language=language,
            locked=True,
        )
        self.store.save(character)
        log.info("character.created id=%s niche=%s", char_id, niche)
        return character

    def get(self, character_id: str) -> Optional[Character]:
        return self.store.get(character_id)

    def switch_niche(self, character_id: str, new_niche: str) -> Character:
        existing = self.store.get(character_id)
        if not existing:
            raise ValueError(f"Character {character_id} not found")
        if new_niche not in self.niche_presets:
            raise ValueError(f"Niche {new_niche} not in presets")
        new_char = existing.switch_niche(new_niche, self.niche_presets[new_niche])
        self.store.save(new_char)
        return new_char

    def get_voice(self, character: Character) -> dict[str, Any]:
        """Return the voice guide used by content generation."""
        return {
            "identity": asdict(character.identity),
            "tone": character.personality.tone,
            "formality": character.personality.formality,
            "humor": character.personality.humor,
            "energy": character.personality.energy,
            "warmth": character.personality.warmth,
            "values": character.personality.values,
            "personality_tags": character.personality.personality_tags,
            "niche": character.niche,
            "vocabulary": character.niche_adaptation.vocabulary,
            "forbidden_words": character.niche_adaptation.forbidden_words,
            "emoji_set": character.niche_adaptation.emoji_set,
            "hook_patterns": character.niche_adaptation.hook_patterns,
            "cta_patterns": character.niche_adaptation.cta_patterns,
            "language": character.language,
            "fingerprint": character.fingerprint(),
        }

    def generate_content_template(
        self, character: Character, topic: str,
    ) -> dict[str, Any]:
        """Generate a content outline that the LLM/content agent can flesh out."""
        import random
        hook = random.choice(character.niche_adaptation.hook_patterns)
        cta = random.choice(character.niche_adaptation.cta_patterns)
        vocab = ", ".join(character.niche_adaptation.vocabulary[:3])
        return {
            "character_id": character.character_id,
            "niche": character.niche,
            "topic": topic,
            "hook": f"{hook}: {topic}",
            "body_outline": (
                f"As {character.identity.name}, an Indonesian {character.identity.gender} "
                f"in {character.identity.location}, share your authentic take on {topic}. "
                f"Use vocabulary like: {vocab}. "
                f"Tone: {character.personality.tone}, formality: {character.personality.formality:.1f}, "
                f"warmth: {character.personality.warmth:.1f}."
            ),
            "cta": cta,
            "suggested_emojis": character.niche_adaptation.emoji_set[:3],
            "language": character.language,
        }

    def list_for_niche(self, niche: str) -> list[Character]:
        return self.store.list_by_niche(niche)

    def list_all(self) -> list[Character]:
        return self.store.list_all()

    def summary(self) -> dict[str, Any]:
        all_chars = self.store.list_all()
        by_niche: dict[str, int] = {}
        for c in all_chars:
            by_niche[c.niche] = by_niche.get(c.niche, 0) + 1
        return {
            "total_characters": len(all_chars),
            "niches_available": self.list_niches(),
            "characters_by_niche": by_niche,
            "templates_available": len(self.templates),
        }


__all__ = [
    "Character",
    "CharacterAgent",
    "CharacterStore",
    "ContentTone",
    "ContentLanguage",
    "PersonaIdentity",
    "PersonalityTraits",
    "NicheAdaptation",
    "NICHE_PRESETS",
    "PERSONA_TEMPLATES",
    "DEFAULT_DB_PATH",
]
