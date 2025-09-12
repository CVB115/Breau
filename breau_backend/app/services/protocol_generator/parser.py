# breau_backend/app/services/protocol_generator/parser.py
from __future__ import annotations
from typing import List, Tuple

# Purpose:
# Agitation tiers in increasing order. We convert labels <-> indices so we can
# safely "bump" agitation up or down by one step without string if/else soup.
AGI_ORDER = ["none", "gentle", "moderate", "high"]

# Purpose:
# Clamp a numeric value to [lo, hi].
def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

# Purpose:
# Parse a ratio like "1:15" and return the denominator (e.g. 15.0).
# Falls back to 15.0 if the string is malformed.
def parse_ratio_den(ratio: str) -> float:
    try:
        _, rhs = ratio.split(":")
        return float(rhs)
    except Exception:
        return 15.0

# Purpose:
# Format a denominator (e.g. 15 or 15.5) back to a "1:X" string.
def format_ratio_den(n: float) -> str:
    n = round(n, 1)
    return f"1:{int(n)}" if float(n).is_integer() else f"1:{n}"

# Purpose:
# Convert an agitation label into its index in AGI_ORDER; default to "gentle".
def _agi_index(a: str) -> int:
    try:
        return AGI_ORDER.index(a)
    except ValueError:
        return 1  # default "gentle"

# Purpose:
# Reduce the last pour's agitation by one tier (if possible).
# Used when we aim for more clarity / less bitterness.
def reduce_late_agitation(pours: List[dict]) -> None:
    if not pours:
        return
    last = pours[-1]
    idx = _agi_index(last.get("agitation", "gentle"))
    if idx > 0:
        last["agitation"] = AGI_ORDER[idx - 1]

# Purpose:
# Increase the middle pour's agitation by one tier (if possible).
# Used when we aim for more body / intensity.
def increase_mid_agitation(pours: List[dict]) -> None:
    if not pours:
        return
    mid_i = len(pours) // 2
    idx = _agi_index(pours[mid_i].get("agitation", "gentle"))
    if idx < len(AGI_ORDER) - 1:
        pours[mid_i]["agitation"] = AGI_ORDER[idx + 1]

# Purpose:
# Given goal phrases and a baseline protocol, compute small bounded nudges for:
# - temp_c (°C), ratio_den (1:X), drawdown_s (seconds)
# and whether we want to tweak agitation tiers mid/late.
# Returns: (temp_c', ratio_den', drawdown_s', pours', want_reduce_late, want_bump_mid)
def bounded_nudges(
    goals: List[str],
    temp_c: float,
    ratio_den: float,
    drawdown_s: int,
    pours: List[dict],
) -> Tuple[float, float, int, List[dict], bool, bool]:
    temp_delta = 0.0
    den_delta = 0.0
    dd_delta = 0.0
    want_reduce_late = False
    want_bump_mid = False

    # Simple, readable mapping from phrases -> variable nudges.
    for phrase in goals:
        if phrase == "increase florality":
            temp_delta += -1.0
            dd_delta += -5.0
        elif phrase == "reduce florality":
            temp_delta += +0.5
            dd_delta += +5.0
        elif phrase == "increase body":
            temp_delta += +1.0
            den_delta += -0.5
            dd_delta += +10.0
            want_bump_mid = True
        elif phrase == "reduce body":
            temp_delta += -0.5
            den_delta += +0.5
            dd_delta += -10.0
            want_reduce_late = True
        elif phrase == "increase sweetness":
            temp_delta += +0.5
            dd_delta += +5.0
        elif phrase == "reduce sweetness":
            temp_delta += -0.5
            dd_delta += -5.0
        elif phrase == "increase acidity":
            temp_delta += -0.75
            dd_delta += -5.0
        elif phrase == "reduce acidity":
            temp_delta += +0.5
            dd_delta += +5.0
        elif phrase == "reduce bitterness":
            temp_delta += -1.0
            den_delta += +0.2
            dd_delta += -10.0
            want_reduce_late = True
        elif phrase == "increase bitterness":
            temp_delta += +0.5
            den_delta += -0.2
            dd_delta += +5.0

    new_temp = clamp(temp_c + temp_delta, temp_c - 3.0, temp_c + 3.0)
    new_den  = clamp(ratio_den + den_delta, max(10.0, ratio_den - 2.0), min(20.0, ratio_den + 2.0))
    new_dd   = int(clamp(drawdown_s + dd_delta, drawdown_s - 30, drawdown_s + 30))
    return new_temp, new_den, new_dd, pours, want_reduce_late, want_bump_mid
