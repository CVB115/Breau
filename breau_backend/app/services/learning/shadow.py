# breau_backend/app/services/learning/shadow.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# L3 "shadow model": tracks per-user overlay effects learned from history
# (not directly used for live decisions, but evaluated alongside bandit).
# Stores rolling aggregates and exposes overlays_for_user() for diagnostics.

@dataclass
class ShadowConfig:
    root_dir: Path
    alpha: float = 0.2
    cap:   float = 0.3

def _clip(v: float, c: float) -> float:
    return -c if v < -c else (c if v > c else v)

VAR_KEYS = ("temp_delta", "grind_delta", "agitation_delta")

class ShadowModel:
    def __init__(self, cfg: ShadowConfig):
        self.cfg = cfg
        ensure_dir(self.cfg.root_dir)

    def _path(self, user_id: str) -> Path:
        return self.cfg.root_dir / f"{user_id}.json"

    def update_from_session(self, user_id: str, goal_tags: List[str], context: Dict, applied_deltas: Dict[str, float], sentiment: float) -> None:
        # Purpose:
        # EMA-learn how deltas correlated with positive sentiment for this user.
        p = self._path(user_id)
        js = read_json(p, {"schema_version": "2025-09-03", "user_id": user_id, "ema": {k:0.0 for k in VAR_KEYS}})
        a = float(self.cfg.alpha)
        ema = js.get("ema", {})
        for k in VAR_KEYS:
            delta = float(applied_deltas.get(k, 0.0)) * float(sentiment if sentiment != 0 else 0.1)
            ema[k] = _clip((1 - a) * float(ema.get(k, 0.0)) + a * delta, self.cfg.cap)
        js["ema"] = ema
        write_json(p, js)

    def overlays_for_user(self, user_id: str, goal_tags: List[str]) -> Dict[str, float]:
        # Purpose:
        # Return shadow EMA as a suggested overlay (for analysis/compare).
        js = read_json(self._path(user_id), None)
        if not js:
            return {}
        out = {k: float(js.get("ema", {}).get(k, 0.0)) for k in VAR_KEYS}
        # small defensive cap
        for k in list(out.keys()):
            out[k] = _clip(out[k], self.cfg.cap)
        return out
