# breau_backend/app/services/protocol_generator/goal_matcher.py
from __future__ import annotations
from typing import List, Dict, Tuple

# Purpose:
# Normalize multiple goal sources (explicit, parsed, semantic) into a single
# deduped, weighted list like: [("increase florality", 1.0), ...].
# This is the glue between NLP outputs and the protocol nudger.

CANON_ORDER = [
    "increase florality", "reduce florality",
    "increase clarity",   "reduce clarity",
    "increase body",      "reduce body",
    "increase sweetness", "reduce sweetness",
    "increase acidity",   "reduce acidity",
    "increase bitterness","reduce bitterness",
]

_alias = {
    # small equivalence map so NLP can be loose while generator stays precise
    "more body": "increase body",
    "less body": "reduce body",
    "more clarity": "increase clarity",
    "less clarity": "reduce clarity",
    "brighter": "increase acidity",
    "not bitter": "reduce bitterness",
}

# Purpose:
# Convert a free-form phrase to a canonical directive (if known).
def _canon(p: str) -> str:
    p = (p or "").strip().lower()
    return _alias.get(p, p)

# Purpose:
# Stable sort that keeps our canonical preference order while preserving
# user weighting as a tiebreaker.
def _stable_sort(goals: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    idx = {k: i for i, k in enumerate(CANON_ORDER)}
    return sorted(goals, key=lambda kv: (idx.get(kv[0], 999), -float(kv[1])))

# Purpose:
# Merge multiple sources of goals with optional weights and remove duplicates.
# Later duplicates accumulate weight (so repeated intent matters).
def merge_goals(
    explicit: List[Tuple[str, float]] | None,
    parsed:   List[Tuple[str, float]] | None,
    semantic: List[Tuple[str, float]] | None,
) -> List[Tuple[str, float]]:
    bucket: Dict[str, float] = {}
    for src in (explicit or []), (parsed or []), (semantic or []):
        for (phrase, w) in src:
            key = _canon(phrase)
            if not key:
                continue
            bucket[key] = bucket.get(key, 0.0) + (float(w) if isinstance(w, (int, float)) else 1.0)
    items = list(bucket.items())
    return _stable_sort(items)

# Purpose:
# Convert a resolved goals list into two utility forms:
# - phrases: ["increase florality", ...]
# - weighted: [("increase florality", 1.0), ...] (for downstream semantic/note ranker)
def goals_as_phrases_and_weighted(
    goals: List[Tuple[str, float]]
) -> tuple[list[str], list[Tuple[str, float]]]:
    phrases = [g for (g, _w) in goals]
    return phrases, goals
