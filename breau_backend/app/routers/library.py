# breau_backend/app/routers/library.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict
from ..flavour.library_loader import (
    upsert_item, upsert_bean,
    get_toolset, get_bean
)

router = APIRouter(prefix="/library", tags=["library"])

# ----- Models -----
class BrewerIn(BaseModel):
    id: str
    geometry_type: Literal["conical","flat","hybrid","immersion","basket"]
    name: Optional[str] = None
    size_code: Optional[str] = None
    outlet_profile: Optional[str] = None

class PaperIn(BaseModel):
    id: str
    permeability: Literal["fast","medium","slow"]
    material: Optional[str] = "paper_bleached"
    thickness: Optional[str] = None

class GrinderIn(BaseModel):
    id: str
    burr_type: Literal["conical","flat","ghost"] = "conical"
    model: Optional[str] = None
    scale_type: Optional[str] = None

class WaterIn(BaseModel):
    id: str
    profile_preset: Optional[str] = "sca_target"
    hardness_gh: Optional[float] = None
    alkalinity_kh: Optional[float] = None

class ToolsetIn(BaseModel):
    id: str
    brewer_id: str
    paper_id: str
    grinder_id: str
    water_id: str

class BeanIn(BaseModel):
    id: str
    process: Optional[str] = None
    roast_level: Optional[str] = None
    age_days: Optional[int] = None
    baseline_notes: Optional[Dict[str,int]] = None

# ----- Upserts -----
@router.post("/brewers")
def upsert_brewer(body: BrewerIn): return upsert_item("brewers", body.model_dump())

@router.post("/papers")
def upsert_paper(body: PaperIn): return upsert_item("papers", body.model_dump())

@router.post("/grinders")
def upsert_grinder(body: GrinderIn): return upsert_item("grinders", body.model_dump())

@router.post("/waters")
def upsert_water(body: WaterIn): return upsert_item("waters", body.model_dump())

@router.post("/toolsets")
def upsert_toolset(body: ToolsetIn): return upsert_item("toolsets", body.model_dump())

@router.post("/beans")
def upsert_bean_api(body: BeanIn): return upsert_bean(body.model_dump())

# ----- Lookups (handy for debugging) -----
class ToolsetResolved(BaseModel):
    brewer: Dict
    filter: Dict
    grinder: Dict
    water: Dict

@router.get("/toolsets/{toolset_id}", response_model=ToolsetResolved)
def read_toolset(toolset_id: str):
    try:
        return get_toolset(toolset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/beans/{bean_id}")
def read_bean(bean_id: str):
    try:
        return get_bean(bean_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
