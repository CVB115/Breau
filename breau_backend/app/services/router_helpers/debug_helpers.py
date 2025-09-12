# breau_backend/app/services/router_helpers/debug_helpers.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import os, sys, platform

def probe() -> Dict[str, Any]:
    """Health + minimal environment info (no exceptions)."""
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    return {
        "ok": "debug",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "data_dir": str(base),
        "exists": base.exists(),
    }

def get_trace() -> Dict[str, Any]:
    """Placeholder for last trace (returns empty if no tracing system)."""
    return {"trace": None}

def ping() -> Dict[str, Any]:
    """Simple loopback ping."""
    return {"ok": True}
