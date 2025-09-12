# breau_backend/app/models/library_models.py

from __future__ import annotations
from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field

# Schema version lock for all JSON/YAML data files
SCHEMA_VERSION = "3.1"



class SchemaHeader(BaseModel):
    schema_version: str = Field(default=SCHEMA_VERSION)


# ---------- Note Profile ----------

class NoteProfile(BaseModel):
    key: str
    category: str | None = None
    flavour_type: str | None = None
    description: str | None = None
    intensity_range: list[str] = Field(default_factory=list)  # ← was required, now default []
    volatility: str | None = None
    note_type: str | None = None
    mouthfeel_influence: list[str] | None = None
    over_extracted_traits: list[str] | None = None
    under_extracted_traits: list[str] | None = None
    may_contain: list[str] | None = None
    associated_flavours: list[str] | None = None
    cultural_notes: list[str] | None = None
    tags: list[str] | None = None

    class Config:
        extra = "allow"  # accept unexpected keys


# ---------- Decision Policy YAML ----------

class DecisionPolicy(BaseModel):
    schema_version: str = Field(default=SCHEMA_VERSION)
    slurry_targets: Dict[str, float] = Field(default_factory=dict)
    overlays: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    caps: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    filter_hints: Dict[str, str] = Field(default_factory=dict)


# ---------- Default Recipe ----------

class PourStep(BaseModel):
    water_g: int
    kettle_temp_c: Optional[int] = None
    pour_style: Optional[str] = None
    agitation: Optional[str] = None
    target_flow_ml_s: Optional[float] = None
    wait_for_bed_ready: Optional[bool] = None
    note: Optional[str] = None

class DefaultRecipe(BaseModel):
    key: Optional[str] = None
    name: str
    method: str
    ratio: str
    total_water_g: int
    temperature_c: int
    grind_label: str
    agitation_overall: str
    filter_hint: Optional[str] = None
    expected_drawdown_s: Optional[int] = None
    pours: List[PourStep]
