"""SEO optimization toolkit.

Keyword research (mocked, deterministic via MD5 seed), content scoring,
title/meta generation, entity extraction, and internal-link suggestions.
"""
from __future__ import annotations

import logging
import re
import hashlib
import math
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

log = logging.getLogger(__name__)


# Hard caps to prevent the optimizer from blowing memory / CPU on pathological
# inputs (e.g. a 1GB content blob).  Pydantic-style validators expressed as
# constants so we don't add a Pydantic dependency for what amounts to two
# length checks.
MAX_CONTENT_LENGTH: int = 50_000
MAX_KEYWORD_LENGTH: int = 200


STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "on", "at", "for", "with", "by", "from", "as", "this", "that",
    "it", "its", "i", "you", "we", "they", "he", "she", "my", "your", "our", "their",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "not", "no", "if", "so", "than", "then", "also", "just", "very", "more", "most",
    "some", "any", "all", "can", "may", "might", "must", "shall", "about", "into",
}


@dataclass
class Keyword:
    term: str
    search_volume: int = 0
    competition: float = 0.0
    cpc_usd: float = 0.0
    trend: str = "stable"
    intent: str = "informational"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SEOScore:
    overall: float
    keyword_density: float
    title_score: float
    meta_score: float
    readability: float
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SEOOptimizer:
    def __init__(self) -> None:
        self._cache: dict[str, list[Keyword]] = {}

    async def research_keywords(
        self, seed: str, niche: str, max_results: int = 20
    ) -> list[Keyword]:
        key = f"{seed}:{niche}:{max_results}"
        if key in self._cache:
            return list(self._cache[key])
        results: list[Keyword] = []
        prefixes = ["best", "top", "cheap", "affordable", "how to", "what is", "vs", "review"]
        suffixes = ["2026", "guide", "tips", "tutorial", "near me", "online", "free", "examples"]
        bases: list[str] = []
        for src in (seed, niche):
            if src:
                for w in src.lower().split():
                    if w and len(w) > 1 and w not in bases:
                        bases.append(w)
        seen: set[str] = set()
        modifiers: list[tuple[str, str]] = (
            [("p", p) for p in prefixes] + [("s", s) for s in suffixes]
        )
        if not bases:
            bases = [seed.lower().strip() or "topic"]
        # Cycle through base × modifier until we have enough or run out
        i = 0
        max_iters = max_results * 4
        while len(results) < max_results and i < max_iters:
            base = bases[i % len(bases)]
            kind, val = modifiers[(i // len(bases)) % len(modifiers)]
            term = f"{val} {base}" if kind == "p" else f"{base} {val}"
            if term not in seen:
                seen.add(term)
                results.append(self._make_keyword(term, seed))
            i += 1
        # Fallback: numeric variants if still short
        n = 1
        while len(results) < max_results:
            term = f"{seed} variant {n}"
            if term not in seen:
                seen.add(term)
                results.append(self._make_keyword(term, seed))
            n += 1
        results = results[:max_results]
        self._cache[key] = results
        return list(results)

    def _make_keyword(self, term: str, seed: str) -> Keyword:
        h = int(hashlib.md5(term.encode()).hexdigest()[:8], 16)
        intents = ["informational", "transactional", "navigational"]
        trends = ["rising", "stable", "declining"]
        return Keyword(
            term=term,
            search_volume=100 + (h % 50000),
            competition=round((h % 1000) / 1000.0, 3),
            cpc_usd=round((h % 500) / 100.0, 2),
            trend=trends[h % 3],
            intent=intents[h % 3],
        )

    def _tokenize(self, text: str) -> list[str]:
        return [
            w.lower().strip(".,!?;:()[]{}\"'")
            for w in re.split(r"\s+", text)
            if w
        ]

    def _word_count(self, text: str) -> int:
        return len([w for w in self._tokenize(text) if w and w not in STOPWORDS])

    def score_content(self, content: str, target_keyword: str) -> SEOScore:
        if content is not None and len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f"content too long: {len(content)} chars (max {MAX_CONTENT_LENGTH})"
            )
        if target_keyword and len(target_keyword) > MAX_KEYWORD_LENGTH:
            raise ValueError(
                f"target_keyword too long: {len(target_keyword)} chars (max {MAX_KEYWORD_LENGTH})"
            )
        if not content:
            return SEOScore(
                overall=0.0,
                keyword_density=0.0,
                title_score=0.0,
                meta_score=0.0,
                readability=0.0,
                suggestions=["Content is empty"],
            )
        tokens = self._tokenize(content)
        kw_lower = target_keyword.lower()
        kw_count = sum(1 for t in tokens if t == kw_lower or kw_lower in t)
        total_words = max(1, len(tokens))
        density = (kw_count / total_words) * 100.0
        first_line = content.split("\n", 1)[0].strip()
        title_score = 0.0
        if 20 <= len(first_line) <= 60:
            title_score += 50.0
        elif len(first_line) > 0:
            title_score += 25.0
        if kw_lower in first_line.lower():
            title_score += 50.0
        meta_score = 0.0
        if 120 <= len(content) <= 320:
            meta_score = 100.0
        elif len(content) >= 60:
            meta_score = 60.0
        else:
            meta_score = 30.0
        sentences = max(1, len([s for s in re.split(r"[.!?]+", content) if s.strip()]))
        avg_sentence_len = total_words / sentences
        avg_word_len = sum(len(t) for t in tokens) / total_words
        readability = 100.0 - min(
            100.0,
            max(0.0, (avg_sentence_len - 15) * 3 + (avg_word_len - 5) * 10),
        )
        kw_density_score = (
            100.0
            if 0.5 <= density <= 2.5
            else max(0.0, 100.0 - abs(density - 1.5) * 30)
        )
        overall = (
            title_score * 0.25
            + meta_score * 0.20
            + readability * 0.30
            + kw_density_score * 0.25
        )
        # Build suggestions directly to avoid recursion with suggest_improvements
        suggestions: list[str] = []
        if first_line:
            if len(first_line) < 20:
                suggestions.append("Title is too short; aim for 20-60 characters")
            elif len(first_line) > 60:
                suggestions.append("Title is too long; aim for 20-60 characters")
            if target_keyword.lower() not in first_line.lower():
                suggestions.append(f"Include target keyword '{target_keyword}' in title")
        else:
            suggestions.append("Add a title as the first line")
        if density < 0.5:
            suggestions.append(
                f"Increase keyword density (currently {density:.2f}%)"
            )
        elif density > 2.5:
            suggestions.append(
                f"Reduce keyword density (currently {density:.2f}%)"
            )
        if readability < 50:
            suggestions.append(
                "Improve readability: use shorter sentences and simpler words"
            )
        if len(content) < 300:
            suggestions.append("Content is short; aim for at least 300 words")
        return SEOScore(
            overall=max(0.0, min(100.0, overall)),
            keyword_density=round(density, 3),
            title_score=max(0.0, min(100.0, title_score)),
            meta_score=max(0.0, min(100.0, meta_score)),
            readability=max(0.0, min(100.0, readability)),
            suggestions=suggestions,
        )

    def suggest_improvements(self, content: str, target_keyword: str) -> list[str]:
        if content is not None and len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f"content too long: {len(content)} chars (max {MAX_CONTENT_LENGTH})"
            )
        if target_keyword and len(target_keyword) > MAX_KEYWORD_LENGTH:
            raise ValueError(
                f"target_keyword too long: {len(target_keyword)} chars (max {MAX_KEYWORD_LENGTH})"
            )
        suggestions: list[str] = []
        if not content or not content.strip():
            return ["Add content"]
        first_line = content.split("\n", 1)[0].strip()
        if len(first_line) < 20:
            suggestions.append("Title is too short; aim for 20-60 characters")
        elif len(first_line) > 60:
            suggestions.append("Title is too long; aim for 20-60 characters")
        if target_keyword.lower() not in first_line.lower():
            suggestions.append(f"Include target keyword '{target_keyword}' in title")
        # Compute density directly to avoid recursion
        tokens = self._tokenize(content)
        kw_lower = target_keyword.lower()
        kw_count = sum(1 for t in tokens if t == kw_lower or kw_lower in t)
        total_words = max(1, len(tokens))
        density = (kw_count / total_words) * 100.0
        # Compute readability directly
        sentences = max(1, len(re.split(r"[.!?]+", content)))
        avg_sentence_len = total_words / sentences
        avg_word_len = sum(len(t) for t in tokens) / total_words
        readability = 100.0 - min(100.0, max(0.0, (avg_sentence_len - 15) * 3 + (avg_word_len - 5) * 10))
        if density < 0.5:
            suggestions.append(
                f"Increase keyword density (currently {density:.2f}%)"
            )
        elif density > 2.5:
            suggestions.append(
                f"Reduce keyword density (currently {density:.2f}%)"
            )
        if readability < 50:
            suggestions.append(
                "Improve readability: use shorter sentences and simpler words"
            )
        if len(content) < 300:
            suggestions.append("Content is short; aim for at least 300 words")
        return suggestions

    def generate_meta_description(self, content: str, max_length: int = 160) -> str:
        if content is not None and len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f"content too long: {len(content)} chars (max {MAX_CONTENT_LENGTH})"
            )
        if not content or not content.strip():
            return ""
        text = re.sub(r"\s+", " ", content).strip()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        desc = ""
        truncated = False
        for s in sentences:
            candidate = (desc + " " + s).strip() if desc else s.strip()
            if len(candidate) <= max_length:
                desc = candidate
            else:
                truncated = True
                break
        if not desc:
            # Hard-truncate; append ellipsis if truncation actually occurred
            desc = text[:max_length]
            if len(text) > max_length and max_length >= 3:
                room = max_length - 3
                desc = desc[:room]
                if " " in desc:
                    desc = desc.rsplit(" ", 1)[0]
                desc = desc.rstrip() + "..."
        elif truncated and not desc.rstrip().endswith((".", "!", "?")):
            # Mid-sentence break; append ellipsis
            room = max_length - 3
            if room > 0 and len(desc) > room:
                desc = desc[:room]
            if " " in desc:
                desc = desc.rsplit(" ", 1)[0]
            desc = desc.rstrip() + "..."
        return desc

    def generate_title_variants(
        self, content: str, target_keyword: str, count: int = 5
    ) -> list[str]:
        templates = [
            f"{target_keyword}: The Ultimate Guide",
            f"How to Master {target_keyword} in 2026",
            f"Top 10 {target_keyword} Tips You Need to Know",
            f"{target_keyword} Explained (Beginner to Advanced)",
            f"Why {target_keyword} Matters and How to Use It",
            f"The Complete {target_keyword} Handbook",
            f"{target_keyword}: Common Mistakes to Avoid",
        ]
        return templates[:count]

    def extract_entities(self, content: str) -> list[str]:
        tokens = re.findall(r"\b[A-Z][a-z]{2,}\b", content)
        quoted = re.findall(r'"([^"]+)"', content)
        seen: list[str] = []
        for t in tokens + quoted:
            if t and t not in seen:
                seen.append(t)
        return seen

    def internal_link_suggestions(
        self, content: str, existing_urls: list[str]
    ) -> list[str]:
        suggestions: list[str] = []
        text_lower = content.lower()
        for url in existing_urls:
            anchor = url.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ")
            if not anchor:
                continue
            if anchor.lower() in text_lower:
                suggestions.append(f"Link '{anchor}' to {url}")
        return suggestions
