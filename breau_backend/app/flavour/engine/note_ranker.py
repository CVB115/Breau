# breau_backend/app/flavour/engines/note_ranker.py
from typing import List, Dict, Optional, Literal, Any

# Purpose:
# Extremely lightweight, heuristic **fallback ranker** for notes, when the
# full semantic ranker is unavailable. Chooses from “florality” vs “body”
# buckets based on the goal vector. Returns [(note_id, score, reason), ...].  :contentReference[oaicite:6]{index=6}

FALLBACK_NOTES = {
    "florality": ["jasmine", "orange_blossom", "bergamot"],
    "body": ["caramelized_sugar", "cocoa_nib", "dark_chocolate"]
}

# Purpose:
# Score a compact list of candidate notes given (goal_vec, context, profile).
def rank(goal_vec: Dict[str, float], context: Dict[str, Any],
         profile: Dict[str, Any]) -> List[tuple[str, float, str]]:
    # Heuristic placeholder: pick from two buckets
    if (goal_vec.get("florality", 0) - abs(goal_vec.get("body", 0))) >= 0:
        lst = FALLBACK_NOTES["florality"]
        reason = "florality goal + gentle context"
    else:
        lst = FALLBACK_NOTES["body"]
        reason = "body goal + robust context"
    return [(n, 0.5 - 0.05*i, reason) for i, n in enumerate(lst)]
