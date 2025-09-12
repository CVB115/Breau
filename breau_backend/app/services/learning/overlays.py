from __future__ import annotations
from typing import Dict, List, Tuple
from pathlib import Path

# L2 sources
from .edge_learner import EdgeLearner, EdgeLearnerConfig
from .personalizer import Personalizer, PersonalizerConfig
from .practice import PracticeManager, PracticeConfig
from .cohort import Cohort, CohortConfig

# L3
from .shadow import ShadowModel, ShadowConfig

# Flags / evaluator / explain
from .flags import Flags, FlagsConfig
from .evaluator import Evaluator, EvalConfig
from .explain import compose as explain_compose, save_last as explain_save

# L5 planner
from .optimizer import Planner, PlannerConfig

# Optional curriculum
try:
    from .curriculum import Curriculum, CurriculumConfig
    _HAS_CURRICULUM = True
except Exception:
    _HAS_CURRICULUM = False

# Storage helpers used elsewhere in backend; if you don't have them, replace with local json I/O
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Paths
DATA_DIR = Path("./data")
EDGES_PATH = DATA_DIR / "priors" / "dynamic_edges.json"
PROFILES_DIR = DATA_DIR / "profiles"
PRACTICE_DIR = DATA_DIR / "practice"
SHADOW_DIR = DATA_DIR / "models" / "shadow"
BANDIT_DIR = DATA_DIR / "metrics"
STATE_DIR = DATA_DIR / "state"
SUR_DIR = DATA_DIR / "models" / "surrogate"
CUR_DIR = DATA_DIR / "curriculum"
COHORT_DIR = DATA_DIR / "cohorts"
SESSIONS_DIR = DATA_DIR / "history" / "sessions"
CLIPS_PATH = BANDIT_DIR / "clips.json"

# Singletons
_edge = EdgeLearner(EdgeLearnerConfig(data_dir=DATA_DIR, edges_path=EDGES_PATH))
_personalizer = Personalizer(PersonalizerConfig(profiles_dir=PROFILES_DIR))
_pm = PracticeManager(PracticeConfig(practice_dir=PRACTICE_DIR))
_shadow = ShadowModel(ShadowConfig(root_dir=SHADOW_DIR))
_flags = Flags(FlagsConfig(state_dir=STATE_DIR))
_eval = Evaluator(EvalConfig(state_dir=STATE_DIR, metrics_dir=BANDIT_DIR))
_planner = Planner(PlannerConfig(model_dir=SUR_DIR))
_cohort = Cohort(CohortConfig(root_dir=COHORT_DIR))
_curriculum = Curriculum(CurriculumConfig(root_dir=CUR_DIR)) if _HAS_CURRICULUM else None


def _cap(v: float, lim: float = 0.3) -> float:
    return -lim if v < -lim else (lim if v > lim else v)


def _context_defaults(context: Dict) -> Dict:
    return {
        "process": context.get("process"),
        "roast": context.get("roast"),
        "ratio_den": context.get("ratio_den"),
        "temp_bucket": context.get("temp_bucket"),
        "filter_perm": context.get("filter_perm"),
        "geometry": context.get("geometry"),
        "priors_used": bool(context.get("priors_used", False)),
        "hint": context.get("hint"),
    }


def _log_clip_event(clipped: bool):
    ensure_dir(BANDIT_DIR)
    js = read_json(CLIPS_PATH, {"total": 0, "clipped": 0})
    js["total"] = int(js.get("total", 0)) + 1
    if clipped:
        js["clipped"] = int(js.get("clipped", 0)) + 1
    write_json(CLIPS_PATH, js)


