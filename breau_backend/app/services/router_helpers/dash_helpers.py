# breau_backend/app/services/router_helpers/dash_helpers.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import json, os

def _read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def overview() -> Dict[str, Any]:
    """Global dashboard snapshot from DATA_DIR/metrics/global.json."""
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    return _read_json(base / "metrics" / "global.json",
                      {"users": 0, "alignment_rate": 0.0, "learning_gain": 0.0, "calibration_hit": 0.0}) or {}

def progress() -> Dict[str, Any]:
    """Lightweight progress summary from DATA_DIR/metrics/users/* (rolled up)."""
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    usr_dir = base / "metrics" / "users"
    out: Dict[str, Any] = {"users": 0, "samples": 0}
    if not usr_dir.exists():
        return out
    u = 0
    s = 0
    for p in usr_dir.glob("*.json"):
        u += 1
        js = _read_json(p, {}) or {}
        s += int(js.get("samples", 0))
    out.update({"users": u, "samples": s})
    return out
