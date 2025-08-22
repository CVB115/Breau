from fastapi import APIRouter
from typing import List, Tuple, Optional

from ..schemas import (
    BrewSuggestRequest, BrewSuggestion, PourStepIn,
    Agitation, PourStyle, PredictedNote
)
from ..services.nlp.anp_extractor import parse_goals
from ..services.nlp.semantic import any_matches  # NEW: MiniLM semantic assist

router = APIRouter()

# ---------- ratio & formatting helpers ----------
def _parse_ratio_den(r: str) -> float:
    """Parse '1:15' -> 15.0; default 15.0 on error."""
    try:
        _, rhs = r.split(":")
        return float(rhs)
    except Exception:
        return 15.0

def _format_ratio_den(n: float) -> str:
    """Format denominator (supports .5) back to '1:15' or '1:14.5'."""
    n = round(n, 1)
    return f"1:{int(n)}" if float(n).is_integer() else f"1:{n}"

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

# ---------- brewer/helpers (your originals) ----------
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

# ---------- semantic goal helpers (NEW) ----------
GOAL_CANDIDATES = [
    "increase florality","reduce florality",
    "increase body","reduce body",
    "increase sweetness","reduce sweetness",
    "increase acidity","reduce acidity",
    "reduce bitterness","increase bitterness",
]

def _canonical(phrase: str) -> Optional[str]:
    """Return the canonical phrase if supported, else None."""
    return phrase if phrase in GOAL_CANDIDATES else None

def _merge_goals_from_text(text: str) -> List[Tuple[str, float]]:
    """
    From free text, return list of (canonical_phrase, weight).
    Rules (strong) + MiniLM semantic (softer), dedup by taking max weight.
    """
    rules = parse_goals(text)  # -> list[str]
    sem = any_matches(text, GOAL_CANDIDATES, threshold=0.48)  # -> [(phrase, score)]

    merged: dict[str, float] = {}

    # Rule hits get strong base weight
    for g in rules:
        c = _canonical(g)
        if not c:
            continue
        merged[c] = max(merged.get(c, 0.0), 0.80)

    # Semantic hits: similarity mapped to [0.35, 0.70]; keep top few
    for phrase, score in sem[:3]:
        c = _canonical(phrase)
        if not c:
            continue
        w = 0.35 + 0.35 * max(0.0, min(1.0, (score - 0.48) / (0.85 - 0.48)))
        merged[c] = max(merged.get(c, 0.0), w)

    # Return as sorted list (hi→lo) for determinism
    return sorted(merged.items(), key=lambda kv: kv[1], reverse=True)

# ---------- agitation helpers (NEW) ----------
_AGI_ORDER = [Agitation.NONE, Agitation.GENTLE, Agitation.MODERATE, Agitation.HIGH]

def _agi_index(a: Agitation) -> int:
    try:
        return _AGI_ORDER.index(a)
    except ValueError:
        return 1  # default GENTLE

def _reduce_late_agitation(pours: List[PourStepIn]) -> None:
    if not pours:
        return
    last = pours[-1]
    idx = _agi_index(last.agitation)
    if idx > 0:
        last.agitation = _AGI_ORDER[idx - 1]

def _increase_mid_agitation(pours: List[PourStepIn]) -> None:
    if not pours:
        return
    mid_i = len(pours) // 2
    idx = _agi_index(pours[mid_i].agitation)
    if idx < len(_AGI_ORDER) - 1:
        pours[mid_i].agitation = _AGI_ORDER[idx + 1]

