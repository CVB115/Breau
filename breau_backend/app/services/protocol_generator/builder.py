# breau_backend/app/protocol_generator/builder.py
from __future__ import annotations
from typing import Optional, List

from breau_backend.app.schemas import (
    BrewSuggestRequest, BrewSuggestion, PourStepIn,
    PredictedNote, Agitation, PourStyle
)
from .goal_matcher import match_goals
from .parser import (
    parse_ratio_den, format_ratio_den, build_description
)
from .note_loader import (
    goals_to_tags, select_candidate_notes, get_note_tags_map,get_policy, get_nudger, load_user_profile,
    slurry_offset_c, rank_notes_from_vec
)

from breau_backend.app.flavour.explanation import SuggestionTrace

# --- Robust enum mapping: works even if you don't have 'ROBUST' ---
# We derive low/medium/high from whatever members exist, in declared order.
_agit_members = list(Agitation)  # e.g. ['GENTLE','MODERATE','AGGRESSIVE'] or similar

# Low and Medium
_AGIT_LOW  = getattr(Agitation, "GENTLE",   _agit_members[0])
_AGIT_MED  = getattr(Agitation, "MODERATE", _agit_members[min(1, len(_agit_members)-1)])

# High: prefer ROBUST, else AGGRESSIVE, else VIGOROUS, else just use the last member
_AGIT_HIGH = getattr(
    Agitation, "ROBUST",
    getattr(Agitation, "AGGRESSIVE",
        getattr(Agitation, "VIGOROUS", _agit_members[-1])
    )
)

_AGIT_ENUM_TO_STR = {
    _AGIT_LOW:  "low",
    _AGIT_MED:  "medium",
    _AGIT_HIGH: "high",
}

_STR_TO_AGIT_ENUM = {
    # semantic levels
    "low": _AGIT_LOW,
    "medium": _AGIT_MED,
    "high": _AGIT_HIGH,
    # common enum-name fallbacks (accept lowercase)
    "gentle": _AGIT_LOW,
    "moderate": _AGIT_MED,
    "robust": _AGIT_HIGH,
    "aggressive": _AGIT_HIGH,
    "vigorous": _AGIT_HIGH,
}
# Overall agitation helper (choose the stronger of the two phases)
_LEVEL_INDEX = {_AGIT_LOW: 0, _AGIT_MED: 1, _AGIT_HIGH: 2}
def _overall_from_phases(early: Agitation, late: Agitation) -> Agitation:
    return early if _LEVEL_INDEX[early] >= _LEVEL_INDEX[late] else late


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

#---------------- Session plan builder (Helper) ----------------

def _build_session_plan(pours: list, ag_early: Agitation, ag_late: Agitation) -> dict:
    """
    pours: list[PourStepIn] in order
    returns: dict matching SessionPlan (so we avoid import cycles)
    """
    steps = []
    # First step (Bloom) if present
    if pours:
        p0 = pours[0]
        steps.append({
            "id": "bloom",
            "instruction": f"Bloom {p0.water_g} g, swirl gently.",
            "gate": "pour_until",
            "target_water_g": p0.water_g,
            "voice_prompt": "Bloom thirty grams, then swirl gently.",
            "note": "Bloom"
        })
    # Remaining steps pour to cumulative targets
    cum = pours[0].water_g if pours else 0
    for i, p in enumerate(pours[1:], start=1):
        cum += p.water_g
        # Early phase for first non-bloom step; late phase afterwards
        phase = "early" if i == 1 else "late"
        ag = ag_early if i == 1 else ag_late
        steps.append({
            "id": f"step{i}",
            "instruction": f"Pour to {cum} g, {phase} {ag.name.lower()} agitation.",
            "gate": "pour_until",
            "target_water_g": cum
        })
    return {
        "mode_default": "beginner",
        "steps": steps
    }


# ---------------- Core builder ----------------

