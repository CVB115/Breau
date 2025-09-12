# breau_backend/app/services/learning/progress.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# Small helper to expose user progress snapshots for UI:
# - sessions completed (from metrics/users/<id>.json)
# - rough learning gain (lastN - firstN mean)
# - streaks / last seen (optional, if present)

DATA_DIR = Path("./data")
USR_METRICS = DATA_DIR / "metrics" / "users"

def user_progress(user_id: str) -> Dict:
    # Purpose:
    # Return a minimal, UI-friendly progress snapshot for a user.
    ensure_dir(USR_METRICS)
    p = USR_METRICS / f"{user_id}.json"
    js = read_json(p, {"samples": 0, "firstN": [], "lastN": [], "last_seen_iso": None})
    from statistics import mean
    firstN, lastN = js.get("firstN", []), js.get("lastN", [])
    gain = (mean(lastN) - mean(firstN)) if (firstN and lastN) else 0.0
    return {
        "user_id": user_id,
        "sessions": int(js.get("samples", 0)),
        "learning_gain": float(gain),
        "last_seen_iso": js.get("last_seen_iso"),
    }
