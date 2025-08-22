# Rule-based MVP: turn free text into goals like
# ["reduce acidity", "increase body", "increase florality"]

from typing import List
import re

# word -> canonical trait
ALIASES = {
    # acidity
    "acidic": "acidity", "sour": "acidity", "bright": "acidity", "tart": "acidity",
    # bitterness
    "bitter": "bitterness", "astringent": "bitterness", "harsh": "bitterness",
    # sweetness
    "sweet": "sweetness", "sugary": "sweetness", "caramel": "sweetness", "honeyed": "sweetness",
    # florality
    "floral": "florality", "jasmine": "florality", "lavender": "florality",
    "blossom": "florality", "aromatic": "florality",
    # body / texture
    "body": "body", "mouthfeel": "body", "thin": "body", "watery": "body",
    "syrupy": "body", "heavy": "body", "thick": "body", "weight": "body",
    # clarity (explicit mentions)
    "clean": "clarity", "clarity": "clarity",
}

INCREASE_CUES = [
    "more", "increase", "stronger", "boost", "enhance", "bring out", "emphasize",
    "heavier", "thicker", "syrupy", "fuller",
]
REDUCE_CUES = [
    "less", "reduce", "mellow", "tone down", "decrease", "suppress", "mute",
    "lighter", "softer", "thin out",
]

def _add_unique(goals: list[str], goal: str) -> None:
    if goal not in goals:
        goals.append(goal)

def parse_goals(text: str) -> List[str]:
    """
    Examples:
      "too acidic and lacks body" -> ["reduce acidity", "increase body"]
      "more florality, less bitterness" -> ["increase florality", "reduce bitterness"]
      "thin and sour" -> ["increase body", "reduce acidity"]
    """
    s = (text or "").lower().strip()
    goals: list[str] = []

    # Rule 1: explicit "more/less <trait>"
    for cue in INCREASE_CUES:
        for w, trait in ALIASES.items():
            if re.search(rf"\b{re.escape(cue)}\s+{re.escape(w)}\b", s):
                _add_unique(goals, f"increase {trait}")
    for cue in REDUCE_CUES:
        for w, trait in ALIASES.items():
            if re.search(rf"\b{re.escape(cue)}\s+{re.escape(w)}\b", s):
                _add_unique(goals, f"reduce {trait}")

    # Rule 2: "lacks <trait>" / "not enough <trait>"
    for w, trait in ALIASES.items():
        if re.search(rf"\blacks\s+{re.escape(w)}\b", s) or re.search(rf"\bnot enough\s+{re.escape(w)}\b", s):
            _add_unique(goals, f"increase {trait}")

    # Rule 3: "too <adj>"
    for w, trait in ALIASES.items():
        if re.search(rf"\btoo\s+{re.escape(w)}\b", s):
            if w in ("thin", "watery"):
                _add_unique(goals, "increase body")
            elif w in ("heavy", "thick", "syrupy"):
                _add_unique(goals, "reduce body")
            else:
                _add_unique(goals, f"reduce {trait}")

    # Rule 4: bare adjectives fallback ("acidic, thin")
    tokens = re.findall(r"[a-z]+", s)
    for t in tokens:
        trait = ALIASES.get(t)
        if not trait:
            continue
        if t in ("thin", "watery"):
            _add_unique(goals, "increase body")
        elif t in ("heavy", "thick", "syrupy"):
            _add_unique(goals, "reduce body")
        elif t in ("acidic", "sour", "bright", "tart"):
            _add_unique(goals, "reduce acidity")
        elif t in ("bitter", "astringent", "harsh"):
            _add_unique(goals, "reduce bitterness")

    return goals or ["increase sweetness"]  # safe default

# Backward-compat alias if any old code calls extract_goals
def extract_goals(text: str) -> List[str]:
    return parse_goals(text)
