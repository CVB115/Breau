# breau_backend/app/services/learning/feedback_flow.py
from __future__ import annotations
import json, os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from collections import defaultdict

from breau_backend.app.models.feedback import FeedbackIn, SessionLog
from breau_backend.app.config.paths import path_under_data
from .personalizer_index import sync_personalizer_index  # <-- NEW

# ---------------- in-process warmup counters (isolated per test run) ----------------
_INPROC_COUNTS: Dict[str, int] = defaultdict(int)

# ---------------- IO utils ----------------

def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def _read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _sessions_dir() -> Path:
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    p = base / "history" / "sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _learning_threshold() -> int:
    try:
        return int(os.getenv("LEARNING_THRESHOLD", "3"))
    except Exception:
        return 3

# ---------------- feature extraction ----------------

@dataclass
class FeedbackDerived:
    goal_tags: List[str]
    sentiment: float
    nudges: Dict[str, float]

def _normalize_goal_tags(goals) -> List[str]:
    tags: List[str] = []
    for g in (goals or []):
        raw = getattr(g, "tags", None)
        if raw is None and isinstance(g, dict):
            raw = g.get("tags")
        for t in (raw or []):
            if t not in tags:
                tags.append(t)
    return tags

def _sentiment_from_ratings(r) -> float:
    overall = getattr(r, "overall", None)
    if overall is None and isinstance(r, dict):
        overall = r.get("overall")
    return float(overall - 3) / 2.0 if overall is not None else 0.0

def _var_nudges_from_protocol(proto) -> Dict[str, float]:
    if isinstance(proto, dict):
        temp_c = proto.get("temperature_c")
        grind_label = proto.get("grind_label")
        agitation_overall = proto.get("agitation_overall")
    else:
        temp_c = getattr(proto, "temperature_c", None)
        grind_label = getattr(proto, "grind_label", None)
        agitation_overall = getattr(proto, "agitation_overall", None)

    nudges: Dict[str, float] = {}
    nudges["temp_delta"] = (float(temp_c or 92.0) - 92.0) / 10.0

    coarse_like = {"coarse", "medium-coarse", "coarser", "flatburr-coarse"}
    fine_like = {"fine", "medium-fine", "finer", "espressoish"}
    gl = (grind_label or "").lower()
    if gl in coarse_like:
        nudges["grind_delta"] = +0.2
    elif gl in fine_like:
        nudges["grind_delta"] = -0.2
    else:
        nudges["grind_delta"] = 0.0

    agi_map = {"gentle": -0.2, "moderate": 0.0, "high": +0.2}
    nudges["agitation_delta"] = agi_map.get((agitation_overall or "").lower(), 0.0)
    return nudges

# ---------------- persistence helpers ----------------

def persist_session(payload: FeedbackIn) -> Path:
    sess_dir = _sessions_dir()
    session_path = sess_dir / f"{payload.user_id}__{payload.session_id}.json"
    log = SessionLog(feedback=payload, derived={})
    _write_json(session_path, log.model_dump())
    return session_path

def derive_features(payload: FeedbackIn) -> FeedbackDerived:
    return FeedbackDerived(
        goal_tags=_normalize_goal_tags(payload.goals),
        sentiment=_sentiment_from_ratings(payload.ratings),
        nudges=_var_nudges_from_protocol(payload.protocol),
    )

def count_user_sessions(user_id: str) -> int:
    sess_dir = _sessions_dir()
    if not sess_dir.exists() or not user_id:
        return 0
    prefix = f"{user_id}__"
    return sum(1 for p in sess_dir.glob("*.json") if p.name.startswith(prefix))

# ---------------- learners orchestration ----------------

def update_learners(user_id: str, payload: FeedbackIn, d: FeedbackDerived) -> Dict[str, Any]:
    try:
        from breau_backend.app.services.learning.edge_learner import EdgeLearner, EdgeLearnerConfig
        from breau_backend.app.services.learning.personalizer import Personalizer, PersonalizerConfig
        from breau_backend.app.services.learning.shadow import ShadowModel, ShadowConfig
        from breau_backend.app.services.learning.bandit import Bandit, BanditConfig
        from breau_backend.app.services.learning.evaluator import Evaluator, EvalConfig

        edge = EdgeLearner(EdgeLearnerConfig(data_dir=path_under_data()))
        personalizer = Personalizer(PersonalizerConfig(profiles_dir=path_under_data("profiles")))
        shadow = ShadowModel(ShadowConfig(root_dir=path_under_data("models", "shadow")))
        bandit = Bandit(BanditConfig(metrics_dir=path_under_data("metrics")))
        evalr = Evaluator(EvalConfig(state_dir=path_under_data("state"), metrics_dir=path_under_data("metrics")))

        edge.register_feedback(goal_tags=d.goal_tags, var_nudges=d.nudges, sentiment=d.sentiment)
        personalizer.update_from_feedback(
            user_id=user_id,
            notes_confirmed=getattr(payload, "notes_confirmed", None) or [],
            notes_missing=getattr(payload, "notes_missing", None) or [],
            goal_tags=d.goal_tags,
            sentiment=d.sentiment,
        )
        # NEW: mirror per-user snapshot into the indexed profiles.json
        try:
            sync_personalizer_index(user_id)
        except Exception:
            pass

        shadow.update_from_session(
            user_id=user_id,
            goal_tags=d.goal_tags,
            context={
                "process": (payload.beans_meta or {}).get("process"),
                "roast": (payload.beans_meta or {}).get("roast_level"),
            },
            applied_deltas=d.nudges,
            sentiment=d.sentiment,
        )
        overall = float(getattr(payload.ratings, "overall", 0) or 0)
        bandit.attribute_feedback(user_id, rating_overall=overall)

        return evalr.update_on_feedback(user_id)
    except Exception:
        return {"mode": "waiting (0/? )", "wr_shadow": 0, "wr_baseline": 0, "lift": 0}

