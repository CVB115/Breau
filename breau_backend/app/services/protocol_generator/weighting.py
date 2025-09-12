# breau_backend/app/services/protocol_generator/weighting.py
from __future__ import annotations
from typing import List, Dict

# What it does:
# Map high-level goal traits (florality, body, etc.) into small, safe nudges for
# brew variables (temperature, agitation tier, drawdown). Also provides helpers
# to convert goal pairs -> structured dicts and tier ↔ label.

# String-based agitation order for simple tier math
AGIT_ORDER = ["gentle", "moderate", "high"]

# Safe caps on how much we nudge variables
CAPS = {
    "temperature_c": (-3, +3),   # °C
    "agitation":     (-1, +1),   # tiers: gentle=0, moderate=1, high=2
    "drawdown_s":    (-30, +30), # seconds
}

# How each trait maps to variables (units match CAPS)
WEIGHT_MAP = {
    "florality":       {"temperature_c": -2.5, "agitation": -0.8, "drawdown_s": -12},
    "clarity":         {"agitation": -0.6, "drawdown_s": -15},
    "body":            {"temperature_c": +1.0, "agitation": +0.8, "drawdown_s": +20},
    "acidity":         {"temperature_c": -1.0},
    "sweetness":       {"temperature_c": +0.5, "drawdown_s": +5},
    "bitterness":      {"temperature_c": -1.2, "agitation": -0.4, "drawdown_s": -10},
    "silky_mouthfeel": {"agitation": -0.5, "drawdown_s": +10},
}

# Purpose:
# Normalize free‑form goal pairs like ("increase florality", 1.0)
# into a structured dict: {"trait": "florality", "direction": "increase", "weight": 1.0}
def goal_pairs_to_dicts(pairs: List[tuple[str, float]]) -> List[Dict]:
    """('increase florality', 1.0) -> {'trait':'florality','direction':'increase','weight':1.0}"""
    out: List[Dict] = []
    for g, w in pairs or []:
        t = (g or "").strip().lower()
        direction = "increase"
        trait = t
        if t.startswith("increase "):
            trait = t[len("increase "):]
        elif t.startswith(("reduce ", "less ", "decrease ", "down ")):
            direction = "decrease"
            trait = t.split(" ", 1)[1] if " " in t else t
        out.append({
            "trait": trait,
            "direction": direction,
            "weight": float(w) if isinstance(w, (int, float)) else 1.0
        })
    return out

# Purpose:
# Accumulate variable deltas contributed by each goal dict and clamp by CAPS.
# Returns a dict with keys: temperature_c, agitation, drawdown_s
def accumulate_goal_deltas(goal_dicts: List[Dict]) -> Dict[str, float]:
    """
    Sum variable deltas from goal dicts and clamp to CAPS.
    Returns keys: 'temperature_c', 'agitation', 'drawdown_s'
    """
    acc: Dict[str, float] = {"temperature_c": 0.0, "agitation": 0.0, "drawdown_s": 0.0}
    for g in goal_dicts or []:
        trait = (g.get("trait") or "").strip().lower().replace(" ", "_")
        direction = 1.0 if (g.get("direction") or "increase").lower() == "increase" else -1.0
        w = float(g.get("weight", 1.0)) * direction
        for var, coeff in WEIGHT_MAP.get(trait, {}).items():
            acc[var] = acc.get(var, 0.0) + coeff * w
    # clamp
    for var, delta in list(acc.items()):
        lo, hi = CAPS.get(var, (-999, 999))
        acc[var] = max(lo, min(hi, delta))
    return acc

# Purpose:
# Translate agitation label ↔ tier for simple arithmetic with CAP clamping.
def agit_to_tier(label: str) -> int:
    try:
        return AGIT_ORDER.index((label or "").lower())
    except ValueError:
        return 1  # default moderate

def tier_to_agit(tier: int) -> str:
    if tier < 0: tier = 0
    if tier > 2: tier = 2
    return AGIT_ORDER[tier]
