# breau_backend/app/services/learning/optimizer.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# L5 planner: uses the surrogate model’s feature featurization to suggest gentle
# overlays consistent with user goals/context. This module mostly wraps the
# Surrogate’s featurize() map to produce human-meaningful deltas.

DATA_DIR = Path("./data")

@dataclass
class PlannerConfig:
    model_dir: Path

def _cap(v: float, lim: float = 0.3) -> float:
    # Purpose: hard trust-region cap for small recipe nudges.
    return -lim if v < -lim else (lim if v > lim else v)

class Planner:
    # Purpose:
    # Request-time planner that asks the Surrogate for directional guidance
    # (via feature influence) and returns clipped protocol deltas.
    def __init__(self, cfg: PlannerConfig):
        self.cfg = cfg
        ensure_dir(self.cfg.model_dir)

    def plan(self, context: Dict, goal_tags: List[str]) -> Dict[str, float]:
        # Purpose:
        # Query the (trained) surrogate to get small deltas aligned to goals.
        try:
            from .surrogate import Surrogate, SurrogateConfig, suggest_from_surrogate
            sur = Surrogate(SurrogateConfig(model_dir=self.cfg.model_dir))
            # Surrogate suggestion returns coarse deltas; we cap them.
            raw = suggest_from_surrogate(sur, context, goal_tags) or {}
            out = {k: _cap(float(v), 0.3) for k, v in raw.items()}
            return out
        except Exception:
            return {}