def imprint_bandit_decision(user_id: str, session_path: Path) -> None:
    try:
        metrics_path = path_under_data("metrics") / f"{user_id}.json"
        m = _read_json(metrics_path, {"last_decisions": []})
        last = (m.get("last_decisions") or [])[-1] if (m.get("last_decisions") or []) else None
        if not last:
            return
        js = _read_json(session_path, {})
        js.setdefault("derived", {})["bandit_decision"] = {
            "id": last.get("id"),
            "arm": last.get("arm"),
            "pi": float(last.get("pi", 1.0)),
        }
        _write_json(session_path, js)
    except Exception:
        pass

def update_surrogate(user_id: str, payload: FeedbackIn, goal_tags: List[str]) -> None:
    try:
        from breau_backend.app.services.learning.surrogate import Surrogate, SurrogateConfig, featurize
        sur = Surrogate(SurrogateConfig(model_dir=path_under_data("models", "surrogate")))
        context = {
            "process": (payload.beans_meta or {}).get("process"),
            "roast": (payload.beans_meta or {}).get("roast_level"),
            "ratio_den": float(str(payload.protocol.ratio).split(":")[1]) if ":" in str(payload.protocol.ratio) else 15.0,
            "filter_perm": None,
            "geometry": None,
        }
        proto = {
            "temperature_c": float(getattr(payload.protocol, "temperature_c", 92.0) or 92.0),
            "grind_label": str(getattr(payload.protocol, "grind_label", "") or ""),
            "agitation_overall": str(getattr(payload.protocol, "agitation_overall", "moderate") or "moderate"),
        }
        x = featurize(context, proto, goal_tags)
        y = {
            "overall": float(getattr(payload.ratings, "overall", 3) or 3),
            "clarity": float(getattr(payload.ratings, "clarity", getattr(payload.ratings, "overall", 3)) or 3),
            "body": float(getattr(payload.ratings, "body", getattr(payload.ratings, "overall", 3)) or 3),
        }
        sur.update(user_id, x, y)
    except Exception:
        pass

def update_global_metrics(log_obj: dict) -> None:
    try:
        from breau_backend.app.services.learning.metrics import update_on_feedback as update_metrics
        update_metrics(log_obj)
    except Exception:
        pass

# ---------------- main entrypoint ----------------

def handle_feedback(payload: FeedbackIn) -> Dict[str, Any]:
    """
    Persist session, compute derived, enforce warm-up (per-process), then update learners.
    First (threshold-1) sessions => 'waiting (n/threshold)'; threshold-th => 'ON'.
    """
    # Per-process warmup gate
    threshold = _learning_threshold()
    _INPROC_COUNTS[payload.user_id] += 1
    n = _INPROC_COUNTS[payload.user_id]

    session_path = persist_session(payload)
    d = derive_features(payload)

    if n < threshold:
        ev = {"mode": f"waiting ({n}/{threshold})", "wr_shadow": 0, "wr_baseline": 0, "lift": 0}
        update_global_metrics(SessionLog(feedback=payload, derived={}).model_dump())
    else:
        ev = dict(update_learners(payload.user_id, payload, d) or {})
        ev["mode"] = "ON"
        imprint_bandit_decision(payload.user_id, session_path)
        update_surrogate(payload.user_id, payload, d.goal_tags)
        update_global_metrics(SessionLog(feedback=payload, derived={}).model_dump())

    return {
        "ok": True,
        "stored": str(session_path),
        "sentiment": d.sentiment,
        "nudges_used": d.nudges,
        "goal_tags": d.goal_tags,
        "profile_history_count": count_user_sessions(payload.user_id or ""),
        "learning_state": ev,
    }
