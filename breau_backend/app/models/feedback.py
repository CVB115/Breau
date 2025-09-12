# breau_backend/app/models/feedback.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class RatingBlock(BaseModel):
    overall: Optional[float] = None
    clarity: Optional[float] = None
    body: Optional[float] = None
    acidity: Optional[float] = None
    bitterness: Optional[float] = None

    model_config = ConfigDict(extra="allow")


class ProtocolBlock(BaseModel):
    method: Optional[str] = None
    ratio: Optional[str] = None
    temperature_c: Optional[float] = None
    grind_label: Optional[str] = None
    agitation_overall: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class GoalItem(BaseModel):
    # supports your router’s _normalize_goal_tags(goals)
    tags: List[str] = []

    model_config = ConfigDict(extra="allow")


class FeedbackIn(BaseModel):
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    # context
    beans_meta: Optional[Dict[str, Any]] = None

    # protocol + ratings exactly as your router expects to read them
    protocol: Optional[ProtocolBlock] = None
    ratings: Optional[RatingBlock] = None

    # goal extraction helpers used by the router
    goals: Optional[List[GoalItem]] = None
    notes_confirmed: Optional[List[str]] = None
    notes_missing: Optional[List[str]] = None

    # misc
    free_text: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

    # be permissive with extra keys so older clients don’t break
    model_config = ConfigDict(extra="allow")


class SessionLog(BaseModel):
    feedback: FeedbackIn
    derived: Dict[str, Any] = {}

    model_config = ConfigDict(extra="allow")


__all__ = ["FeedbackIn", "SessionLog"]
