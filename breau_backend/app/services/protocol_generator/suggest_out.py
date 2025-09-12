from __future__ import annotations
from typing import List, Optional
from breau_backend.app.schemas import (
    BrewSuggestRequest, BrewSuggestion, BrewSuggestionVariant,
    PourStepIn, Agitation, PredictedNote
)
from .session_plan import build_session_plan
from breau_backend.app.schemas import PourStyle
# Optional grind math (cosmetic label), safe if missing.
try:
    from breau_backend.app.flavour.engine.grind_math import setting_for_microns_grinder  # type: ignore
except Exception:  # pragma: no cover
    def setting_for_microns_grinder(*_args, **_kwargs):
        return {}

def _overall_from_phases(early: Agitation, late: Agitation) -> Agitation:
    order = [Agitation.GENTLE, Agitation.MODERATE, getattr(Agitation, "ROBUST", Agitation.MODERATE)]
    return early if order.index(early) >= order.index(late) else late

def _compose_summary(
    temperature_c: int,
    ratio_den: float,
    ag_early: Agitation,
    ag_late: Agitation,
    filter_hint: Optional[str],
) -> str:
    bits = [
        f"Set temperature {temperature_c}°C",
        f"ratio 1:{ratio_den:.1f}",
        f"early {ag_early.name.lower()}",
        f"late {ag_late.name.lower()}",
    ]
    blurb = []
    if temperature_c <= 91:
        blurb.append("Cooler water + gentle early agitation to preserve brightness")
    elif temperature_c >= 93:
        blurb.append("Warmer water + stronger late agitation to round out sugars and body")
    else:
        blurb.append("Balanced temperature with controlled agitation for clarity and sweetness")
    if filter_hint:
        blurb.append(
            "fast filter for clarity" if "fast" in filter_hint
            else ("slow filter for fuller body" if "slow" in filter_hint else "")
        )
    return f"{', '.join(bits)}. " + "; ".join([b for b in blurb if b]) + "."

def finalize_pours_and_plan(
    *,
    req: BrewSuggestRequest,
    ratio_den: float,
    temperature_c: int,
    early_enum: Agitation,
    late_enum: Agitation,
    filter_hint: Optional[str],
    pours_from_candidates: List[PourStepIn] | None = None,
) -> tuple[list[PourStepIn], dict, str, str, Agitation]:
    pours = [PourStepIn(**(p.model_dump() if hasattr(p, "model_dump") else dict(p))) for p in (pours_from_candidates or [])]
    if not pours:
        bloom = PourStepIn(
            water_g=30,
            agitation=Agitation.GENTLE,
            kettle_temp_c=int(temperature_c),
            pour_style=PourStyle.SPIRAL,
            wait_for_bed_ready=True,
            note="Bloom"
        )
        mid = PourStepIn(
            water_g=120,
            agitation=Agitation.MODERATE,
            kettle_temp_c=int(temperature_c),
            pour_style=PourStyle.SPIRAL,
            wait_for_bed_ready=True
        )
        late = PourStepIn(
            water_g=90,
            agitation=late_enum,
            kettle_temp_c=int(temperature_c),
            pour_style=PourStyle.CENTER,
            wait_for_bed_ready=True
        )
        pours = [bloom, mid, late]

    for p in pours:
        p.kettle_temp_c = int(temperature_c)

    ratio_str = f"1:{ratio_den:.1f}".rstrip("0").rstrip(".")
    notes_text = _compose_summary(int(temperature_c), float(ratio_den), early_enum, late_enum, filter_hint)

    # --- NEW: append breadcrumb if personalization overlays were applied upstream ---
    try:
        crumb = getattr(req, "_explain_breadcrumb", None)
        if crumb:
            notes_text = (notes_text.rstrip(".") + f". {crumb}") if notes_text else str(crumb)
    except Exception:
        # Never block the plan for a cosmetic note
        pass

    plan = build_session_plan(pours, early_enum, late_enum)
    overall = _overall_from_phases(early_enum, late_enum)
    return pours, plan, notes_text, ratio_str, overall

def _to_agit_enum(val) -> Agitation:
    if isinstance(val, Agitation):
        return val
    s = str(val).lower()
    mapping = {
        "gentle": Agitation.GENTLE, "low": Agitation.GENTLE,
        "moderate": Agitation.MODERATE, "medium": Agitation.MODERATE,
        "high": getattr(Agitation, "ROBUST", Agitation.MODERATE),
        "robust": getattr(Agitation, "ROBUST", Agitation.MODERATE),
    }
    return mapping.get(s, Agitation.MODERATE)

