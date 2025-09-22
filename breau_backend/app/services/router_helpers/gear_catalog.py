from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
import os

# Where to look for the catalogs:
#  - ENV var RULES_DIR can override
#  - default to app/flavours/rules/gear
#  - fallback to app/flavour/rules/gear (singular) if that’s what the repo uses in some places
_DEF_DIRS = []

_here = Path(__file__).resolve()
# app/service/router_helpers  -> up 2 -> app
_app = _here.parents[2]
_DEF_DIRS.append(_app / "flavours" / "rules" / "gear")
_DEF_DIRS.append(_app / "flavour"  / "rules" / "gear")

_env = os.getenv("RULES_DIR")
if _env:
    _DEF_DIRS.insert(0, Path(_env) / "gear")

# simple cache
_CACHE: Dict[str, Any] = {}

def _load_json(fname: str) -> Dict[str, Any]:
    key = f"json::{fname}"
    if key in _CACHE:
        return _CACHE[key]
    for base in _DEF_DIRS:
        p = (base / fname)
        if p.exists():
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                _CACHE[key] = data
                return data
    _CACHE[key] = {}
    return {}

def list_grinders() -> List[Dict[str, Any]]:
    return _load_json("grinders.json").get("grinders", [])

def list_brewers() -> List[Dict[str, Any]]:
    return _load_json("brewers.json").get("brewers", [])

def list_filters() -> List[Dict[str, Any]]:
    return _load_json("filters.json").get("filters", [])

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def find_grinder_by_alias(brand: Optional[str], model: Optional[str]) -> Optional[Dict[str, Any]]:
    b = _norm(brand); m = _norm(model)
    for g in list_grinders():
        names = set([_norm(g.get("model")), f"{_norm(g.get('brand'))} {_norm(g.get('model'))}".strip()])
        for a in g.get("aliases", []) or []:
            names.add(_norm(a))
        if m in names or f"{b} {m}".strip() in names:
            return g
    return None

def get_brewer(brewer_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not brewer_id: return None
    for b in list_brewers():
        if _norm(b.get("id")) == _norm(brewer_id):
            return b
    return None

def get_filter(filter_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not filter_id: return None
    for f in list_filters():
        if _norm(f.get("id")) == _norm(filter_id):
            return f
    return None

# --- Bridge into grind_math presets so new models work without code changes ---
def sync_grinders_into_grind_math():
    try:
        # Import only when called to avoid hard dependency on import order
        from breau_backend.app.flavour.engine.grind_math import PRESET_CURVES
    except Exception:
        return
    for g in list_grinders():
        model_key = _norm(g.get("model"))
        a = g.get("a"); b = g.get("b"); scale = g.get("scale")
        if a is None or b is None or not isinstance(scale, dict):
            continue
        PRESET_CURVES[model_key] = {"a": float(a), "b": float(b), "scale": scale}
