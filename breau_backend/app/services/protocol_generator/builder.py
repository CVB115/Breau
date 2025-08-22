# breau_backend/app/protocol_generator/builder.py
from __future__ import annotations
from typing import Optional, List

from breau_backend.app.schemas import (
    BrewSuggestRequest, BrewSuggestion, PourStepIn,
    PredictedNote, Agitation, PourStyle
)
from .goal_matcher import match_goals
from .parser import (
    parse_ratio_den, format_ratio_den, bounded_nudges, build_description
)

# from .note_loader import probable_notes_for_goals, load_note_profiles

def _method_from_brewer(brewer) -> str:
    if not brewer:
        return "pour-over"
    gt = brewer.geometry_type.value  # "conical"/"flat"/"hybrid"/"immersion"/"basket"
    return {
        "conical": "v60-style",
        "flat": "flatbed",
        "hybrid": "hybrid",
        "immersion": "clever-style",
        "basket": "basket",
    }.get(gt, "pour-over")

def _default_style(brewer) -> PourStyle:
    if not brewer:
        return PourStyle.SPIRAL
    return PourStyle.SEGMENTED if brewer.geometry_type.value == "flat" else PourStyle.SPIRAL

def _baseline_expected_drawdown(filter_) -> int:
    if not filter_:
        return 180
    p = filter_.permeability.value  # "fast" | "medium" | "slow"
    if p == "fast":
        return 165
    if p == "slow":
        return 240
    return 195

def _filter_hint(filter_) -> Optional[str]:
    if not filter_:
        return None
    p = filter_.permeability.value
    if p == "fast":
        return "fast filter → clarity, shorter contact"
    if p == "slow":
        return "slow filter → more contact, fuller body"
    return "medium filter"

def build_suggestion(req: BrewSuggestRequest) -> BrewSuggestion:
    # 1) goals
    explicit = None
    if req.goals:
        explicit = [(g.direction.lower(), g.trait.value.lower()) for g in req.goals]
    weighted = match_goals(explicit_goals=explicit, free_text=(req.text or ""))
    goals = [g for g, _ in weighted]

    # 2) baseline
    ratio_str = req.ratio or "1:15"
    den = parse_ratio_den(ratio_str)
    dose = float(req.dose_g or 15)
    total_water = int(round(dose * den))

    temperature_c = 92.0
    grind_label = "medium-fine"
    overall_agitation = Agitation.GENTLE
    style = _default_style(req.brewer)
    expected_drawdown = _baseline_expected_drawdown(req.filter)
    filter_hint = _filter_hint(req.filter)

    # 3) pours (bloom + 3 pours)
    bloom = req.bloom_water_g or 30
    remain = max(0, total_water - bloom)
    step = max(1, remain // 3)
    pours_py = [
        {"water_g": bloom, "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": overall_agitation.name, "note": "Bloom"},
        {"water_g": step,  "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": overall_agitation.name},
        {"water_g": step,  "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": overall_agitation.name},
        {"water_g": remain - 2*step, "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": overall_agitation.name},
    ]

    # 4) bounded nudges
    temperature_c, den, expected_drawdown, pours_py, _, _ = bounded_nudges(
        goals, temperature_c, den, expected_drawdown, pours_py
    )
    ratio_str = format_ratio_den(den)
    total_water = int(round(dose * den))

    def _to_agitation(val):
        # Accept Agitation enum OR string (case-insensitive)
        if isinstance(val, Agitation):
            return val
        if isinstance(val, str):
            return Agitation[val.upper()]
        return Agitation.GENTLE  # fallback

    def _to_style(val):
        # Accept PourStyle enum OR string (case-insensitive)
        if isinstance(val, PourStyle):
            return val
        if isinstance(val, str):
            return PourStyle[val.upper()]
        return PourStyle.SPIRAL  # fallback

    # 5) Convert pours back to schema enums/objects (uses the normalizers)
    pours = [
        PourStepIn(
            water_g=p["water_g"],
            kettle_temp_c=p["kettle_temp_c"],
            pour_style=_to_style(p.get("pour_style", "SPIRAL")),
            agitation=_to_agitation(p.get("agitation", "GENTLE")),
            note=p.get("note")
        )
        for p in pours_py
    ]

    # 6) predicted notes (simple mapping for now)
    _ = load_note_profiles()  # placeholder for future smarter scoring
    predicted = [
        PredictedNote(label=label, confidence=conf, rationale=why)
        for (label, conf, why) in probable_notes_for_goals(goals)
    ]

    # 7) description
    agitation_summary = "agitation kept gentle overall"
    description = build_description(goals, int(round(temperature_c)), ratio_str, agitation_summary)

    return BrewSuggestion(
        method=_method_from_brewer(req.brewer),
        ratio=ratio_str,
        total_water_g=total_water,
        temperature_c=int(round(temperature_c)),
        grind_label=grind_label,
        agitation_overall=overall_agitation,
        filter_hint=filter_hint,
        expected_drawdown_s=int(expected_drawdown),
        pours=pours,
        predicted_notes=predicted,
        notes=description,
    )
