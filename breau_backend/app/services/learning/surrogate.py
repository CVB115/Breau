# breau_backend/app/services/learning/surrogate.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# L5 surrogate: super-light regression-like learner that maps
# (context, protocol deltas, goal tags) → component scores (overall/clarity/body).
# It supports:
#   - update(user, x, y) with tiny per-user additive memories
#   - featurize(context, proto, goal_tags) to build x
#   - suggest_from_surrogate() to produce small direction hints for overlays

@dataclass
class SurrogateConfig:
    model_dir: Path
    alpha: float = 0.2
    cap: float = 0.3

def _clip(v: float, c: float) -> float:
    return -c if v < -c else (c if v > c else v)

def featurize(context: Dict, proto: Dict, goal_tags: List[str]) -> Dict[str, float]:
    # Purpose: simplified feature map used by both update() and planner.
    x: Dict[str, float] = {}
    x["temp_delta"] = float(proto.get("temperature_c", 92.0) - 92.0) / 10.0
    gl = (proto.get("grind_label", "") or "").lower()
    if "coarse" in gl:   x["grind_delta"] = +0.2
    elif "fine" in gl:   x["grind_delta"] = -0.2
    else:                x["grind_delta"] = 0.0
    ag = (proto.get("agitation_overall", "moderate") or "").lower()
    x["agitation_delta"] = {"gentle": -0.2, "moderate": 0.0, "high": +0.2}.get(ag, 0.0)

    # goal hints as binary toggles (kept tiny)
    g = [t.lower() for t in (goal_tags or [])]
    x["hint_clarity"] = 1.0 if any(k in g for k in ["clarity","floral","citrus_acidity"]) else 0.0
    x["hint_body"]    = 1.0 if any(k in g for k in ["body","syrupy_body"]) else 0.0
    return x

class Surrogate:
    def __init__(self, cfg: SurrogateConfig):
        self.cfg = cfg
        ensure_dir(self.cfg.model_dir)

    def _path(self, user_id: str) -> Path:
        return self.cfg.model_dir / f"{user_id}.json"

    def update(self, user_id: str, x: Dict[str, float], y: Dict[str, float]) -> None:
        # Purpose:
        # Per-user tiny additive model: y_hat = w·x; we EMA-update w by (y - w·x) signs.
        p = self._path(user_id)
        js = read_json(p, {"schema_version": "2025-09-03", "w": {}})
        w = js.get("w", {})
        a = float(self.cfg.alpha)
        for k, v in x.items():
            # naive directional update: if higher overall desired and x_k positive correlates → increase
            grad = 0.0
            target = float(y.get("overall", 3.0)) - 3.0  # centered target
            grad += target * float(v)
            w[k] = _clip((1 - a) * float(w.get(k, 0.0)) + a * grad, self.cfg.cap)
        js["w"] = w
        write_json(p, js)

def suggest_from_surrogate(sur: Surrogate, context: Dict, goal_tags: List[str]) -> Dict[str, float]:
    # Purpose:
    # Project w onto a synthetic “proto” to produce small suggested deltas.
    # Note: we don’t require current proto here; we suggest direction by goals.
    dummy_proto = {
        "temperature_c": 92.0,
        "grind_label": "medium",
        "agitation_overall": "moderate",
    }
    x = featurize(context, dummy_proto, goal_tags)
    # Use weights as-is; final caps happen upstream.
    p = sur._path(context.get("user_id","_global"))
    js = read_json(p, {"w": {}})
    w = js.get("w", {})
    out = {k: float(w.get(k, 0.0)) for k in ("temp_delta","grind_delta","agitation_delta")}
    return out
