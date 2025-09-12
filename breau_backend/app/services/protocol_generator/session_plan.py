from __future__ import annotations
from typing import List, Dict, Any
from breau_backend.app.schemas import Agitation

__all__ = ["build_session_plan"]

# What it does:
# Turn an internal list of "pours" into a beginner‑friendly, step‑by‑step brew guide
# suitable for voice prompts or on‑screen instructions. We keep it simple:
# - First step is always Bloom
# - Subsequent steps accumulate target water mass and label agitation as early/late
def build_session_plan(pours: List[Any], ag_early: Agitation, ag_late: Agitation) -> Dict[str, Any]:
    """
    Create a beginner-friendly session plan (voice / step-by-step) from the pours.
    """
    steps: List[Dict[str, Any]] = []

    if pours:
        p0 = pours[0]
        steps.append({
            "id": "bloom",
            "instruction": f"Bloom {p0.water_g} g, swirl gently.",
            "gate": "pour_until",
            "target_water_g": p0.water_g,
            "timer_s": None,
            "voice_prompt": "Bloom thirty grams, then swirl gently.",
            "note": "Bloom",
        })

    cum = pours[0].water_g if pours else 0
    for i, p in enumerate(pours[1:], start=1):
        cum += p.water_g
        phase = "early" if i == 1 else "late"
        ag = ag_early if i == 1 else ag_late
        steps.append({
            "id": f"step{i}",
            "instruction": f"Pour to {cum} g, {phase} {ag.name.lower()} agitation.",
            "gate": "pour_until",
            "target_water_g": cum,
            "timer_s": None,
            "voice_prompt": None,
            "note": None,
        })

    return {"mode_default": "beginner", "steps": steps}
