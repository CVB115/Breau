# breau_backend/app/services/data_stores/profiles.py
from __future__ import annotations

import json, os, time
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from breau_backend.app.config.paths import path_under_data, ensure_data_dir_exists
from .io_utils import atomic_write, read_json

_IO_LOCK = RLock()

ensure_data_dir_exists()  # ensures ./data exists
PROFILES_PATH = Path(
    os.getenv("BREAU_PROFILE_PATH", str(path_under_data("profiles.json")))
).resolve()

def _read_json(path: Path, default):
    return read_json(path, default)

def _write_profiles_list(items: List[Dict[str, Any]]) -> None:
    with _IO_LOCK:
        atomic_write(PROFILES_PATH, json.dumps(items, ensure_ascii=False, indent=2))

def _read_profiles_list() -> List[Dict[str, Any]]:
    with _IO_LOCK:
        raw = _read_json(PROFILES_PATH, default=[])
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict) and "items" in raw and isinstance(raw["items"], list):
            return raw["items"]
        if isinstance(raw, dict):  # legacy {"local": {...}}
            now = time.time()
            return [{"user_id": k, "created_at": now, "updated_at": now, "data": v} for k, v in raw.items()]
        return []

def _canon_filter_material(s: Optional[str]) -> Optional[str]:
    if not s:
        return s
    key = str(s).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "paper_bleached": {"paper_bleached","paperbleached","bleached","white_paper","bleached_paper"},
        "paper_unbleached": {"paper_unbleached","paperunbleached","unbleached","brown_paper","natural_paper"},
        "abaca": {"abaca","paper_abaca","abaca_paper","cafec_abaca"},
        "hemp": {"hemp","hemp_paper"},
        "metal_stainless": {"metal_stainless","stainless","stainless_steel","steel"},
        "metal_titanium": {"metal_titanium","titanium","titanium_steel","ti"},
        "cloth_cotton": {"cloth_cotton","cloth","cotton","cotton_cloth"},
        "synthetic_poly": {"synthetic_poly","poly","polyester","nylon","synthetic"},
    }
    for canon, alts in aliases.items():
        if key == canon or key in alts:
            return canon
    return s

def _canon_profile_data(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data or {})
    if isinstance(data.get("filter"), dict):
        m = data["filter"].get("material")
        if isinstance(m, str):
            data["filter"]["material"] = _canon_filter_material(m)
    return data

def get_default_profile_template() -> Dict[str, Any]:
    return {
        "user_id": "default",
        "brewer": {
            "name":"Hario V60","geometry_type":"conical","cone_angle_deg":30,
            "outlet_profile":"single_large","size_code":"02","inner_diameter_mm":40,
            "hole_count":1,"thermal_mass":"medium"
        },
        "filter": {"permeability":"fast","thickness":"thin","material":"paper_bleached","pore_size_microns":5},
        "grinder": {
            "burr_type":"conical","model":"Generic","scale_type":"numbers","setting_value":None,
            "clicks_from_zero":None,"micron_estimate":None,"calibration_points":[],
            "user_scale_min":0,"user_scale_max":40
        },
        "water": {
            "profile_preset":"sca_target","hardness_gh":100,"alkalinity_kh":40,"tds":120,
            "calcium_mg_l":30,"magnesium_mg_l":10,"sodium_mg_l":10,"bicarbonate_mg_l":70
        },
        "dose_g": 15, "ratio":"1:15", "bloom_water_g":30, "bloom_time_s":35, "notes": None
    }

def get_profile(user_id: str) -> Dict[str, Any]:
    items = _read_profiles_list()
    for rec in items:
        if rec.get("user_id") == user_id:
            rec = dict(rec)
            rec["data"] = _canon_profile_data(rec.get("data", {}))
            return rec
    raise KeyError(f"profile not found: {user_id}")

def _deep_fill(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in (src or {}).items():
        if k not in dst or dst[k] is None:
            dst[k] = v
        elif isinstance(dst[k], dict) and isinstance(v, dict):
            _deep_fill(dst[k], v)
    return dst

def upsert_profile(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    items = _read_profiles_list()
    now = time.time()
    data = _canon_profile_data(dict(data or {}))
    if not data.get("user_id"):
        data["user_id"] = user_id

    found = False
    for i, rec in enumerate(items):
        if rec.get("user_id") == user_id:
            created = rec.get("created_at", now)
            items[i] = {"user_id": user_id, "created_at": created, "updated_at": now, "data": data}
            found = True
            break
    if not found:
        items.append({"user_id": user_id, "created_at": now, "updated_at": now, "data": data})

    _write_profiles_list(items)
    return get_profile(user_id)

def resolve_defaults_for_request(base: Dict[str, Any], user_id: str, fallback_to_template: bool = True) -> Dict[str, Any]:
    """
    Merge a base request payload with stored profile data for user_id.
    If profile missing and fallback_to_template=True, merge with default template.
    """
    try:
        prof = get_profile(user_id).get("data", {})
    except Exception:
        prof = get_default_profile_template() if fallback_to_template else {}

    # Normalize any filter material aliases from base
    base = dict(base or {})
    if isinstance(base.get("filter"), dict):
        m = base["filter"].get("material")
        if isinstance(m, str):
            base["filter"]["material"] = _canon_filter_material(m)

    merged = _deep_fill(base, prof)
    return merged
