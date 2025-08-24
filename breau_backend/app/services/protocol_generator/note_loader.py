# app/protocol_generator/note_loader.py
from typing import List, Tuple, Dict, Optional
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
    top_k: int = 5,
    include_tags: Optional[List[str]] = None,  # preferences (e.g., "acidity_family:citric")
    exclude_tags: Optional[List[str]] = None   # avoids (e.g., "acidity_family:acetic", "note:vinegar")
) -> List[Tuple[str, float, Dict]]:
    """
    Score = base_overlap * salience + context_bonus
            + ALPHA * (# preference tag matches)
            - BETA  * (# avoid tag matches)
    Returns top_k [(note_name, score, dbg)] sorted high→low.
    """
    include_tags = include_tags or []
    exclude_tags = exclude_tags or []

    onto = get_ontology()
    out: List[Tuple[str, float, Dict]] = []

    inc_set = set(include_tags)
    exc_set = set(exclude_tags)

    # gentle nudges so ontology remains primary signal
    ALPHA = 0.05  # preference bonus per match
    BETA  = 0.08  # avoid penalty per match

    for name, note in onto.notes.items():
        base = _jaccard(goal_tags, note.tags)                           # 0..1
        sal  = 0.4 + 0.6 * float(getattr(note, "salience", 0.6))        # 0.4..1.0
        ctx  = _context_bonus(note.tags, coffee_profile)                 # −/+

        inc_hits = len(inc_set & set(note.tags))
        exc_hits = len(exc_set & set(note.tags))
        if f"note:{name}" in exc_set:
            exc_hits += 1

        score = base * sal + ctx + (ALPHA * inc_hits) - (BETA * exc_hits)
        out.append((
            name,
            score,
            {
                "base": round(base, 3),
                "salience": round(sal, 3),
                "context_bonus": round(ctx, 3),
                "inc_hits": inc_hits,
                "exc_hits": exc_hits
            }
        ))

    out.sort(key=lambda x: x[1], reverse=True)

    # Edge transforms (continuous blend). If your _apply_edges supports goal_tags, pass them.
    try:
        out = _apply_edges(out, coffee_profile, goal_tags=goal_tags)
    except TypeError:
        out = _apply_edges(out, coffee_profile)

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
# ===== 6) Policy / Nudger / Profile wrappers (centralized here) =====
from pathlib import Path
import json
from breau_backend.app.flavour.nudger import Nudger
from breau_backend.app.flavour.profile import load_profile as _load_profile

_POLICY = None
_NUDGER = None

def _root_app_dir() -> Path:
    # note_loader.py lives in app/protocol_generator/, so parents[1] is app/
    return Path(__file__).resolve().parents[1]

def get_policy() -> dict:
    global _POLICY
    if _POLICY is None:
        cfg = _root_app_dir() / "config" / "decision_policy.json"
        _POLICY = json.loads(cfg.read_text())
    return _POLICY

def get_nudger() -> Nudger:
    global _NUDGER
    if _NUDGER is None:
        _NUDGER = Nudger(get_policy())
    return _NUDGER

def load_user_profile(user_id: str) -> dict:
    return _load_profile(user_id)

def slurry_offset_c(profile: dict) -> float:
    policy = get_policy()
    return float(profile.get("slurry_offset_c",
                             policy["defaults"]["slurry_offset_c"]))

def canonical_goal_strings_from_vec(goal_vec: dict[str, float]) -> list[str]:
    # turn {florality:+0.8, body:-0.5} -> ["increase florality","reduce body"]
    out = []
    for trait, w in goal_vec.items():
        if abs(w) < 1e-6:
            continue
        out.append(("increase " if w > 0 else "reduce ") + trait)
    return out

def rank_notes_from_vec(goal_vec: dict, coffee_profile: dict, k: int = 5):
    canonical_goals = canonical_goal_strings_from_vec(goal_vec)
    gtags = goals_to_tags(canonical_goals)
    return select_candidate_notes(gtags, coffee_profile, top_k=k)

from pathlib import Path
import json

_POLICY = None

def _root_app_dir() -> Path:
    # note_loader.py lives in app/services/protocol_generator/
    # parents[0]=protocol_generator, [1]=services, [2]=app, [3]=breau_backend
    return Path(__file__).resolve().parents[2]  # -> .../app

def get_policy():
    global _POLICY
    if _POLICY is not None:
        return _POLICY

    candidates = [
        _root_app_dir() / "config" / "decision_policy.json",                          # app/config/decision_policy.json (intended)
        Path(__file__).resolve().parents[3] / "app" / "config" / "decision_policy.json",  # fallback if tree changes
    ]

    for cfg in candidates:
        if cfg.exists():
            _POLICY = json.loads(cfg.read_text())
            return _POLICY

    # If we got here, the file isn't where we expect.
    looked = " | ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"decision_policy.json not found. Looked at: {looked}")
