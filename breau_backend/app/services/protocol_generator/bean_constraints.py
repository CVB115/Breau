# breau_backend/app/services/protocol_generator/bean_constraints.py
from __future__ import annotations
from typing import Dict, Any

# Purpose:
# Provide optional bean-specific caps or nudges discovered during testing.
# These are *soft* constraints to keep suggestions realistic for certain lots.
# If a bean has unusual processing or known limits, we can bound variables here.

# Example constraint schema (all optional):
# {
#   "max_temp_c": 93,
#   "min_temp_c": 88,
#   "min_ratio_den": 14.5,
#   "max_ratio_den": 17.5,
#   "agitation_cap": "moderate",   # cap late agitation at this tier
#   "notes_bias": ["jasmine","bergamot"]  # tiny +confidence boost
# }

# Purpose:
# Return constraints dict for a bean_id/alias if we have one, else {}.
# (Right now a stub; extend to read from ./data/library/beans.json extras if needed.)
def constraints_for(bean_id: str | None) -> Dict[str, Any]:
    _stub = {}  # plug a small per-bean table here if desired
    return _stub

# Purpose:
# Apply soft bounds to the trio (temp_c, ratio_den, late_agitation_label).
def apply_soft_caps(
    temp_c: float,
    ratio_den: float,
    late_agit: str,
    caps: Dict[str, Any] | None,
) -> tuple[float, float, str]:
    if not caps:
        return temp_c, ratio_den, late_agit

    # temperature bounds
    lo = float(caps.get("min_temp_c", temp_c - 999))
    hi = float(caps.get("max_temp_c", temp_c + 999))
    if temp_c < lo: temp_c = lo
    if temp_c > hi: temp_c = hi

    # ratio bounds (denominator of "1:X")
    lo = float(caps.get("min_ratio_den", ratio_den - 999))
    hi = float(caps.get("max_ratio_den", ratio_den + 999))
    if ratio_den < lo: ratio_den = lo
    if ratio_den > hi: ratio_den = hi

    # agitation cap
    cap = (caps.get("agitation_cap") or "").lower()
    if cap in ("gentle", "moderate", "high"):
        order = ["gentle", "moderate", "high"]
        if order.index(late_agit) > order.index(cap):
            late_agit = cap

    return temp_c, ratio_den, late_agit
