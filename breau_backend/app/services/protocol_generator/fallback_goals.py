# breau_backend/app/services/protocol_generator/fallback_goals.py
from __future__ import annotations
from typing import List, Optional

# What it does:
# Provide cluster-aware default goal tags when the user didn't specify goals.
# We return *tags* (not phrases) because downstream note selection uses tags.
def fallback_goal_tags_for_cluster(
    process: Optional[str],
    roast: Optional[str],
) -> List[str]:
    p = (process or "").lower()
    r = (roast or "").lower()

    # Very small, opinionated defaults that keep suggestions sensible.
    # - Washed + light: emphasize clarity & florality
    # - Natural + medium/dark: aim for rounder body, reduce bitterness hints
    if p == "washed" and r in ("light", "light-medium", "medium-light"):
        return [
            "category:floral",
            "volatility:high",
            "contact_time_affinity:short",
            "temp_affinity:lower",
            "agitation_affinity:low",
        ]
    if p in ("natural", "honey") and r in ("medium", "medium-dark", "dark"):
        return [
            "density:rich",
            "contact_time_affinity:long",
            "temp_affinity:high",
            "texture:syrupy",
        ]

    # Generic fallback: neutral mix that doesn’t over-steer either way.
    return ["density:balanced", "contact_time_affinity:medium"]
