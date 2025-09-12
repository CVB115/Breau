from __future__ import annotations
from typing import Any, Dict

from fastapi import APIRouter

from breau_backend.app.schemas import (
    BrewSuggestRequest,
    # BrewFeedbackIn,  # ← not used directly anymore to avoid 422 on flat test payloads
)

from breau_backend.app.services.router_helpers import brew_helpers as H

router = APIRouter(prefix="/brew", tags=["brew"])


# ----------------------------------------------------------------------
# Suggestion endpoints
# ----------------------------------------------------------------------

@router.post("/suggest")
def suggest(req: BrewSuggestRequest):
    """
    Build a full brewing suggestion (notes, pours, temps, etc.)
    via the protocol generator. Returns 500 on unexpected errors.
    """
    return H.suggest(req)


@router.post("/resolve")
def resolve_goals(payload: Dict[str, Any]):
    """
    Free‑text -> structured goals (best‑effort), plus a cluster preview string.
    Tests assert 'resolved.goals' exists and the preview looks like 'washed:light:fast'.
    """
    return H.resolve_goals(payload)


@router.post("/plan")
def plan(payload: Dict[str, Any]):
    """
    Convert pour dictionaries into validated PourStepIn items and
    produce a session plan. Returns 400 for malformed inputs.
    """
    return H.plan(payload)


@router.get("/fallback")
def fallback():
    """
    Minimal, safe suggestion (used when builder is not fully wired).
    """
    return H.fallback()


# ----------------------------------------------------------------------
# Feedback endpoint (updates dynamic priors / learning)
# ----------------------------------------------------------------------

@router.post("/feedback")
def post_feedback(payload: Dict[str, Any]):
    """
    Record post‑brew feedback. Tolerates both the flat test payload shape
    and richer shapes. The helper will validate minimally and return 4xx
    for clearly invalid payloads (e.g., empty user_id/session_id).
    """
    return H.feedback_any(payload)


# ----------------------------------------------------------------------
# Priors endpoints (both 'cluster' and 'path' forms)
# ----------------------------------------------------------------------

@router.get("/priors/{cluster}")
def read_priors_by_cluster(cluster: str, top_k: int = 5):
    """
    Inspect learned+static priors for a cluster key, e.g. 'washed:light:fast'.
    Response includes:
      - dynamic_notes_top
      - static_notes
      - dynamic_traits
    """
    return H.priors_by_cluster(cluster, top_k=top_k)


@router.get("/priors/{process}/{roast}/{permeability}")
def read_priors_by_path(process: str, roast: str, permeability: str, top_k: int = 5):
    """
    Path-form variant used by tests:
      /brew/priors/washed/light/fast
    Returns the same keys as read_priors_by_cluster(..).
    """
    return H.priors_by_path(process, roast, permeability, top_k=top_k)
