# breau_backend/app/services/protocol_generator/fallback.py
from __future__ import annotations
from typing import Optional
from breau_backend.app.schemas import BrewSuggestion, PourStepIn, Agitation

from .session_plan import build_session_plan


# What it does:
# Build a minimal fallback suggestion when no goals/pours provided.
def build_fallback_suggestion(
    *,
    method: str = "v60-style",
    ratio: str = "1:15",
    total_water_g: int = 225,
    temperature_c: int = 91,
    early_agitation: Agitation = Agitation.MODERATE,
    late_agitation: Agitation = Agitation.MODERATE,
    filter_hint: Optional[str] = "medium filter",
    notes: Optional[str] = "Basic recipe fallback (medium agitation, medium grind).",
) -> BrewSuggestion:
    pours = [
        PourStepIn(water_g=30, agitation=early_agitation, kettle_temp_c=temperature_c, note="Bloom"),
        PourStepIn(water_g=64, agitation=early_agitation, kettle_temp_c=temperature_c),
        PourStepIn(water_g=64, agitation=late_agitation, kettle_temp_c=temperature_c),
        PourStepIn(water_g=67, agitation=late_agitation, kettle_temp_c=temperature_c),
    ]

    session_plan = build_session_plan(pours, early_agitation, late_agitation)

    return BrewSuggestion(
        method=method,
        ratio=ratio,
        total_water_g=total_water_g,
        temperature_c=temperature_c,
        agitation_overall=late_agitation,
        filter_hint=filter_hint,
        expected_drawdown_s=165,
        pours=pours,
        notes=notes,
        session_plan=session_plan,
        predicted_notes=[],
        alternative=None,
        grind_label="",
    )
