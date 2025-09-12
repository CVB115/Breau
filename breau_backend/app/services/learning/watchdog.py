# breau_backend/app/services/learning/watchdog.py
from __future__ import annotations
from pathlib import Path
from typing import Dict
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# Guardrails / sanity checks over learned artifacts. We record lightweight
# health flags for dashboards (e.g., when any overlay source keeps getting
# clipped, or when metrics files go missing).

DATA_DIR = Path("./data")
STATE_DIR = DATA_DIR / "state"
WD_PATH = STATE_DIR / "watchdog.json"

def _default_state() -> Dict:
    return {"schema_version":"2025-09-03","alerts":{},"seen":0}

def note_clip_rate(total: int, clipped: int) -> Dict:
    # Purpose: convert clip telemetry counts into a health status bundle.
    rate = (clipped / total) if total > 0 else 0.0
    status = "ok" if rate < 0.2 else ("warn" if rate < 0.4 else "alert")
    return {"rate": round(rate,3), "status": status, "total": total, "clipped": clipped}

def refresh() -> Dict:
    # Purpose:
    # recompute a single watchdog snapshot; called opportunistically by API.
    ensure_dir(STATE_DIR)
    js = read_json(WD_PATH, _default_state())
    # read overlay clip telemetry
    clips = read_json(DATA_DIR / "metrics" / "clips.json", {"total":0, "clipped":0})
    js["alerts"]["overlays_clip"] = note_clip_rate(int(clips.get("total",0)), int(clips.get("clipped",0)))
    js["seen"] = int(js.get("seen",0)) + 1
    write_json(WD_PATH, js)
    return js
