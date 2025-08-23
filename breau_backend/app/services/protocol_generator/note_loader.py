# app/protocol_generator/note_loader.py
from typing import Dict, List, Tuple
from breau_backend.app.flavour.store import get_ontology

# ---- 1) Canonical goal -> tag targets (temporary; replace with embedding scorer later)
_GOAL_TAGS: Dict[str, List[str]] = {
    "increase florality": ["category:floral","volatility:high","stability:fragile","density:thin",
                           "contact_time_affinity:short","temp_affinity:lower","agitation_affinity:low"],
    "reduce florality":   ["density:rich","contact_time_affinity:long"],
    "increase body":      ["density:rich","contact_time_affinity:long","heat_retention_affinity:high","temp_affinity:high"],
    "reduce body":        ["density:thin","contact_time_affinity:short","agitation_affinity:low"],
    "increase sweetness": ["sweetness_type:honeyed","texture:silky"],
    "reduce sweetness":   ["density:thin","texture:crisp"],
    "increase acidity":   ["acidity_family:citric","density:thin","contact_time_affinity:short","temp_affinity:lower"],
    "reduce acidity":     ["density:rich","contact_time_affinity:long"],
    "reduce bitterness":  ["density:thin","temp_affinity:lower","agitation_affinity:low"],
    "increase bitterness":["density:rich","temp_affinity:high"]
}

def goals_to_tags(goals: List[str]) -> List[str]:
    """
    Flattens canonical goal phrases into a deduplicated list of facet:value tags.
    Example goals: ["increase florality","reduce body"]
    """
    out: List[str] = []
    for g in goals or []:
        for t in _GOAL_TAGS.get(g, []):
            if t not in out:
                out.append(t)
    # fallback so scoring still works
    return out or ["density:thin","contact_time_affinity:short"]

# ---- 2) Candidate selection using ontology + context nudges (simple tag-overlap scorer)

def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    return (len(sa & sb) / len(sa | sb)) if sa and sb else 0.0

def _context_bonus(note_tags: List[str], coffee_profile: Dict) -> float:
    """
    Adds small positive nudges for tags that are favored by context rules
    matching the given coffee_profile (e.g., process/origin).
    """
    onto = get_ontology()
    bonus = 0.0
    for rule in onto.context:
        # All keys in 'when' must match
        if all(coffee_profile.get(k) == v for k, v in rule.when.items()):
            for t, delta in rule.tag_weight_deltas.items():
                if t in note_tags:
                    bonus += float(delta)
    return bonus


# ---- 3) NEW: Edge-based transformations (using note_edges.json)

def _clip01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x

def _blend_factor(profile: Dict) -> float:
    """
    Continuous 0..1 factor from brew conditions:
    - contact_time: short=0, neutral=0.5, long=1
    - temperature: maps 92→96°C to 0→1 linearly
    Final factor f = 0.6*contact + 0.4*temp  (tunable)
    """
    contact_time = profile.get("contact_time")
    if contact_time in ("short", "neutral", "long"):
        contact_score = {"short": 0.0, "neutral": 0.5, "long": 1.0}[contact_time]
    else:
        contact_score = 0.0

    temp_c = profile.get("temperature_c", 92)
    temp_score = _clip01((float(temp_c) - 92.0) / 4.0)  # 92→96 => 0→1

    return _clip01(0.8 * contact_score + 0.2 * temp_score)


def _apply_edges(
    candidates: List[Tuple[str, float, Dict]],
    brew_profile: Dict
) -> List[Tuple[str, float, Dict]]:
    """
    Adjusts candidate scores using transform edges with CONTINUOUS blending.
    - Keeps source note present (never hard-deletes).
    - Boosts target note proportional to (edge.confidence * f(conditions)).
    - Softly reduces source note by a tunable fraction of that boost.
    """
    onto = get_ontology()
    # name -> {score: float, dbg: dict}
    adjusted = {name: {"score": max(score, 0.0), "dbg": (dbg or {}).copy()} for name, score, dbg in candidates}

    f = _blend_factor(brew_profile)  # 0..1
    if f <= 0:
        # nothing to do if no transforming conditions present
        return [(n, v["score"], v["dbg"]) for n, v in adjusted.items()]

    for edge in onto.edges:
        if edge.type != "transform_tendency":
            continue
        src_name = edge.source
        tgt_name = edge.target
        if src_name not in adjusted:
            continue

        src = adjusted[src_name]
        tgt = adjusted.get(tgt_name, {"score": 0.0, "dbg": {"base": 0, "salience": 0, "context_bonus": 0}})
        # how strongly the rule itself is defined (e.g., 0.6)
        conf = float(getattr(edge, "confidence", 0.5))

        # boost towards target
        boost = src["score"] * conf * f
        tgt["score"] += boost

        # soften the source a bit; k controls how much the source recedes at max effect
        k = 0.7
        src["score"] *= (1.0 - conf * f * k)

        # annotate rationale/debug
        tgt_dbg = tgt.setdefault("dbg", {})
        tgt_dbg["edge_from"] = src_name
        tgt_dbg["edge_f"] = round(f, 2)
        tgt_dbg["edge_conf"] = round(conf, 2)

        adjusted[tgt_name] = tgt
        adjusted[src_name] = src

    return [(name, data["score"], data["dbg"]) for name, data in adjusted.items()]

# ---- 4) Main candidate selector (with edges applied)

def select_candidate_notes(
    goal_tags: List[str],
    coffee_profile: Dict,
    top_k: int = 5
) -> List[Tuple[str, float, Dict]]:
    """
    Returns a list of (note_name, score, debug) sorted high→low.
    debug fields: {"base": float, "salience": float, "context_bonus": float, ...}
    """
    onto = get_ontology()
    out = []
    for name, note in onto.notes.items():
        base = _jaccard(goal_tags, note.tags)
        sal  = 0.4 + 0.6 * float(note.salience)  # scale 0.4..1.0
        ctx  = _context_bonus(note.tags, coffee_profile)
        score = base * sal + ctx
        out.append((name, score, {"base": round(base,3), "salience": round(sal,3), "context_bonus": round(ctx,3)}))
    out.sort(key=lambda x: x[1], reverse=True)

    # NEW: apply edge transformations before final ranking
    out = _apply_edges(out, coffee_profile)

    # Re-sort after transformations
    out.sort(key=lambda x: x[1], reverse=True)
    return out[:top_k]


# ---- 5) Small helpers

def get_note_tags_map(note_names: List[str]) -> Dict[str, List[str]]:
    onto = get_ontology()
    return {n: onto.notes[n].tags for n in note_names if n in onto.notes}

def ontology_info() -> Dict:
    onto = get_ontology()
    return {
        "notes": list(onto.notes.keys()),
        "edges": len(onto.edges),
        "context_rules": len(onto.context),
        "facets": list(onto.taxonomy.facets.keys())
    }
