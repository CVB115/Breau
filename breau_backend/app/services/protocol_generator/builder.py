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
from .note_loader import (
    goals_to_tags, select_candidate_notes, get_note_tags_map
)

# ---------------- Utility mappers ----------------

def _method_from_brewer(brewer) -> str:
    """Map brewer geometry -> human-friendly brew method label."""
    if not brewer:
        return "pour-over"
    gt = brewer.geometry_type.value
    return {
        "conical": "v60-style",
        "flat": "flatbed",
        "hybrid": "hybrid",
        "immersion": "clever-style",
        "basket": "basket",
    }.get(gt, "pour-over")


def _default_style(brewer) -> PourStyle:
    """Choose default pour style based on brewer geometry."""
    if not brewer:
        return PourStyle.SPIRAL
    return PourStyle.SEGMENTED if brewer.geometry_type.value == "flat" else PourStyle.SPIRAL


def _baseline_expected_drawdown(filter_) -> int:
    """Estimate baseline drawdown time (seconds) from filter permeability."""
    if not filter_:
        return 180
    p = filter_.permeability.value
    if p == "fast":
        return 165
    if p == "slow":
        return 240
    return 195


def _filter_hint(filter_) -> Optional[str]:
    """Add an explanatory hint about filter impact on cup profile."""
    if not filter_:
        return None
    p = filter_.permeability.value
    if p == "fast":
        return "fast filter → clarity, shorter contact"
    if p == "slow":
        return "slow filter → more contact, fuller body"
    return "medium filter"


def _heat_retention_label(brewer, filter_) -> str:
    """
    Heuristic for heat retention: heavier brewers + thicker/unbleached filters retain heat better.
    Returns: 'low' | 'medium' | 'high'
    """
    score = 0
    if brewer and getattr(brewer, "thermal_mass", None) in ("high", "cast_metal", "heavy"):
        score += 1
    if filter_:
        try:
            if filter_.thickness.value == "thick":
                score += 1
        except Exception:
            pass
        try:
            if filter_.material.value in ("paper_unbleached", "cloth"):
                score += 1
        except Exception:
            pass
    return "high" if score >= 2 else ("medium" if score == 1 else "low")


# ---------------- Core builder ----------------

def build_suggestion(req: BrewSuggestRequest) -> BrewSuggestion:
    """Main pipeline: goals → tags → recipe nudges → candidate notes → final suggestion."""

    # 1) Extract goals (explicit list + free text)
    explicit = None
    if req.goals:
        explicit = [(g.direction.lower(), g.trait.value.lower()) for g in req.goals]
    weighted = match_goals(explicit_goals=explicit, free_text=(req.text or ""))
    goals = [g for g, _ in weighted]

    # Convert canonical goals -> tag list
    goal_tags = goals_to_tags(goals)

    # Collect relevant bean profile (origin, process, etc.)
    coffee_profile = {}
    if req.bean:
        if getattr(req.bean, "origin", None):
            coffee_profile["origin_region"] = req.bean.origin
        if getattr(req.bean, "process", None):
            coffee_profile["process"] = req.bean.process

    # 2) Baseline recipe setup
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

    # 3) Construct initial pours (bloom + 3)
    bloom = req.bloom_water_g or 30
    remain = max(0, total_water - bloom)
    step = max(1, remain // 3)
    pours_py = [
        {"water_g": bloom, "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": overall_agitation.name, "note": "Bloom"},
        {"water_g": step,  "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": overall_agitation.name},
        {"water_g": step,  "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": overall_agitation.name},
        {"water_g": remain - 2*step, "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": overall_agitation.name},
    ]

    # 4) Apply bounded nudges from goals (temp, ratio, agitation, drawdown)
    temperature_c, den, expected_drawdown, pours_py, _, _ = bounded_nudges(
        goals, temperature_c, den, expected_drawdown, pours_py
    )

    # --- Brew context passed to note-edge engine (for transformations) ---
    coffee_profile["temperature_c"] = int(round(temperature_c))
    coffee_profile["contact_time"] = (
        "long" if expected_drawdown >= 210 else "short" if expected_drawdown <= 170 else "neutral"
    )
    coffee_profile["heat_retention"] = _heat_retention_label(req.brewer, req.filter)
    # ---------------------------------------------------------------------

    ratio_str = format_ratio_den(den)
    total_water = int(round(dose * den))

    # Normalizers for enums
    def _to_agitation(val):
        if isinstance(val, Agitation):
            return val
        if isinstance(val, str):
            return Agitation[val.upper()]
        return Agitation.GENTLE

    def _to_style(val):
        if isinstance(val, PourStyle):
            return val
        if isinstance(val, str):
            return PourStyle[val.upper()]
        return PourStyle.SPIRAL

    # Convert pours back to schema objects
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

    # 5) Candidate note selection (ontology-backed, includes edge transforms)
    # ask for top_k=5 internally so you can see boosted notes, but return only top-3
    cands = select_candidate_notes(goal_tags, coffee_profile, top_k=5)
    total = sum(max(s, 0.0) for _, s, _ in cands) or 1.0

    predicted = []
    for (name, score, dbg) in cands[:3]:
        rationale_parts = []
        if "edge_from" in dbg:
            rationale_parts.append(f"transformed from {dbg['edge_from']}")
        rationale_parts.append(
            f"overlap={dbg.get('base')} · sal={dbg.get('salience')} · ctx={dbg.get('context_bonus')}"
        )
        rationale = " | ".join(rationale_parts)

        predicted.append(
            PredictedNote(
                label=name,
                confidence=round(max(score, 0.0) / total, 3),
                rationale=rationale
            )
        )

    # 6) Description text
    agitation_summary = "agitation kept gentle overall"
    description = build_description(goals, int(round(temperature_c)), ratio_str, agitation_summary)

    # 7) Return full structured suggestion
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
