# schemas.py  (Improvement set: geometry/materials/grinder scale/water/beans)

from __future__ import annotations
from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field, conint, confloat


# ===================== Enums =====================

class BrewerGeometryType(str, Enum):
    CONICAL = "conical"          # e.g., V60, Orea UFO (angle varies)
    FLAT = "flat"                # e.g., Kalita Wave
    HYBRID = "hybrid"            # e.g., flared/basket-like hybrids
    IMMERSION = "immersion"      # e.g., Clever (with drain)
    BASKET = "basket"            # e.g., large flat baskets

class OutletProfile(str, Enum):
    SINGLE_LARGE = "single_large"
    MULTI_SMALL = "multi_small"
    MESH = "mesh"                # metal mesh base/side

class Permeability(str, Enum):
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"

class Thickness(str, Enum):
    THIN = "thin"
    MEDIUM = "medium"
    THICK = "thick"

class FilterMaterial(str, Enum):
    PAPER_BLEACHED = "paper_bleached"
    PAPER_UNBLEACHED = "paper_unbleached"
    ABACA = "abaca"
    HEMP = "hemp"
    METAL_STAINLESS = "metal_stainless"
    METAL_TITANIUM = "metal_titanium"
    CLOTH_COTTON = "cloth_cotton"
    SYNTHETIC_POLY = "synthetic_poly"

class BurrType(str, Enum):
    CONICAL = "conical"
    FLAT = "flat"
    GHOST = "ghost"

class GrinderScaleType(str, Enum):
    NUMBERS = "numbers"
    CLICKS_FROM_ZERO = "clicks_from_zero"
    CLICKS_FROM_TIGHT = "clicks_from_tight"
    MICRONS_ESTIMATE = "microns_estimate"

class PourStyle(str, Enum):
    SPIRAL = "spiral"
    CENTER = "center"
    SEGMENTED = "segmented"
    PULSE = "pulse"

class Agitation(str, Enum):
    NONE = "none"
    GENTLE = "gentle"
    MODERATE = "moderate"
    HIGH = "high"

class GoalTrait(str, Enum):
    ACIDITY = "acidity"
    SWEETNESS = "sweetness"
    BITTERNESS = "bitterness"
    FLORALITY = "florality"
    BODY = "body"
    CLARITY = "clarity"
    AFTERTASTE = "aftertaste"

class WaterPreset(str, Enum):
    SCA_TARGET = "sca_target"
    RAO_V60 = "rao_v60"
    THIRD_WAVE = "third_wave"
    CUSTOM = "custom"


# ===================== Specs =====================

class BrewerSpecIn(BaseModel):
    name: Optional[str] = None                  # e.g., "Hario V60-02", "Orea V3 UFO"
    geometry_type: BrewerGeometryType
    cone_angle_deg: Optional[confloat(ge=30, le=100)] = None   # only meaningful if conical/flared
    outlet_profile: Optional[OutletProfile] = None
    size_code: Optional[str] = None             # "01","02","03" or "small/medium/large"
    inner_diameter_mm: Optional[confloat(ge=40, le=150)] = None
    hole_count: Optional[int] = None
    thermal_mass: Optional[str] = None          # "low","medium","high"

class FilterSpecIn(BaseModel):
    permeability: Permeability
    thickness: Thickness
    material: FilterMaterial
    pore_size_microns: Optional[confloat(ge=5, le=200)] = None

class GrinderCalibrationPoint(BaseModel):
    label: str          # e.g., "filter medium-fine"
    value: Union[int, float]

class GrinderSpecIn(BaseModel):
    burr_type: BurrType
    model: Optional[str] = None
    scale_type: GrinderScaleType = GrinderScaleType.NUMBERS
    setting_value: Optional[Union[int, float]] = None
    clicks_from_zero: Optional[conint(ge=0, le=999)] = None
    micron_estimate: Optional[confloat(ge=100, le=2000)] = None
    calibration_points: Optional[List[GrinderCalibrationPoint]] = None
    user_scale_min: Optional[int] = None
    user_scale_max: Optional[int] = None

class WaterProfileIn(BaseModel):
    profile_preset: WaterPreset = WaterPreset.SCA_TARGET
    # Beginner-facing
    hardness_gh: Optional[confloat(ge=0, le=300)] = None
    alkalinity_kh: Optional[confloat(ge=0, le=300)] = None
    tds: Optional[confloat(ge=0, le=500)] = None
    # Advanced (optional)
    calcium_mg_l: Optional[confloat(ge=0, le=200)] = None
    magnesium_mg_l: Optional[confloat(ge=0, le=200)] = None
    sodium_mg_l: Optional[confloat(ge=0, le=200)] = None
    bicarbonate_mg_l: Optional[confloat(ge=0, le=400)] = None

class BeanComponent(BaseModel):
    origin: Optional[str] = None
    variety: Optional[str] = None
    process: Optional[str] = None
    percent: Optional[confloat(ge=0, le=100)] = None

class BeanInfo(BaseModel):
    roaster: Optional[str] = None
    name: Optional[str] = None
    origin: Optional[str] = None
    variety: Optional[str] = None
    process: Optional[str] = None
    roast_level: Optional[str] = None         # light/medium/dark
    density_class: Optional[str] = None       # low/medium/high
    measured_density_g_l: Optional[confloat(ge=100, le=900)] = None
    roast_date: Optional[str] = None          # ISO date "YYYY-MM-DD"
    age_days: Optional[int] = None            # can be derived if date known
    components: Optional[List[BeanComponent]] = None  # for blends


# ===================== Goals & Recipe =====================

class WeightedGoal(BaseModel):
    trait: GoalTrait
    direction: str                        # "increase" | "reduce"
    weight: confloat(ge=0, le=1) = 1.0

class PourStepIn(BaseModel):
    water_g: conint(ge=1)
    kettle_temp_c: conint(ge=70, le=100)
    pour_style: PourStyle
    agitation: Agitation
    target_flow_ml_s: Optional[confloat(ge=0.5, le=10)] = None
    wait_for_bed_ready: bool = True
    note: Optional[str] = None

class BrewSuggestRequest(BaseModel):
    goals: Optional[List[WeightedGoal]] = None
    text: Optional[str] = None

    brewer: Optional[BrewerSpecIn] = None
    filter: Optional[FilterSpecIn] = None
    grinder: Optional[GrinderSpecIn] = None
    water: Optional[WaterProfileIn] = None
    bean: Optional[BeanInfo] = None

    dose_g: Optional[conint(ge=5, le=60)] = 15
    ratio: Optional[str] = "1:15"
    target_strength_tds: Optional[confloat(ge=0.8, le=2.0)] = None
    target_drawdown_s: Optional[conint(ge=60, le=480)] = None
    bypass_g: Optional[conint(ge=0, le=200)] = 0
    bloom_water_g: Optional[conint(ge=0, le=120)] = 30
    bloom_time_s: Optional[conint(ge=0, le=90)] = 35

class PredictedNote(BaseModel):
    label: str
    confidence: confloat(ge=0, le=1)
    rationale: Optional[str] = None

class BrewSuggestion(BaseModel):
    method: str
    ratio: str
    total_water_g: conint(ge=50, le=1200)
    temperature_c: conint(ge=80, le=100)
    grind_label: str
    agitation_overall: Agitation
    filter_hint: Optional[str] = None
    expected_drawdown_s: Optional[int] = None
    pours: List[PourStepIn] = Field(default_factory=list)
    predicted_notes: List[PredictedNote] = Field(default_factory=list)
    notes: Optional[str] = None

    notes: str
