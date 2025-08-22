from fastapi import APIRouter
from ..schemas import (
    BrewSuggestRequest, BrewSuggestion, PourStepIn,
    Agitation, PourStyle, PredictedNote
)
from ..services.nlp.anp_extractor import parse_goals

router = APIRouter()

def _parse_ratio(r: str) -> int:
    try:
        _, rhs = r.split(":")
        return int(rhs)
    except Exception:
        return 15

def _method_from_brewer(brewer) -> str:
    if not brewer:
        return "pour-over"
    gt = brewer.geometry_type.value  # enum → "conical"/"flat"/...
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
        return 180  # 3:00
    p = filter_.permeability.value  # enum → "fast"/"medium"/"slow"
    if p == "fast":
        return 165  # 2:45
    if p == "slow":
        return 240  # 4:00
    return 195  # 3:15

@router.post("/suggest", response_model=BrewSuggestion)
def suggest(req: BrewSuggestRequest) -> BrewSuggestion:
    # ----- goals input: direct or parsed from text -----
    goals = []
    if req.goals:
        for g in req.goals:
            goals.append(f"{g.direction.lower()} {g.trait.value.lower()}")
    elif req.text:
        goals = parse_goals(req.text)

    # ----- base recipe -----
    ratio_str = req.ratio or "1:15"
    R = _parse_ratio(ratio_str)
    dose = req.dose_g or 15
    total_water = dose * R

    temperature_c = 92
    grind_label = "medium-fine"
    overall_agitation = Agitation.GENTLE
    style = _default_style(req.brewer)
    expected_drawdown = _baseline_expected_drawdown(req.filter)
    filter_hint = None

    # ----- adjust from filter -----
    if req.filter:
        p = req.filter.permeability.value
        if p == "fast":
            filter_hint = "fast filter → clarity, shorter contact"
        elif p == "slow":
            filter_hint = "slow filter → more contact, fuller body"
        else:
            filter_hint = "medium filter"

    # ----- goal-driven nudges -----
    lg = [g.lower() for g in goals]

    if any("increase florality" in g for g in lg):
        temperature_c = max(90, temperature_c - 1)
        overall_agitation = Agitation.GENTLE
        style = PourStyle.SPIRAL
        expected_drawdown = max(150, expected_drawdown - 15)

    if any("increase body" in g for g in lg):
        ratio_str = "1:13"; R = 13; total_water = dose * R
        temperature_c = min(96, temperature_c + 2)
        overall_agitation = Agitation.MODERATE
        expected_drawdown = min(270, expected_drawdown + 20)

    if any("reduce body" in g for g in lg):
        ratio_str = "1:16"; R = 16; total_water = dose * R
        temperature_c = max(88, temperature_c - 1)
        overall_agitation = Agitation.GENTLE
        expected_drawdown = max(150, expected_drawdown - 15)

    if any("reduce acidity" in g for g in lg):
        temperature_c = min(96, temperature_c + 1)
        overall_agitation = Agitation.MODERATE
        expected_drawdown = min(270, expected_drawdown + 10)

    if any("increase sweetness" in g for g in lg):
        ratio_str = "1:14"; R = 14; total_water = dose * R
        temperature_c = 93

    if any("reduce bitterness" in g for g in lg):
        temperature_c = max(90, temperature_c - 2)
        overall_agitation = Agitation.GENTLE
        expected_drawdown = max(150, expected_drawdown - 10)

    # ----- pours (water milestones first) -----
    bloom = req.bloom_water_g or 30
    remain = max(0, total_water - bloom)
    step = max(1, remain // 3)  # default: 3 post-bloom pours
    pours = [
        PourStepIn(water_g=bloom, kettle_temp_c=temperature_c,
                   pour_style=style, agitation=Agitation.GENTLE, note="Bloom"),
        PourStepIn(water_g=step,  kettle_temp_c=temperature_c,
                   pour_style=style, agitation=overall_agitation),
        PourStepIn(water_g=step,  kettle_temp_c=temperature_c,
                   pour_style=style, agitation=overall_agitation),
        PourStepIn(water_g=remain - 2*step, kettle_temp_c=temperature_c,
                   pour_style=style, agitation=overall_agitation),
    ]

    # ----- predicted notes (placeholder) -----
    predicted = []
    if any("florality" in g for g in lg):
        predicted.append(PredictedNote(label="floral clarity", confidence=0.6,
                                       rationale="gentle agitation + shorter contact"))
    if any("increase body" in g for g in lg):
        predicted.append(PredictedNote(label="syrupy body", confidence=0.6,
                                       rationale="higher temp + tighter ratio"))
    if not predicted:
        predicted.append(PredictedNote(label="balanced cup", confidence=0.5))

    return BrewSuggestion(
        method=_method_from_brewer(req.brewer),
        ratio=ratio_str,
        total_water_g=total_water,
        temperature_c=temperature_c,
        grind_label=grind_label,
        agitation_overall=overall_agitation,
        filter_hint=filter_hint,
        expected_drawdown_s=expected_drawdown,
        pours=pours,
        predicted_notes=predicted,
        notes="Heuristic MVP. Will refine with geometry, water, and note traits."
    )