@router.post("/suggest", response_model=BrewSuggestion)
def suggest(req: BrewSuggestRequest) -> BrewSuggestion:
    # ----- goals input: explicit, or parsed from text (+semantic assist) -----
    goal_phrases_weighted: List[Tuple[str, float]] = []
    if req.goals:
        # explicit list -> strong weight 0.9
        for g in req.goals:
            phrase = f"{g.direction.lower()} {g.trait.value.lower()}"
            c = _canonical(phrase)
            if c:
                goal_phrases_weighted.append((c, 0.9))
    elif req.text:
        goal_phrases_weighted = _merge_goals_from_text(req.text)

    # Keep a lowercase list of phrases (for predicted notes section)
    goal_phrases = [p for p, _ in goal_phrases_weighted]
    lg = [p.lower() for p in goal_phrases]

    # ----- base recipe (your existing baseline) -----
    ratio_str = req.ratio or "1:15"
    den = _parse_ratio_den(ratio_str)
    dose = float(req.dose_g or 15)
    total_water = int(round(dose * den))

    # Baseline knobs
    temperature_c = 92
    grind_label = "medium-fine"
    overall_agitation = Agitation.GENTLE
    style = _default_style(req.brewer)
    expected_drawdown = _baseline_expected_drawdown(req.filter)
    filter_hint = None

    # ----- adjust from filter (your original hints) -----
    if req.filter:
        p = req.filter.permeability.value
        if p == "fast":
            filter_hint = "fast filter → clarity, shorter contact"
        elif p == "slow":
            filter_hint = "slow filter → more contact, fuller body"
        else:
            filter_hint = "medium filter"

    # ----- goal-driven bounded nudges (NEW, gentle & additive) -----
    # Aggregate tiny deltas scaled by weights; clamp after.
    temp_delta = 0.0
    den_delta = 0.0       # + makes lighter (e.g., 15 → 15.5), − makes stronger
    dd_delta = 0.0
    prefer_style: Optional[PourStyle] = None
    want_reduce_late = False
    want_bump_mid = False

    for phrase, w in goal_phrases_weighted:
        if phrase == "increase florality":
            temp_delta += -1.0 * w
            dd_delta += -5.0 * w
            prefer_style = prefer_style or PourStyle.SPIRAL
        elif phrase == "reduce florality":
            temp_delta += +0.5 * w
            dd_delta += +5.0 * w
            prefer_style = prefer_style or _default_style(req.brewer)

        elif phrase == "increase body":
            temp_delta += +1.0 * w
            den_delta += -0.5 * w
            dd_delta += +10.0 * w
            overall_agitation = Agitation.MODERATE  # small bias
        elif phrase == "reduce body":
            temp_delta += -0.5 * w
            den_delta += +0.5 * w
            dd_delta += -10.0 * w
            overall_agitation = Agitation.GENTLE

        elif phrase == "increase sweetness":
            temp_delta += +0.5 * w
            dd_delta += +5.0 * w
            want_bump_mid = True
        elif phrase == "reduce sweetness":
            temp_delta += -0.5 * w
            dd_delta += -5.0 * w

        elif phrase == "increase acidity":
            temp_delta += -0.75 * w
            dd_delta += -5.0 * w
        elif phrase == "reduce acidity":
            temp_delta += +0.5 * w
            dd_delta += +5.0 * w

        elif phrase == "reduce bitterness":
            temp_delta += -1.0 * w
            den_delta += +0.2 * w
            dd_delta += -10.0 * w
            want_reduce_late = True
        elif phrase == "increase bitterness":
            temp_delta += +0.5 * w
            den_delta += -0.2 * w
            dd_delta += +5.0 * w

    # Apply tiny, clamped adjustments
    base_t = float(temperature_c)
    temperature_c = int(round(_clamp(base_t + temp_delta, base_t - 2.0, base_t + 2.0)))

    den_new = _clamp(den + den_delta, 12.0, 18.0)
    ratio_str = _format_ratio_den(den_new)
    total_water = int(round(dose * den_new))

    base_dd = float(expected_drawdown)
    expected_drawdown = int(round(_clamp(base_dd + dd_delta, base_dd - 20.0, base_dd + 20.0)))

    if prefer_style:
        style = prefer_style

    # ----- pours (same structure as your original, now using adjusted knobs) -----
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

    # Post-build agitation micro-tweaks
    if want_reduce_late:
        _reduce_late_agitation(pours)
    if want_bump_mid:
        _increase_mid_agitation(pours)

    # ----- predicted notes (placeholder; uses recognized goals) -----
    predicted: List[PredictedNote] = []
    if any("florality" in g for g in lg):
        predicted.append(PredictedNote(label="floral clarity", confidence=0.6,
                                       rationale="gentle agitation + shorter contact"))
    if any("increase body" in g for g in lg):
        predicted.append(PredictedNote(label="syrupy body", confidence=0.6,
                                       rationale="slightly tighter ratio + warmer temp"))
    if any("increase sweetness" in g for g in lg):
        predicted.append(PredictedNote(label="sweetness", confidence=0.55,
                                       rationale="mid-phase agitation + modest temp lift"))
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
        notes="Geometry & filter set the baseline; text goals add small, bounded tweaks."
    )
