from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Literal
from ..flavour.profile import append_observation, load_profile, save_profile, update_drawdown_ema

router = APIRouter()

class GoalIn(BaseModel):
    type: Optional[Literal["trait", "note"]] = "trait"
    trait: Optional[str] = None
    note: Optional[str] = None
    direction: Optional[Literal["increase", "decrease"]] = None
    weight: Optional[float] = 1.0

class BrewContextIn(BaseModel):
    toolset_id: Optional[str] = None
    bean_id: Optional[str] = None

class FeedbackIn(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    brew_context: Optional[BrewContextIn] = None
    goal: Optional[GoalIn] = None

    drawdown_s: Optional[float] = None
    satisfaction: Optional[float] = Field(None, ge=0, le=1)
    alignment: Optional[Literal["closer", "same", "further"]] = None

    # quick forced choices (early sessions)
    thinner_heavier: Optional[Literal["thinner", "heavier"]] = None
    brighter_duller: Optional[Literal["brighter", "duller"]] = None

    # detail sliders (0..10 typical)
    sliders: Optional[Dict[str, float]] = None  # acidity/sweetness/body/bitterness/clarity

    confirmed_notes: Optional[List[str]] = None
    free_text: Optional[str] = None
    mode: Optional[Literal["beginner", "expert"]] = None
    ab_variant: Optional[Literal["A", "B"]] = None

@router.post("/feedback")
def post_feedback(body: FeedbackIn):
    profile = load_profile(body.user_id)

    # Append raw row for learning later
    row = body.model_dump()
    append_observation(body.user_id, row)

    # Update drawdown EMA if provided
    if body.drawdown_s is not None:
        update_drawdown_ema(profile, key="default", drawdown_s=body.drawdown_s)

    # Increment rows_seen
    ts = profile.get("training_state", {})
    ts["rows_seen"] = ts.get("rows_seen", 0) + 1
    profile["training_state"] = ts

    save_profile(body.user_id, profile)
    return {"ok": True}
