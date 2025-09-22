# breau_backend/app/services/gear_norm.py
from __future__ import annotations
from typing import Any, Dict, Optional

def _coerce_obj(v) -> Optional[Dict[str, Any]]:
    if v is None:
        return None
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        return {"name": v}
    return None

def normalize_gear_combo(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Accepts many shapes:
      - {"gear": {...}} or {"gear_combo": {...}} or {"combo": {...}}
      - {"brewer": "...", "grinder": "...", ...}
      - {"label": "...", "brewer_name": "...", "grind": "20 clicks", "water_temp": 96, ...}
    Returns canonical combo dict (see docstring) or None if not enough info.
    """
    if not isinstance(payload, dict):
        return None

    # dig out the gear-ish object, or treat top-level as the object
    g = payload.get("gear") or payload.get("gear_combo") or payload.get("combo") or payload
    if not isinstance(g, dict):
        return None

    brewer  = _coerce_obj(g.get("brewer")  or g.get("brewer_name")  or payload.get("brewer"))
    grinder = _coerce_obj(g.get("grinder") or g.get("grinder_name") or payload.get("grinder"))
    filter_ = _coerce_obj(g.get("filter")  or g.get("filter_name")  or payload.get("filter"))
    water   = _coerce_obj(g.get("water")   or g.get("water_name")   or payload.get("water"))

    # common synonyms
    grind_setting = g.get("grind") or g.get("grinder_setting") or g.get("setting")
    if isinstance(grinder, dict) and grind_setting:
        grinder.setdefault("setting", grind_setting)

    temp = g.get("temp_c") or g.get("temperature_c") or g.get("water_temp") or payload.get("temp_c")
    if isinstance(water, dict) and temp is not None:
        try:
            water.setdefault("temp_c", float(temp))
        except Exception:
            pass

    tds = g.get("tds") or g.get("water_tds") or payload.get("tds")
    if isinstance(water, dict) and tds is not None:
        try:
            water.setdefault("tds", float(tds))
        except Exception:
            pass

    label = g.get("label") or payload.get("label")
    combo_id = g.get("id") or payload.get("gear_combo_id") or payload.get("id")

    # If we literally have nothing, bail
    if not any([brewer, grinder, filter_, water]):
        return None

    return {
        "id": combo_id,
        "label": label or build_label(brewer, grinder, water),
        "brewer": brewer or {"name": "Unknown brewer"},
        "grinder": grinder or {"name": "Unknown grinder"},
        "filter": filter_ or {"name": "Unknown filter"},
        "water": water or {"name": "Water", "temp_c": 96},
    }

def build_label(brewer, grinder, water) -> str:
    b = (brewer or {}).get("name") or "Brewer"
    g = (grinder or {}).get("name") or "Grinder"
    w = (water or {}).get("name") or "Water"
    return f"{b} • {g} • {w}"
