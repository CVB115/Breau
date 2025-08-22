# breau_backend/app/protocol_generator/goal_matcher.py
from __future__ import annotations
from typing import Iterable, Optional

# absolute imports so uvicorn reload + py3.13 are happy
from breau_backend.app.services.nlp.anp_extractor import parse_goals
from breau_backend.app.services.nlp.semantic import any_matches

DEFAULT_CANDIDATES = [
    "increase florality","reduce florality",
    "increase body","reduce body",
    "increase sweetness","reduce sweetness",
    "increase acidity","reduce acidity",
    "reduce bitterness","increase bitterness",
]

def _canonical(phrase: str) -> Optional[str]:
    p = (phrase or "").strip().lower()
    return p if p in DEFAULT_CANDIDATES else None

def match_goals(
    explicit_goals: Optional[Iterable[tuple[str, str]]] = None,  # [("increase","florality"), ...]
    free_text: Optional[str] = None,
    candidates: list[str] = DEFAULT_CANDIDATES,
) -> list[tuple[str, float]]:
    merged: dict[str, float] = {}

    # 1) explicit goals (highest weight)
    if explicit_goals:
        for direction, trait in explicit_goals:
            canon = _canonical(f"{direction.strip().lower()} {trait.strip().lower()}")
            if canon:
                merged[canon] = max(merged.get(canon, 0.0), 0.90)

    # 2) rules from free text (strong)
    if free_text:
        for g in parse_goals(free_text):
            canon = _canonical(g)
            if canon:
                merged[canon] = max(merged.get(canon, 0.0), 0.80)

    # 3) semantic (softer)
    if free_text:
        for phrase, score in any_matches(free_text, candidates, threshold=0.48)[:3]:
            canon = _canonical(phrase)
            if not canon:
                continue
            # map cosine score to [0.35, 0.70]
            w = 0.35 + 0.35 * max(0.0, min(1.0, (score - 0.48) / (0.85 - 0.48)))
            merged[canon] = max(merged.get(canon, 0.0), w)

    return sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