def build_suggestion(req: BrewSuggestRequest) -> BrewSuggestion:
    """Main pipeline: goals → tags → recipe nudges → candidate notes → final suggestion."""

    # 1) Extract goals (explicit list + free text)
    explicit = None
    if req.goals:
        explicit = [(g.direction.lower(), g.trait.value.lower()) for g in req.goals]

    # NEW: match_goals now returns a dict with goals + preferences + avoids
    mg = match_goals(explicit_goals=explicit, free_text=(req.text or ""))

    # Canonical goals that drive recipe nudges and base tag mapping
    goals = [g for g, _ in mg["goals"]]

    # NEW: user “what kind” and “what not” — e.g., acidity_family:citric / :acetic
    include_tags = [t for t, _ in mg.get("preferences", [])]   # prefer these facets
    exclude_tags = [t for t, _ in mg.get("avoids", [])]        # penalize these facets/notes

    # Convert canonical goals → ontology tags, then tilt selection toward preferences
    goal_tags = goals_to_tags(goals) + include_tags

    # Collect relevant bean profile (origin, process, etc.)
    coffee_profile = {}
    if req.bean:
        if getattr(req.bean, "origin", None):
            coffee_profile["origin_region"] = req.bean.origin
        if getattr(req.bean, "process", None):
            coffee_profile["process"] = req.bean.process

    # 2) Baseline recipe setup (rule defaults)
    ratio_str = req.ratio or "1:15"
    den = parse_ratio_den(ratio_str)
    dose = float(req.dose_g or 15)
    total_water = int(round(dose * den))

    style = _default_style(req.brewer)
    expected_drawdown = _baseline_expected_drawdown(req.filter)
    filter_hint = _filter_hint(req.filter)

    # User profile & policy-backed slurry targeting
    profile = load_user_profile(getattr(req, "user_id", "local"))
    offset = slurry_offset_c(profile)

    # Build base_vars for Nudger
    base_vars = {
        "ratio_den": den,
        "temperature_c": 92.0,  # UI-facing kettle target will be computed from slurry
        "slurry_c": 92.0 - offset,
        "agitation": "medium",            # parity default
        "agitation_early": "medium",
        "agitation_late": "medium",
        "method": _method_from_brewer(req.brewer)
    }

    # Context for rule constraints
    context = {
        "brewer": {"geometry_type": (req.brewer.geometry_type.value if req.brewer else "conical")},
        "filter": {"permeability": (req.filter.permeability.value if req.filter else "medium")},
        "grinder": {"burr_type": getattr(getattr(req, "grinder", None), "burr_type", None)}
    }

    # Build a simple goal vector from matched goals (increase/decrease)
    goal_vec = {}
    for g, w in mg["goals"]:
        txt = (g or "").lower()
        weight = w if isinstance(w, (int, float)) else 1.0
        if txt.startswith(("increase", "more", "up")):
            trait = txt.split()[-1]
            goal_vec[trait] = goal_vec.get(trait, 0.0) + weight
        elif txt.startswith(("reduce", "less", "decrease", "down")):
            trait = txt.split()[-1]
            goal_vec[trait] = goal_vec.get(trait, 0.0) - weight

    # 3) Apply Nudger deltas (rules with caps/constraints)
    nudger = get_nudger()
    rule_delta, _reasons = nudger.propose(goal_vec, base_vars, context, profile)
    final_vars, clips = nudger.apply_and_clip(base_vars, rule_delta, context)

    # Map slurry back to kettle for display/steps
    slurry_target_c = float(final_vars["slurry_c"])
    kettle_target_c = slurry_target_c + offset

    # Use kettle temp for pours/UX, slurry is our internal target
    temperature_c = kettle_target_c

    # 4) Construct pours using early/late agitation (3 steps + bloom)
    bloom = req.bloom_water_g or 30
    remain = max(0, int(round(dose * final_vars["ratio_den"])) - bloom)
    step = max(1, remain // 3)

    # Agitation enums from final_vars strings
    ag_early_enum = _STR_TO_AGIT_ENUM[final_vars["agitation_early"]]
    ag_late_enum  = _STR_TO_AGIT_ENUM[final_vars["agitation_late"]]
    overall_agitation = _overall_from_phases(ag_early_enum, ag_late_enum)

    pours_py = [
        {"water_g": bloom,           "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": ag_early_enum.name, "note": "Bloom"},
        {"water_g": step,            "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": ag_early_enum.name},
        {"water_g": step,            "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": ag_late_enum.name},
        {"water_g": remain - 2*step, "kettle_temp_c": int(round(temperature_c)), "pour_style": style.name, "agitation": ag_late_enum.name},
    ]

    # Convert pours_py to schema objects
    def _to_agitation(val):
        if isinstance(val, Agitation):
            return val
        s = str(val).lower()
        # support both "low/medium/high" and "GENTLE/MODERATE/ROBUST"
        if s in _STR_TO_AGIT_ENUM:
            return _STR_TO_AGIT_ENUM[s]
        try:
            return Agitation[s.upper()]
        except Exception:
            return Agitation.MODERATE

    def _to_style(val):
        if isinstance(val, PourStyle):
            return val
        try:
            return PourStyle[str(val).upper()]
        except Exception:
            return PourStyle.SPIRAL

    pours = [
        PourStepIn(
            water_g=p["water_g"],
            kettle_temp_c=p["kettle_temp_c"],
            pour_style=_to_style(p.get("pour_style", "SPIRAL")),
            agitation=_to_agitation(p.get("agitation", "MODERATE")),
            note=p.get("note")
        ) for p in pours_py
    ]

    # Feed slurry temp (not kettle) into note engine context
    coffee_profile["temperature_c"] = int(round(slurry_target_c))

    # 5) Candidate notes (ontology-backed)
    cands = select_candidate_notes(
        goal_tags,
        coffee_profile,
        top_k=5,
        include_tags=include_tags,
        exclude_tags=exclude_tags
    )
    if cands:
        min_s = min(s for _, s, _ in cands)
        if min_s < 0:
            cands = [(n, s - min_s + 1e-6, dbg) for (n, s, dbg) in cands]
        total = sum(s for _, s, _ in cands) or 1.0
    else:
        cands, total = [], 1.0  # safety, should not happen with your selector

    predicted = []
    for (name, score, dbg) in cands[:3]:
        rationale_parts = []
        if "edge_from" in dbg:
            rationale_parts.append(f"transformed from {dbg['edge_from']}")
        rationale_parts.append(f"overlap={dbg.get('base')} · sal={dbg.get('salience')} · ctx={dbg.get('context_bonus')}")
        predicted.append(
            PredictedNote(
                label=name,
                confidence=round(max(score, 0.0) / total, 3),
                rationale=" | ".join(rationale_parts)
            )
        )

    # Sync ratio string & total water with the FINAL ratio
    ratio_str = format_ratio_den(final_vars["ratio_den"])
    total_water = int(round(dose * final_vars["ratio_den"]))

    # Best-effort grind label
    grind_label = None
    if getattr(req, "grinder", None):
        grind_label = getattr(req.grinder, "label", None)
        if not grind_label:
            bt = getattr(req.grinder, "burr_type", None)
            grind_label = (str(bt).lower() if bt else None)

    # 6) Description text (use kettle temp for user-facing text)
    agitation_summary = f"early {ag_early_enum.name.lower()}, late {ag_late_enum.name.lower()}"
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
        session_plan = _build_session_plan(pours, ag_early_enum, ag_late_enum)
        
    )
