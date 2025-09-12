# breau_backend/app/flavour/engines/models.py
from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field

# Purpose:
# Typed models used by the flavour engines:
# - Note/Edge schemas (with conditions/effects/confidence)
# - Context modifiers (conditional tag/edge weight deltas)
# - Profiles and failure modes metadata.  :contentReference[oaicite:5]{index=5}

FacetTag = str  # "facet:value"

class FailureModes(BaseModel):
    # Purpose: common pitfalls for a note (what goes wrong over/under).
    over: List[str] = []
    under: List[str] = []

class SubProfile(BaseModel):
    # Purpose: sub-variants of a note (e.g., jasmine vs orange-blossom facets).
    tags: List[FacetTag] = []

class NoteProfile(BaseModel):
    # Purpose: master note definition + descriptive metadata for ranking/explain.
    name: str
    aliases: List[str] = []
    description: str
    tags: List[FacetTag]
    salience: float = Field(0.5, ge=0.0, le=1.0)
    failure_modes: FailureModes = FailureModes()
    sub_profiles: Dict[str, SubProfile] = {}

class EdgeEffect(BaseModel):
    # Purpose: what a neighbor changes in the tag space (add/remove).
    add: List[FacetTag] = []
    remove: List[FacetTag] = []
    notes: Optional[Union[str, List[str]]] = None

class EdgeConditions(BaseModel):
    # Purpose: brewing constraints under which an edge applies (temp region, contact time).
    brew: Dict[str, Any] = {}  # e.g. {"temp_min": 93, "contact_time": "long"}

class NoteEdge(BaseModel):
    # Purpose: link between notes with a type, effect, and optional conditions.
    type: Literal["association","synergy","suppression","transform_tendency"]
    source: str
    target: str
    conditions: EdgeConditions = EdgeConditions()
    effect: EdgeEffect = EdgeEffect()
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    notes: Optional[Union[str, List[str]]] = None

class ContextModifier(BaseModel):
    # Purpose: “when X then adjust Y” rule for tags/edges.
    when: Dict[str, Any]
    tag_weight_deltas: Dict[FacetTag, float] = {}
    edge_weight_deltas: Dict[str, float] = {}
