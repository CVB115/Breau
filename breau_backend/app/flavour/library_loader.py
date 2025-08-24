# breau_backend/app/flavour/library_loader.py
from __future__ import annotations
from pathlib import Path
import json
from typing import Dict, Any, Optional

_DATA_DIR = Path(__file__).resolve().parent / "data" / "library"
_TOOLS_PATH = _DATA_DIR / "tools.json"
_BEANS_PATH = _DATA_DIR / "beans.json"

_TOOLS_DEFAULT = {"brewers": [], "papers": [], "grinders": [], "waters": [], "toolsets": []}
_BEANS_DEFAULT = {"beans": []}

def _ensure_files() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _TOOLS_PATH.exists():
        _TOOLS_PATH.write_text(json.dumps(_TOOLS_DEFAULT, indent=2))
    if not _BEANS_PATH.exists():
        _BEANS_PATH.write_text(json.dumps(_BEANS_DEFAULT, indent=2))

def _load_tools() -> Dict[str, Any]:
    _ensure_files()
    try:
        return json.loads(_TOOLS_PATH.read_text())
    except Exception:
        return dict(_TOOLS_DEFAULT)

def _save_tools(data: Dict[str, Any]) -> None:
    _ensure_files()
    _TOOLS_PATH.write_text(json.dumps(data, indent=2))

def _load_beans() -> Dict[str, Any]:
    _ensure_files()
    try:
        return json.loads(_BEANS_PATH.read_text())
    except Exception:
        return dict(_BEANS_DEFAULT)

def _save_beans(data: Dict[str, Any]) -> None:
    _ensure_files()
    _BEANS_PATH.write_text(json.dumps(data, indent=2))

# ---------- Upserts ----------
def upsert_item(bucket: str, item: Dict[str, Any]) -> Dict[str, Any]:
    tools = _load_tools()
    items = tools.get(bucket, [])
    if "id" not in item or not item["id"]:
        raise ValueError("Item must have an 'id'.")
    items = [i for i in items if i.get("id") != item["id"]] + [item]
    tools[bucket] = items
    _save_tools(tools)
    return item

def upsert_bean(bean: Dict[str, Any]) -> Dict[str, Any]:
    beans = _load_beans()
    arr = beans.get("beans", [])
    if "id" not in bean or not bean["id"]:
        raise ValueError("Bean must have an 'id'.")
    arr = [b for b in arr if b.get("id") != bean["id"]] + [bean]
    beans["beans"] = arr
    _save_beans(beans)
    return bean

# ---------- Getters ----------
def _get_by_id(items, _id: str) -> Optional[Dict[str, Any]]:
    for it in items:
        if it.get("id") == _id:
            return it
    return None

def get_brewer(_id: str) -> Dict[str, Any]:
    item = _get_by_id(_load_tools()["brewers"], _id)
    if not item: raise KeyError(f"brewer '{_id}' not found")
    return item

def get_paper(_id: str) -> Dict[str, Any]:
    item = _get_by_id(_load_tools()["papers"], _id)
    if not item: raise KeyError(f"paper '{_id}' not found")
    return item

def get_grinder(_id: str) -> Dict[str, Any]:
    item = _get_by_id(_load_tools()["grinders"], _id)
    if not item: raise KeyError(f"grinder '{_id}' not found")
    return item

def get_water(_id: str) -> Dict[str, Any]:
    item = _get_by_id(_load_tools()["waters"], _id)
    if not item: raise KeyError(f"water '{_id}' not found")
    return item

def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}

def get_toolset(_id: str) -> Dict[str, Any]:
    tools = _load_tools()
    ts = _get_by_id(tools["toolsets"], _id)
    if not ts:
        raise KeyError(f"toolset '{_id}' not found")

    brewer  = get_brewer(ts["brewer_id"])
    paper   = get_paper(ts["paper_id"])
    grinder = get_grinder(ts["grinder_id"])
    water   = get_water(ts["water_id"])

    # REQUIRED enum defaults for your Pydantic models:
    thickness = paper.get("thickness") or "medium"          # Thickness enum
    material  = paper.get("material")  or "paper_bleached"  # FilterMaterial enum
    scale     = grinder.get("scale_type") or "numbers"      # GrinderScaleType enum

    return {
        "brewer": _clean({
            "name": brewer.get("name"),
            "geometry_type": brewer["geometry_type"],
            "size_code": brewer.get("size_code"),
            "outlet_profile": brewer.get("outlet_profile"),
        }),
        "filter": {
            # don't _clean here; we must keep required fields
            "permeability": paper["permeability"],
            "thickness": thickness,
            "material": material,
            # optional stays dropped if None
            **_clean({"pore_size_microns": paper.get("pore_size_microns")})
        },
        "grinder": _clean({
            "burr_type": grinder["burr_type"],
            "model": grinder.get("model"),
            "scale_type": scale
        }),
        "water": _clean({
            "profile_preset": water.get("profile_preset", "sca_target"),
            "hardness_gh": water.get("hardness_gh"),
            "alkalinity_kh": water.get("alkalinity_kh"),
        }),
    }

def get_bean(_id: str) -> Dict[str, Any]:
    bean = _get_by_id(_load_beans()["beans"], _id)
    if not bean: raise KeyError(f"bean '{_id}' not found")
    return bean
