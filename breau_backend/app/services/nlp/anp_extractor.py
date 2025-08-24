# anp_extractor.py
# Turn free text into structured brewing intents.
# Keeps existing parse_goals() for backward-compat; adds parse_structured_goals().

from typing import List, Tuple
import re

# --- Backward-compatible bits (unchanged callers can keep using this) ---

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
    # clarity
    "clean": "clarity", "clarity": "clarity",
}
INCREASE_CUES = ["more", "increase", "stronger", "boost", "enhance", "bring out", "emphasize", "heavier", "thicker", "syrupy", "fuller"]
REDUCE_CUES   = ["less", "reduce", "mellow", "tone down", "decrease", "suppress", "mute", "lighter", "softer", "thin out"]

def _add_unique(goals: list[str], goal: str) -> None:
    if goal not in goals:
        goals.append(goal)

def parse_goals(text: str) -> List[str]:
    """Legacy extractor that yields canonical goals only (no preferences/avoids)."""
    s = (text or "").lower().strip()
    goals: list[str] = []

    # explicit "more/less X"
    for cue in INCREASE_CUES:
        for w, trait in ALIASES.items():
            if re.search(rf"\b{re.escape(cue)}\s+{re.escape(w)}\b", s):
                _add_unique(goals, f"increase {trait}")
    for cue in REDUCE_CUES:
        for w, trait in ALIASES.items():
            if re.search(rf"\b{re.escape(cue)}\s+{re.escape(w)}\b", s):
                _add_unique(goals, f"reduce {trait}")

    # lacks / not enough
    for w, trait in ALIASES.items():
        if re.search(rf"\blacks\s+{re.escape(w)}\b", s) or re.search(rf"\bnot enough\s+{re.escape(w)}\b", s):
            _add_unique(goals, f"increase {trait}")

    # too <adj>
    for w, trait in ALIASES.items():
        if re.search(rf"\btoo\s+{re.escape(w)}\b", s):
            if w in ("thin", "watery"):
                _add_unique(goals, "increase body")
            elif w in ("heavy", "thick", "syrupy"):
                _add_unique(goals, "reduce body")
            else:
                _add_unique(goals, f"reduce {trait}")

    # bare adjectives fallback ("acidic, thin")
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

# --- NEW: structured extractor for boosts + preferences + avoids ---

try:
    # optional: coarse whole-sentence polarity (used only to bump weights)
    from .sentiment import analyze_sentiment
except Exception:
    def analyze_sentiment(text: str):  # fallback
        return {"label": "neutral", "score": 0.0}

def parse_structured_goals(text: str) -> tuple[list[tuple[str, float]], list[tuple[str, float]], list[tuple[str, float]]]:
    """
    Returns:
      boosts      -> [(canonical_goal, weight)]
      preferences -> [(facet:value, weight)]
      avoids      -> [(facet:value|note:*, weight)]
    Example:
      "highlight acidity but not vinegary, more lime/citrusy"
        -> boosts:       [("increase acidity", 0.85)]
           preferences:  [("acidity_family:citric", 0.9)]
           avoids:       [("acidity_family:acetic", 0.9), ("note:vinegar", 0.8)]
    """
    s = (text or "").lower().strip()
    boosts: list[tuple[str, float]] = []
    prefs:  list[tuple[str, float]] = []
    avoids: list[tuple[str, float]] = []

    # 1) polarity/intents
    if re.search(r"\b(highlight|more|increase|brighter|zesty)\b.*\bacid", s):
        boosts.append(("increase acidity", 0.85))
    if re.search(r"\b(less|reduce|mellow|softer|smoother)\b.*\bacid", s) or "too acidic" in s or "too sour" in s:
        boosts.append(("reduce acidity", 0.85))
    if re.search(r"\b(more|increase|thicker|fuller|syrupy)\b.*\b(body|mouthfeel)\b", s):
        boosts.append(("increase body", 0.8))
    if re.search(r"\b(lighter|reduce|thin out)\b.*\b(body|mouthfeel)\b", s):
        boosts.append(("reduce body", 0.8))
    if re.search(r"\b(more|increase)\b.*\b(floral|florality|jasmine)\b", s):
        boosts.append(("increase florality", 0.8))

    # 2) preferences: *which kind*
    if re.search(r"\b(lime|lemon|citrus|citrusy)\b", s):
        prefs.append(("acidity_family:citric", 0.9))
    if re.search(r"\b(apple|pear|malic)\b", s):
        prefs.append(("acidity_family:malic", 0.8))
    if re.search(r"\b(grape|winey|tartaric)\b", s):
        prefs.append(("acidity_family:tartaric", 0.7))
    if re.search(r"\b(silky|rounder)\b", s):
        prefs.append(("texture:silky", 0.6))
    if re.search(r"\b(crisp|snappy)\b", s):
        prefs.append(("texture:crisp", 0.6))

    # 3) avoids: explicit negations
    if re.search(r"\bnot\s+vinegary\b|\bno\s+vinegar\b|\bacetic\b", s):
        avoids.append(("acidity_family:acetic", 0.9))
        avoids.append(("note:vinegar", 0.8))

    # bump avoids if sentiment is strongly negative overall around vinegar-ish asks
    if "vinegar" in s or "vinegary" in s:
        sent = analyze_sentiment(text or "")
        if sent["label"] == "negative" and sent["score"] >= 0.7:
            avoids = [(tag, min(1.0, w + 0.1)) for tag, w in avoids] or [("acidity_family:acetic", 0.85)]

    if not boosts and not prefs and not avoids:
        boosts = [("increase sweetness", 0.6)]

    return boosts, prefs, avoids
