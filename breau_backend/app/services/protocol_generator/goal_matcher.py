# goal_matcher.py
from typing import List, Tuple, Dict, Optional
from ..nlp.anp_extractor import parse_structured_goals
# if you have semantic helpers, import them; otherwise keep it simple
try:
    from ..nlp.semantic import any_matches
except Exception:
    def any_matches(query, candidates, threshold=0.55):
        return []

def match_goals(explicit_goals: Optional[List[Tuple[str, str]]] = None,
                free_text: str = "") -> Dict[str, List[Tuple[str, float]]]:
    """
    Returns:
      {
        "goals":       [(canonical_goal, weight)],
        "preferences": [(facet:value, weight)],
        "avoids":      [(facet:value|note:*, weight)]
      }
    """
    goals: List[Tuple[str, float]] = []
    prefs: List[Tuple[str, float]] = []
    avoids: List[Tuple[str, float]] = []

    # 1) explicit schema goals (strong weight)
    if explicit_goals:
        for direction, trait in explicit_goals:
            if direction and trait:
                goals.append((f"{direction.strip()} {trait.strip()}", 0.9))

    # 2) structured parse from free text (boosts / prefs / avoids)
    b, p, a = parse_structured_goals(free_text or "")
    goals.extend(b); prefs.extend(p); avoids.extend(a)

    # 3) (optional) semantic backoff for fuzzy asks
    candidates = [
        "increase acidity","reduce acidity","increase body","reduce body",
        "increase sweetness","increase florality","reduce bitterness"
    ]
    for cand, sim in any_matches(free_text or "", candidates, threshold=0.55):
        goals.append((cand, min(0.8, 0.4 + sim)))

    # de-dupe by max weight
    def dedupe_max(items: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        cache: Dict[str, float] = {}
        for k, w in items:
            cache[k] = max(w, cache.get(k, 0.0))
        return [(k, cache[k]) for k in cache]

    return {
        "goals": dedupe_max(goals),
        "preferences": dedupe_max(prefs),
        "avoids": dedupe_max(avoids),
    }
