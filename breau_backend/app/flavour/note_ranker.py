from typing import Dict, Any, List, Tuple

FALLBACK_NOTES = {
    "florality": ["jasmine", "orange_blossom", "bergamot"],
    "body": ["caramelized_sugar", "cocoa_nib", "dark_chocolate"]
}

def rank(goal_vec: Dict[str, float], context: Dict[str, Any],
         profile: Dict[str, Any]) -> List[Tuple[str, float, str]]:
    # Heuristic placeholder: pick from two buckets
    if (goal_vec.get("florality", 0) - abs(goal_vec.get("body", 0))) >= 0:
        lst = FALLBACK_NOTES["florality"]
        reason = "florality goal + gentle context"
    else:
        lst = FALLBACK_NOTES["body"]
        reason = "body goal + robust context"
    return [(n, 0.5 - 0.05*i, reason) for i, n in enumerate(lst)]
