from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
from pathlib import Path

from breau_backend.app.config.paths import path_under_data, ensure_data_dir_exists
from breau_backend.app.flavour.engine.grind_math import microns_for_setting

router = APIRouter(prefix="/library", tags=["library"])

def _lib_path(name: str) -> Path:
    """Resolve a path under DATA_DIR/library and ensure the parent exists."""
    ensure_data_dir_exists("library")
    return path_under_data("library", name)

LIB_TOOLS = _lib_path("tools.json")
LIB_BEANS = _lib_path("beans.json")

def _read_json(p: Path):
    """Safe JSON read; returns None on fail/missing for caller to default."""
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None

def _write_json(p: Path, obj: dict):
    """Atomic JSON write with tmp swap."""
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

# ---------- Models ----------
class GrinderIn(BaseModel):
    id: str
    model: str
    burr_type: str
    scale_type: str = "numbers"
    user_scale_min: float = 0
    user_scale_max: float = 40
    calibration_points: Optional[List[Dict[str, float]]] = None
    preset_curve: Optional[Dict[str, float]] = None  # {"a":200,"b":18}

class BrewerIn(BaseModel):
    id: str
    name: str
    geometry_type: str
    cone_angle_deg: Optional[float] = None
    outlet_profile: Optional[str] = None
    inner_diameter_mm: Optional[float] = None
    hole_count: Optional[int] = None
    thermal_mass: Optional[str] = None

class FilterIn(BaseModel):
    id: str
    permeability: str
    thickness: Optional[str] = None
    material: Optional[str] = None
    pore_size_microns: Optional[float] = None

class WaterIn(BaseModel):
    id: str
    profile_preset: Optional[str] = None
    hardness_gh: Optional[float] = None
    alkalinity_kh: Optional[float] = None
    tds: Optional[float] = None

class ToolsDoc(BaseModel):
    grinders: List[GrinderIn] = []
    brewers: List[BrewerIn] = []
    filters: List[FilterIn] = []
    waters: List[WaterIn] = []

class BeanIn(BaseModel):
    id: str
    aliases: List[str] = []
    origin: Optional[str] = None
    process: Optional[str] = None
    roast_level: Optional[str] = None
    solubility_hint: Optional[str] = None
    character_caps: Optional[List[str]] = []

# ---------- Tools ----------
# What it does:
# List all tools in the library.
@router.get("/tools")
def list_tools():
    return _read_json(LIB_TOOLS) or {"grinders": [], "brewers": [], "filters": [], "waters": []}

# What it does:
# Append new tools to the library (no dedupe).
@router.post("/tools")
def add_tools(payload: ToolsDoc):
    doc = _read_json(LIB_TOOLS) or {"grinders": [], "brewers": [], "filters": [], "waters": []}
    doc["grinders"].extend([g.model_dump() for g in payload.grinders])
    doc["brewers"].extend([b.model_dump() for b in payload.brewers])
    doc["filters"].extend([f.model_dump() for f in payload.filters])
    doc["waters"].extend([w.model_dump() for w in payload.waters])
    _write_json(LIB_TOOLS, doc)
    return {"ok": True}

# What it does:
# Patch a single tool by id (searches across all sections).
@router.patch("/tools/{tool_id}")
def update_tool(tool_id: str, payload: Dict):
    doc = _read_json(LIB_TOOLS) or {"grinders": [], "brewers": [], "filters": [], "waters": []}
    updated = False
    for section in ("grinders", "brewers", "filters", "waters"):
        for i, item in enumerate(doc.get(section, [])):
            if item.get("id") == tool_id:
                item.update(payload)
                doc[section][i] = item
                updated = True
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool id not found")
    _write_json(LIB_TOOLS, doc)
    return {"ok": True}

# What it does:
# Remove a tool by id (searched across sections).
@router.delete("/tools/{tool_id}")
def delete_tool(tool_id: str):
    doc = _read_json(LIB_TOOLS) or {"grinders": [], "brewers": [], "filters": [], "waters": []}
    removed = False
    for section in ("grinders", "brewers", "filters", "waters"):
        before = len(doc.get(section, []))
        doc[section] = [x for x in doc.get(section, []) if x.get("id") != tool_id]
        removed = removed or (len(doc[section]) < before)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool id not found")
    _write_json(LIB_TOOLS, doc)
    return {"ok": True}

# ---------- Beans ----------
# What it does:
# List bean entries in the library.
@router.get("/beans")
def list_beans():
    return _read_json(LIB_BEANS) or {"beans": []}

# What it does:
# Append beans (no dedupe).
@router.post("/beans")
def add_beans(payload: Dict[str, List[BeanIn]]):
    doc = _read_json(LIB_BEANS) or {"beans": []}
    for b in payload.get("beans", []):
        doc["beans"].append(b.model_dump() if hasattr(b, "model_dump") else b)
    _write_json(LIB_BEANS, doc)
    return {"ok": True}

# What it does:
# Patch a bean by id.
@router.patch("/beans/{bean_id}")
def update_bean(bean_id: str, patch: Dict):
    doc = _read_json(LIB_BEANS) or {"beans": []}
    for i, b in enumerate(doc["beans"]):
        if b.get("id") == bean_id:
            b.update(patch)
            doc["beans"][i] = b
            _write_json(LIB_BEANS, doc)
            return {"ok": True}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bean id not found")

# What it does:
# Delete a bean by id.
@router.delete("/beans/{bean_id}")
def delete_bean(bean_id: str):
    doc = _read_json(LIB_BEANS) or {"beans": []}
    before = len(doc["beans"])
    doc["beans"] = [b for b in doc["beans"] if b.get("id") != bean_id]
    if len(doc["beans"]) == before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bean id not found")
    _write_json(LIB_BEANS, doc)
    return {"ok": True}

# ---------- Microns ----------
# What it does:
# Convert a grinder UI setting -> micron size using stored calibration/preset curve.
@router.get("/grinders/{grinder_id}/microns")
def grinder_microns(grinder_id: str, setting: float):
    doc = _read_json(LIB_TOOLS) or {"grinders": []}
    g = next((x for x in doc.get("grinders", []) if x.get("id") == grinder_id), None)
    if not g:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grinder not found")
    micron = microns_for_setting(
        setting=setting,
        calibration_points=g.get("calibration_points") or [],
        preset_curve=g.get("preset_curve") or None,
        burr_type=g.get("burr_type"),
    )
    return {"grinder_id": grinder_id, "setting": setting, "micron": micron}
