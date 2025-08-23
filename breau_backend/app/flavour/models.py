from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field

FacetTag = str  # "facet:value"

class FailureModes(BaseModel):
    over: List[str] = []
    under: List[str] = []

class SubProfile(BaseModel):
    tags: List[FacetTag] = []

class NoteProfile(BaseModel):
    name: str
    aliases: List[str] = []
    description: str
    tags: List[FacetTag]
    salience: float = Field(0.5, ge=0.0, le=1.0)
    failure_modes: FailureModes = FailureModes()
    sub_profiles: Dict[str, SubProfile] = {}

class EdgeEffect(BaseModel):
    add: List[FacetTag] = []
    remove: List[FacetTag] = []
    notes: Optional[str] = None

class EdgeConditions(BaseModel):
    brew: Dict[str, Any] = {}  # e.g. {"temp_min": 93, "contact_time": "long"}

class NoteEdge(BaseModel):
    type: Literal["association","synergy","suppression","transform_tendency"]
    source: str
    target: str
    conditions: EdgeConditions = EdgeConditions()
    effect: EdgeEffect = EdgeEffect()
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    notes: Optional[str] = None

class ContextModifier(BaseModel):
    when: Dict[str, Any]
    tag_weight_deltas: Dict[FacetTag, float] = {}
    edge_weight_deltas: Dict[str, float] = {}
