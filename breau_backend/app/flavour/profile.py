from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]  # breau_backend/
USER_OVERLAYS = ROOT / "app" / "flavour" / "data" / "overlays" / "user"
OBS_DIR = ROOT / "app" / "flavour" / "data" / "observations"
USER_OVERLAYS.mkdir(parents=True, exist_ok=True)
OBS_DIR.mkdir(parents=True, exist_ok=True)

def _profile_path(user_id: str) -> Path:
    return USER_OVERLAYS / f"{user_id}.json"

def default_profile() -> Dict[str, Any]:
    return {
        "strength_comfort": {"ratio_den_min": 15.0, "ratio_den_max": 16.5},
        "slurry_offset_c": 3.0,
        "agitation_bias": {"early": 0.0, "late": 0.0},
        "note_bias": {},
        "drawdown_memory": {},  # key like "conical_fast": {"ema_s": 0.0, "var_s2": 0.0}
        "training_state": {"mode": "off", "rows_seen": 0, "alpha_index": 0, "consecutive_good": 0,
                           "model_path": "models/delta_predictor.pkl", "last_eval": {}},
        "setup_phase": True
    }

def load_profile(user_id: str) -> Dict[str, Any]:
    p = _profile_path(user_id)
    if not p.exists():
        prof = default_profile()
        p.write_text(json.dumps(prof, indent=2))
        return prof
    return json.loads(p.read_text())

def save_profile(user_id: str, profile: Dict[str, Any]) -> None:
    _profile_path(user_id).write_text(json.dumps(profile, indent=2))

def append_observation(user_id: str, row: Dict[str, Any]) -> None:
    f = OBS_DIR / f"user_{user_id}.jsonl"
    with f.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")

def update_drawdown_ema(profile: Dict[str, Any], key: str, drawdown_s: float, alpha: float = 0.3) -> None:
    dm = profile.setdefault("drawdown_memory", {}).setdefault(key, {"ema_s": drawdown_s, "var_s2": 0.0})
    prev = dm["ema_s"]
    dm["ema_s"] = prev + alpha * (drawdown_s - prev)