def _sum_overlays(*srcs: Dict[str, float]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for m in srcs:
        for k, v in (m or {}).items():
            out[k] = out.get(k, 0.0) + float(v)
    return out


def _trait_budget_cap(overlay: Dict[str, float]) -> Dict[str, float]:
    if not overlay:
        return overlay
    temp = float(overlay.get("temp_delta", 0.0)) / 0.3
    grind = float(overlay.get("grind_delta", 0.0)) / 0.25
    agi = float(overlay.get("agitation_delta", 0.0)) / 0.25

    floral_promote = max(0.0, (-temp)) + max(0.0, (+grind)) + max(0.0, (-agi))
    body_promote   = max(0.0, (+temp)) + max(0.0, (-grind)) + max(0.0, (+agi))

    def _scale(d: Dict[str, float], promote: float, limit: float = 0.30) -> Dict[str, float]:
        if promote <= limit or promote <= 1e-6:
            return d
        sc = limit / promote
        out = dict(d)
        for k in ("temp_delta", "grind_delta", "agitation_delta"):
            if k in out:
                out[k] = out[k] * sc
        return out

    overlay = _scale(overlay, floral_promote, 0.30)
    overlay = _scale(overlay, body_promote,   0.30)
    for k in list(overlay.keys()):
        overlay[k] = _cap(overlay[k], 0.3)
    return overlay


def _compute_l2(user_id: str, goal_tags: List[str], context: Dict) -> Tuple[Dict[str, float], Dict[str, float]]:
    merged: Dict[str, float] = {}
    trace_parts = {"prior": 0.0, "history": 0.0, "edge": 0.0}

    # 0) Cohort seed for cold-start
    try:
        import glob
        pats = str(SESSIONS_DIR / f"{user_id}__*.json")
        if _flags.is_on(user_id, "use_cohort_seed") and len(glob.glob(pats)) < 3:
            seed = _cohort.seed_overlay(context, goal_tags) or {}
            merged = _sum_overlays(merged, seed)
            trace_parts["prior"] += sum(abs(v) for v in seed.values())
    except Exception:
        pass

    # 1) global learned edges
    if _flags.is_on(user_id, "use_learned_edges"):
        e = _edge.overlays_for_goals(goal_tags) or {}
        merged = _sum_overlays(merged, e)
        trace_parts["edge"] += sum(abs(v) for v in e.values())

    # 2) per-user personalisation
    if _flags.is_on(user_id, "use_user_personalisation"):
        p = _personalizer.overlays_for_user(user_id, goal_tags) or {}
        merged = _sum_overlays(merged, p)
        trace_parts["history"] += sum(abs(v) for v in p.values())

    # 3) practice / curriculum (optional)
    micro_overlay: Dict[str, float] = {}
    if _flags.is_on(user_id, "use_curriculum") and _HAS_CURRICULUM and _curriculum and hasattr(_curriculum, "peek_due"):
        try:
            mo = _curriculum.peek_due(user_id) or {}
            micro_overlay = mo.get("overlay", {}) if isinstance(mo, dict) else {}
        except Exception:
            micro_overlay = {}
    if not micro_overlay and _flags.is_on(user_id, "use_practice"):
        pm = _pm.micro_adjustment(user_id)
        micro_overlay = (pm or {}).get("overlay", {}) if isinstance(pm, dict) else {}
    if micro_overlay:
        merged = _sum_overlays(merged, micro_overlay)
        trace_parts["prior"] += sum(abs(v) for v in micro_overlay.values())

    # early cap
    for k in list(merged.keys()):
        merged[k] = _cap(merged[k], 0.3)
    return merged, trace_parts


# --- compatibility wrapper: support both 4‑arg and 3‑arg call patterns ---
def compute_overlays(*args, **kwargs):
    """
    Supports two call patterns:
      1) compute_overlays(user_id, flags_override, context, goal_tags)  # new
      2) compute_overlays(user_id, goal_tags, context)                  # legacy tests
    """
    # new-style explicit kwargs
    if {"user_id", "flags_override", "context", "goal_tags"} <= set(kwargs.keys()):
        user_id = kwargs["user_id"]
        flags_override = kwargs["flags_override"]
        context = kwargs["context"]
        goal_tags = kwargs["goal_tags"]
        return _compute_overlays_impl(user_id, flags_override, context, goal_tags)

    # positional handling
    if len(args) == 4:
        user_id, flags_override, context, goal_tags = args
        return _compute_overlays_impl(user_id, flags_override or {}, context or {}, goal_tags or [])
    elif len(args) == 3:
        user_id, goal_tags, context = args
        return _compute_overlays_impl(user_id, {}, context or {}, goal_tags or [])
    else:
        raise TypeError("compute_overlays expects (user_id, flags, context, goal_tags) or (user_id, goal_tags, context)")


def _compute_overlays_impl(user_id: str, flags_override: Dict, context: Dict, goal_tags: List[str]) -> Dict[str, float]:
    # Merge flags (store + per-request overrides)
    req_flags = _flags_global_dict()
    req_flags.update(_flags_user_dict(user_id))
    req_flags.update(flags_override or {})

    base_l2, trace_parts = _compute_l2(user_id, goal_tags, context)

    # L3 diagnostic overlay
    shadow = _shadow.overlays_for_user(user_id, goal_tags) or {}
    if shadow:
        base_l2 = _sum_overlays(base_l2, shadow)
        trace_parts["history"] += sum(abs(v) for v in shadow.values())

    # L5 planner (optional)
    if req_flags.get("use_model_planner", False):
        plan = _planner.plan({**context, "user_id": user_id}, goal_tags) or {}
        base_l2 = _sum_overlays(base_l2, plan)

    # Trait-budget cap + telemetry + explain
    pre_cap = dict(base_l2)
    final_overlay = _trait_budget_cap(base_l2)
    clipped = any(abs(final_overlay.get(k, 0.0) - pre_cap.get(k, 0.0)) > 1e-9 for k in set(pre_cap) | set(final_overlay))
    _log_clip_event(clipped)

    why = explain_compose(trace_parts, _context_defaults(context))
    explain_save(user_id, why, trace_parts, arm="compose")

    return {
    "temp_delta": final_overlay.get("temp_delta", 0.0),
    "grind_delta": final_overlay.get("grind_delta", 0.0),
    "agitation_delta": final_overlay.get("agitation_delta", 0.0),
    }

def _flags_global_dict() -> Dict[str, bool]:
    # tolerate FakeFlags or dict-like replacements in tests
    try:
        return dict(_flags.get_global())
    except Exception:
        try:
            return dict(_flags)  # mapping-like
        except Exception:
            return dict(getattr(_flags, "flags", {}) or {})

def _flags_user_dict(user_id: str) -> Dict[str, bool]:
    try:
        return dict(_flags.get_user(user_id))
    except Exception:
        # tests may not provide per-user flags
        return {}
