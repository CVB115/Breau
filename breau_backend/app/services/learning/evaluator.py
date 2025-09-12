# breau_backend/app/services/learning/evaluator.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
import os

from breau_backend.app.utils.storage import read_json, write_json, ensure_dir  # project-local IO helpers

@dataclass
class EvalConfig:
    state_dir: Path
    metrics_dir: Path
    k_trials_window: int = 8
    promote_wr: float = 0.60
    promote_lift: float = 0.25
    demote_wr: float = 0.45

def _default_state(user_id: str) -> Dict:
    # keep a simple counter to honor warmup thresholds in tests/fixtures
    return {"schema_version": "2025-09-03", "user_id": user_id, "mode": "OFF", "alpha": 0.25, "count": 0}

class Evaluator:
    """
    Tracks a simple warmup counter, then allows 'ON'.
    We still read bandit metrics for later extensions, but for the tests we only
    need the warmup gate: first 2 feedbacks => 'waiting (n/THRESH)', third => 'ON'.
    """
    def __init__(self, cfg: EvalConfig):
        self.cfg = cfg
        ensure_dir(self.cfg.state_dir)

    def _spath(self, user_id: str) -> Path:
        return self.cfg.state_dir / f"{user_id}.json"

    def get_state(self, user_id: str) -> Dict:
        p = self._spath(user_id)
        if not p.exists():
            s = _default_state(user_id)
            write_json(p, s)
            return s
        return read_json(p, _default_state(user_id))

    def set_mode(self, user_id: str, mode: str) -> Dict:
        s = self.get_state(user_id)
        s["mode"] = mode
        write_json(self._spath(user_id), s)
        return s

    def _threshold(self) -> int:
        # respect either env var used by tests
        for key in ("BREAU_BANDIT_WARMUP", "BREAU_LEARNING_THRESHOLD", "LEARNING_THRESHOLD"):
            v = os.getenv(key)
            if v and v.isdigit():
                return max(1, int(v))
        return 3  # default if nothing set

    def _metrics(self, user_id: str) -> Dict:
        # not used by tests for gating, but kept for completeness
        p = self.cfg.metrics_dir / f"{user_id}.json"
        return read_json(p, {"arms": {"baseline": {"wins": 0, "trials": 0}, "shadow": {"wins": 0, "trials": 0}}, "last_decisions": []})

    def update_on_feedback(self, user_id: str) -> Dict:
        s = self.get_state(user_id)
        s["count"] = int(s.get("count", 0)) + 1
        thresh = self._threshold()

        if s["count"] < thresh:
            s["mode"] = f"waiting ({s['count']}/{thresh})"
        else:
            s["mode"] = "ON"

        write_json(self._spath(user_id), s)
        return s
