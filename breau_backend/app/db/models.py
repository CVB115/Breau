# models.py  (Improvement set: richer brewer/filter/grinder/water/bean)

from __future__ import annotations
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime


# ---------- Brewer & Filter ----------

class BrewerSpec(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: Optional[str] = None
    geometry_type: str                             # enum string
    cone_angle_deg: Optional[float] = None
    outlet_profile: Optional[str] = None
    size_code: Optional[str] = None
    inner_diameter_mm: Optional[float] = None
    hole_count: Optional[int] = None
    thermal_mass: Optional[str] = None

class FilterSpec(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    permeability: str
    thickness: str
    material: str
    pore_size_microns: Optional[float] = None


# ---------- Grinder ----------

class GrinderSpec(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    burr_type: str
    model: Optional[str] = None
    scale_type: str
    setting_value: Optional[float] = None
    clicks_from_zero: Optional[int] = None
    micron_estimate: Optional[float] = None
    calibration_points: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    user_scale_min: Optional[int] = None
    user_scale_max: Optional[int] = None


# ---------- Water ----------

class WaterProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_preset: str = "sca_target"
    hardness_gh: Optional[float] = None
    alkalinity_kh: Optional[float] = None
    tds: Optional[float] = None
    calcium_mg_l: Optional[float] = None
    magnesium_mg_l: Optional[float] = None
    sodium_mg_l: Optional[float] = None
    bicarbonate_mg_l: Optional[float] = None


# ---------- Beans (with blends) ----------

class BeanProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    roaster: Optional[str] = None
    name: Optional[str] = None
    origin: Optional[str] = None
    variety: Optional[str] = None
    process: Optional[str] = None
    roast_level: Optional[str] = None
    density_class: Optional[str] = None
    measured_density_g_l: Optional[float] = None
    roast_date: Optional[str] = None
    age_days: Optional[int] = None
    components: Optional[dict] = Field(default=None, sa_column=Column(JSON))  # list of components


# ---------- Flavor dictionary (to be filled later) ----------

class NoteProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str
    category: Optional[str] = None
    volatility: Optional[str] = None
    extraction_sensitivity: Optional[float] = None
    agitation_sensitivity: Optional[float] = None
    thermal_sensitivity: Optional[float] = None
    flow_sensitivity: Optional[float] = None
    mouthfeel_weight: Optional[float] = None
    high_extraction_traits: Optional[list] = Field(default=None, sa_column=Column(JSON))
    low_extraction_traits: Optional[list] = Field(default=None, sa_column=Column(JSON))
    tags: Optional[list] = Field(default=None, sa_column=Column(JSON))
    cultural_notes: Optional[list] = Field(default=None, sa_column=Column(JSON))


# ---------- Templates & Logs ----------

class RecipeTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    brewer_spec_id: Optional[int] = Field(default=None, foreign_key="brewerspec.id")
    filter_spec_id: Optional[int] = Field(default=None, foreign_key="filterspec.id")
    base_ratio: str = "1:15"
    temperature_c: int = 92
    grind_label: str = "medium-fine"
    agitation_overall: str = "gentle"
    param_bias: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BrewLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    method: str
    ratio: str
    temperature_c: int
    grind_label: str
    agitation: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
