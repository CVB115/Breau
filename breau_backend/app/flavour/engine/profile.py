# breau_backend/app/flavour/engines/profile.py
from __future__ import annotations
from typing import Dict, Any
import time

# Purpose:
# Thin wrapper around the services layer “data stores” to read/write **user flavour
# profiles** and append observations, so the engines don’t touch storage details.  :contentReference[oaicite:9]{index=9}

# Use services layer so all data lives under ./data
from breau_backend.app.services.data_stores import (
    get_profile as _ds_get_profile,
    upsert_profile as _ds_upsert_profile,
    append_session as _ds_append_session,  # or append_feedback if you prefer
)

# Purpose:
# Baseline profile fields and defaults for new users.
def default_profile() -> Dict[str, Any]:
    return {
        "strength_comfort": {"ratio_den_min": 15.0, "ratio_den_max": 16.5},
        "slurry_offset_c": 3.0,
        "agitation_bias": {"early": 0.0, "late": 0.0},
        "note_bias": {},
        "drawdown_memory": {},  # e.g., "conical_fast": {"ema_s": ..., "var_s2": ...}
        "training_state": {
            "mode": "off", "rows_seen": 0, "alpha_index": 0, "consecutive_good": 0,
            "model_path": "models/delta_predictor.pkl", "last_eval": {}
        },
        "setup_phase": True,
    }

# Purpose:
# Read profile from store or initialize-and-save a default.
def load_profile(user_id: str) -> Dict[str, Any]:
    try:
        return _ds_get_profile(user_id)["data"]
    except Exception:
        prof = default_profile()
        _ds_upsert_profile(user_id, prof)
        return prof

# Purpose:
# Persist profile back to the store.
def save_profile(user_id: str, profile: Dict[str, Any]) -> None:
    _ds_upsert_profile(user_id, profile)

# Purpose:
# Append a raw observation (lightweight session row) to the user’s history.
def append_observation(user_id: str, row: Dict[str, Any]) -> None:
    payload = dict(row or {})
    payload.setdefault("user_id", user_id)
    payload.setdefault("_ts", time.time())
    payload.setdefault("_kind", "observation")
    _ds_append_session(payload)

# Purpose:
# Update EMA of drawdown timing/behavior for a named context key.
def update_drawdown_ema(profile: Dict[str, Any], key: str, drawdown_s: float, alpha: float = 0.3) -> None:
    dm = profile.setdefault("drawdown_memory", {}).setdefault(key, {"ema_s": drawdown_s, "var_s2": 0.0})
    prev = dm["ema_s"]
    dm["ema_s"] = prev + alpha * (drawdown_s - prev)
