from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter

from breau_backend.app.schemas import BrewSuggestRequest
from breau_backend.app.services.router_helpers import brew_helpers as H

router = APIRouter(prefix="/brew", tags=["brew"])

@router.post("/suggest")
def suggest(req: BrewSuggestRequest):
    return H.suggest(req)

@router.post("/resolve")
def resolve_goals(payload: Dict[str, Any]):
    return H.resolve_goals(payload)

@router.post("/plan")
def plan(payload: Dict[str, Any]):
    return H.plan(payload)

@router.get("/fallback")
def fallback():
    return H.fallback()

@router.post("/feedback")
def feedback(payload: Dict[str, Any]):
    """
    Tolerant endpoint: accepts either the minimal BrewFeedbackIn shape or the rich FeedbackIn.
    """
    return H.feedback_any(payload)

@router.get("/priors/{cluster}")
def read_priors_by_cluster(cluster: str, top_k: int = 5):
    """
    Returns:
      - static_notes
      - dynamic_notes
      - dynamic_traits
      - ratings_summary
    """
    return H.read_dynamic_priors(cluster, top_k=top_k)

@router.get("/priors/{process}/{roast}/{permeability}")
def read_priors_by_path(process: str, roast: str, permeability: str, top_k: int = 5):
    """
    Path-form variant used by tests:
      /brew/priors/washed/light/fast
    """
    return H.priors_by_path(process, roast, permeability, top_k=top_k)
