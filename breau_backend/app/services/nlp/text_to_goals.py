# breau_backend/app/services/nlp/text_to_goals.py
from __future__ import annotations
import re
from collections import defaultdict
from typing import List, Dict, Set

# --- keyword → trait dictionaries ---------------------------------
# default intent for these keywords is "increase"
INC: Dict[str, Set[str]] = {
    "acidity": {"bright", "brighter", "juicy", "lively", "sparkling", "tart", "zesty"},
    "clarity": {"clear", "clean", "transparent", "crisp"},
    "sweetness": {"sweet", "sweeter", "honeyed", "caramelly", "caramel", "sugarcane"},
    "florality": {"floral", "jasmine", "tea-like", "tea", "perfumed"},
    "body": {"body", "full", "fuller", "syrupy", "rich", "thick", "heavy"},
}

# default intent for these keywords is "decrease"
DEC: Dict[str, Set[str]] = {
    "bitterness": {"bitter", "bitterness", "harsh", "ashy"},
    "astringency": {"drying", "astringent", "puckering"},
    # body can be decreased too (for 'lighter body')
    "body": {"light body", "lighter body", "thinner"},
}

# multi-word phrases we want to catch first (mapped to (trait, direction))
PHRASES: Dict[str, tuple[str, str]] = {
    "less bitter": ("bitterness", "decrease"),
    "reduce bitterness": ("bitterness", "decrease"),
    "not bitter": ("bitterness", "decrease"),
    "less astringent": ("astringency", "decrease"),
    "more clarity": ("clarity", "increase"),
    "more body": ("body", "increase"),
    "less body": ("body", "decrease"),
    "clean cup": ("clarity", "increase"),
}

# generic comparators to flip direction when paired with a keyword
MORE = {"more", "increase", "increased", "boost", "stronger", "extra"}
LESS = {"less", "decrease", "decreased", "reduce", "lower", "weaker"}

def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s\-]", " ", text)  # strip punctuation, keep spaces/hyphens
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _weight(n: int) -> int:
    # 1 mention → weight 1; 2–3 → 2; 4+ → 3
    return 1 if n <= 1 else (2 if n <= 3 else 3)

# --- NEW: simple morphological reduction for comparatives/superlatives ----
def _collect_bases(d: Dict[str, Set[str]]) -> Set[str]:
    s: Set[str] = set()
    for kws in d.values():
        s |= set(kws)
    return s

_ALL_BASES = _collect_bases(INC) | _collect_bases(DEC)

def _morph_reduce(tok: str) -> str:
    """
    Reduce simple comparative/superlative endings to base if the base
    is a known keyword. E.g., cleaner->clean, sweetest->sweet, fuller->full.
    Safe: only reduces when base exists in our known vocabulary.
    """
    for suf in ("er", "est"):
        if tok.endswith(suf) and len(tok) > len(suf) + 2:
            base = tok[: -len(suf)]
            if base in _ALL_BASES:
                return base
    return tok

# -------------------------------------------------------------------------

def parse_text_to_goals(text: str) -> List[Dict]:
    """
    Convert free text like 'brighter, cleaner, less bitter' to:
      [{"trait":"acidity","direction":"increase","weight":2}, ...]
    """
    if not text or not text.strip():
        return []

    t = _normalize(text)
    # count buckets: (trait, direction) -> count
    counts = defaultdict(int)

    # 1) phrase pass (handles 'less bitter', 'clean cup', etc.)
    for phrase, (trait, direction) in PHRASES.items():
        if phrase in t:
            c = t.count(phrase)
            counts[(trait, direction)] += c
            t = t.replace(phrase, " ")

    # 2) token pass with neighbor lookups for MORE/LESS + morph reduction
    raw_tokens = t.split()
    tokens = [_morph_reduce(x) for x in raw_tokens]

    for i, tok in enumerate(tokens):
        # check INC keywords
        for trait, kws in INC.items():
            if tok in kws:
                direction = "increase"
                if i > 0 and raw_tokens[i - 1] in LESS:
                    direction = "decrease"
                counts[(trait, direction)] += 1
        # check DEC keywords
        for trait, kws in DEC.items():
            if tok in kws:
                direction = "decrease"
                if i > 0 and raw_tokens[i - 1] in MORE:
                    direction = "increase"
                counts[(trait, direction)] += 1

    # 3) collapse opposing intents per trait (net direction by counts)
    per_trait = defaultdict(lambda: {"increase": 0, "decrease": 0})
    for (trait, direction), n in counts.items():
        per_trait[trait][direction] += n

    goals: List[Dict] = []
    for trait, tally in per_trait.items():
        inc, dec = tally["increase"], tally["decrease"]
        if inc == 0 and dec == 0:
            continue
        if inc >= dec:
            goals.append({"trait": trait, "direction": "increase", "weight": _weight(inc - dec or inc)})
        else:
            goals.append({"trait": trait, "direction": "decrease", "weight": _weight(dec - inc)})

    # stable order for tests/UI
    trait_order = {"clarity":0, "acidity":1, "sweetness":2, "body":3, "bitterness":4, "astringency":5, "florality":6}
    goals.sort(key=lambda g: trait_order.get(g["trait"], 999))
    return goals
