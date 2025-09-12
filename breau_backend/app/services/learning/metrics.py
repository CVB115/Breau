# breau_backend/app/services/learning/metrics.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional
from statistics import mean
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# Track per-user and global learning/quality metrics from feedback payloads:
# - alignment (predicted_notes ∩ confirmed_notes)
# - rolling windows for learning gain (firstN vs lastN)
# - coarse calibration hits from free-text ("bitter"/"sour")
# Data lives under ./data/metrics/{users/*.json, global.json}

DATA_DIR = Path("./data")
USR_DIR = DATA_DIR / "metrics" / "users"
GLB_PATH = DATA_DIR / "metrics" / "global.json"
ensure_dir(USR_DIR.parent); ensure_dir(USR_DIR)

def _default_user():
    # Purpose:
    # New user metrics skeleton with small windows (N=5).
    return {
        "schema_version": "2025-09-03",
        "samples": 0,
        "alignment_hits": 0,   # notes_confirmed ∩ predicted_notes != ∅
        "overall_ratings": [], # keep last 50
        "firstN": [],          # first N for baseline (N=5)
        "lastN": [],           # last N (N=5 rolling)
        "calib_bitter": 0,
        "calib_sour": 0,
        "calib_total": 0,
        "N": 5
    }

def _default_global():
    # Purpose:
    # Snapshot of global aggregates averaged across users with data.
    return {"schema_version":"2025-09-03","users":0,"alignment_rate":0.0,"learning_gain":0.0,"calibration_hit":0.0}

def _clip_list(xs: List[float], k: int) -> List[float]:
    # Purpose:
    # Keep only last k entries (rolling window).
    return xs[-k:] if len(xs) > k else xs

def update_on_feedback(session_log: Dict) -> Dict:
    # Purpose:
    # Update per-user metrics from one session_log (SessionLog model_dump).
    # Also recompute global aggregates (simple mean over users).
    fb = session_log.get("feedback", {})
    user = fb.get("user_id")
    if not user: return {"ok": False}

    # Predicteds may be present from request or recomputed—use payload if available
    predicted = []
    pred = fb.get("prediction")
    if pred:
        predicted = list(pred.get("predicted_notes") or [])

    confirmed = list(fb.get("notes_confirmed") or [])
    overall = fb.get("ratings", {}).get("overall", 3)

    # calibration signals (very rough heuristic from free-text)
    ft = (fb.get("free_text") or "").lower()
    calib_bitter = int("too bitter" in ft or "bitter" in ft)
    calib_sour   = int("too sour" in ft or "sour" in ft)

    # load user metrics
    path = USR_DIR / f"{user}.json"
    js = read_json(path, _default_user())
    N = int(js.get("N", 5))

    # alignment (hit if any predicted was confirmed)
    align_hit = 1 if any(n for n in confirmed if n in predicted) else 0
    js["alignment_hits"] = int(js.get("alignment_hits", 0)) + align_hit

    # ratings (keep last 50)
    ratings = list(js.get("overall_ratings", [])) + [overall]
    js["overall_ratings"] = _clip_list(ratings, 50)

    # firstN/lastN windows for learning gain
    if len(js["firstN"]) < N:
        js["firstN"].append(overall)
    js["lastN"] = _clip_list(list(js.get("lastN", [])) + [overall], N)

    # calibration aggregates
    js["calib_bitter"] = int(js.get("calib_bitter", 0)) + calib_bitter
    js["calib_sour"]   = int(js.get("calib_sour", 0)) + calib_sour
    js["calib_total"]  = int(js.get("calib_total", 0)) + 1

    js["samples"] = int(js.get("samples", 0)) + 1
    write_json(path, js)

    # update global aggregates (simple mean over users with data)
    users = list(USR_DIR.glob("*.json"))
    if users:
        arates = []
        gains = []
        chits = []
        for u in users:
            uj = read_json(u, _default_user())
            s = max(1, uj.get("samples", 0))
            arate = uj.get("alignment_hits", 0) / s
            firstN = uj.get("firstN", [])
            lastN = uj.get("lastN", [])
            if firstN and lastN:
                gains.append(mean(lastN) - mean(firstN))
            ch_total = max(1, uj.get("calib_total", 0))
            ch = (uj.get("calib_bitter", 0) + uj.get("calib_sour", 0)) / ch_total
            arates.append(arate); chits.append(ch)
        glb = {
            "schema_version":"2025-09-03",
            "users": len(users),
            "alignment_rate": float(mean(arates)) if arates else 0.0,
            "learning_gain": float(mean(gains)) if gains else 0.0,
            "calibration_hit": float(mean(chits)) if chits else 0.0,
        }
        write_json(GLB_PATH, glb)

    return {"ok": True}