def make_alternative_variant(
    *,
    req: BrewSuggestRequest,
    method: str,
    ratio_str: str,
    temperature_c: int,
    agitation_overall: Agitation,
    filter_hint: Optional[str],
    expected_dd: Optional[int],
    pours: List[PourStepIn],
    notes_text: Optional[str],
) -> BrewSuggestionVariant:
    alt_pours = [PourStepIn(**(p.model_dump() if hasattr(p, "model_dump") else dict(p))) for p in pours]
    temp = int(temperature_c)
    alt_hint = filter_hint
    drawdown = int(expected_dd) if expected_dd is not None else None

    goals_text = (getattr(req, "goals_text", "") or "").lower()
    want_clarity = (
        any(k in goals_text for k in ["floral", "florality", "clarity", "acidity", "bright", "lighter body"])
        and not any(k in goals_text for k in ["increase body", "more body", "fuller body", "syrupy"])
    )

    if want_clarity:
        temp = max(88, temp - 1)
        if drawdown is not None:
            drawdown = max(0, drawdown - 8)
        if alt_hint and "slow" in alt_hint:
            alt_hint = "fast filter → clarity, shorter contact"
        for i, p in enumerate(alt_pours):
            if i >= 2:
                p.agitation = _to_agit_enum("gentle")
        notes = (notes_text.rstrip(".") + ". Alt: cooler + gentler for extra clarity.") if notes_text else \
            "Alt: cooler + gentler for extra clarity."
        alt_ag = Agitation.GENTLE
        label = "clarity_plus"
    else:
        temp = min(96, temp + 1)
        if drawdown is not None:
            drawdown = drawdown + 10
        if alt_hint and "fast" in alt_hint:
            alt_hint = "slow filter → more contact, fuller body"
        for i, p in enumerate(alt_pours):
            if i >= 2:
                p.agitation = _to_agit_enum("high")
        notes = (notes_text.rstrip(".") + ". Alt: warmer + stronger late agitation for more body.") if notes_text else \
            "Alt: warmer + stronger late agitation for more body."
        alt_ag = _to_agit_enum("high")
        label = "body_plus"

    for p in alt_pours:
        p.kettle_temp_c = int(temp)

    early = alt_pours[1].agitation if len(alt_pours) > 1 else alt_pours[0].agitation
    late = alt_pours[2].agitation if len(alt_pours) > 2 else early
    alt_plan = build_session_plan(alt_pours, early, late)

    return BrewSuggestionVariant(
        method=method,
        ratio=ratio_str,
        total_water_g=int(getattr(req, "total_water_g", 240) or 240),
        temperature_c=int(temp),
        agitation_overall=alt_ag,
        filter_hint=alt_hint,
        expected_drawdown_s=(int(drawdown) if drawdown is not None else None),
        pours=alt_pours,
        notes=notes,
        session_plan=alt_plan,
        variant_label=label,
    )

def assemble_response(
    *,
    req: BrewSuggestRequest,
    method: str,
    ratio_str: str,
    total_water_g: int,
    temperature_c: int,
    agitation_overall: Agitation,
    filter_hint: Optional[str],
    expected_dd: Optional[int],
    pours: List[PourStepIn],
    notes_text: str,
    session_plan: dict,
    alternative: BrewSuggestionVariant,
    predicted_notes: List[PredictedNote],
) -> BrewSuggestion:
    # optional cosmetic grinder label
    grind_label_val: Optional[str] = ""
    try:
        if getattr(req, "grinder", None):
            res = setting_for_microns_grinder(req.grinder.model_dump())
            if isinstance(res, dict):
                grind_label_val = res.get("label") or ""
    except Exception:
        grind_label_val = ""

    # --- NEW: enforce schema: notes must be a string ---
    if isinstance(notes_text, list):
        # join defensively in case any upstream step accidentally returns a list
        notes_text = "; ".join(str(x) for x in notes_text if x)
    elif notes_text is None:
        notes_text = ""

    notes_list: List[str] = [notes_text] if notes_text else []

    return BrewSuggestion(
        method=method,
        ratio=ratio_str,
        total_water_g=int(total_water_g),
        temperature_c=int(temperature_c),
        agitation_overall=agitation_overall,
        filter_hint=filter_hint,
        expected_drawdown_s=(int(expected_dd) if expected_dd is not None else None),
        pours=pours,
        notes=notes_list,  # <- schema expects string
        session_plan=session_plan,
        grind_label=(grind_label_val or ""),
        alternative=alternative,
        predicted_notes=predicted_notes or [],
        toolset_id=getattr(req, "toolset_id", None),
        bean_id=getattr(req, "bean_id", None),
        note_target=getattr(req, "note_target", None),
        note_goal_downgraded=False,
        goal_explanation=None,
    )
