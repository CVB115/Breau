# app/routers/brew.py
from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter

from breau_backend.app.schemas import BrewSuggestRequest
from breau_backend.app.services.router_helpers import brew_helpers as H


# ---- tolerant schema import ----
try:
    from app.schemas import BrewSuggestRequest
except Exception:
    from breau_backend.app.schemas import BrewSuggestRequest  # fallback

# ---- tolerant helper import ----
try:
    # same module you uploaded (has suggest/resolve_goals/plan/etc.)
    from app.services.router_helpers import brew_helpers as H
except Exception:
    from breau_backend.app.services.router_helpers import brew_helpers as H  # fallback

# optional recommender
try:
    from app.services.router_helpers.grind_recommender import recommend_grind
except Exception:
    try:
        from breau_backend.app.services.router_helpers.grind_recommender import recommend_grind
    except Exception:
        recommend_grind = None  # type: ignore

# optional active-gear helper
try:
    from app.services.router_helpers.profile_helpers import get_active_gear  # type: ignore
except Exception:
    try:
        from breau_backend.app.services.router_helpers.profile_helpers import get_active_gear  # type: ignore
    except Exception:
        get_active_gear = None  # type: ignore

router = APIRouter(prefix="/brew", tags=["brew"])

@router.post("/suggest")
def suggest(req: BrewSuggestRequest):
    """
    Returns a recipe suggestion. If grinder/brewer/filter/bean info is available,
    enrich the recipe with:
      - recipe.grind_target_micron (float)
      - recipe.grind_setting (float)
      - recipe.grind_label (e.g., "C40 ≈ 22 clicks (~820 µm)")
      - recipe.grind_scale (dial metadata if available)
    """
    res = H.suggest(req)

    # Ensure we have a dict with a recipe map we can extend
    if not isinstance(res, dict):
        return res
    recipe: Dict[str, Any] = dict(res.get("recipe") or {})
    bean = getattr(req, "bean", None)  # FE sends a snapshot now
    gear = getattr(req, "gear", None)

    if gear is None and get_active_gear is not None:
        try:
            gear = get_active_gear(req.user_id)  # type: ignore
        except Exception:
            gear = None

    if recommend_grind and gear:
        try:
            rec = recommend_grind(bean, gear)
            recipe["grind_target_micron"] = rec["target_micron"]
            recipe["grind_setting"] = rec["setting"]
            recipe["grind_label"] = rec["label"]
            recipe["grind_scale"] = rec.get("scale")
            res["recipe"] = recipe
        except Exception:
            # keep suggestion working even if recommender fails
            pass

    return res

@router.post("/resolve")
def resolve_goals(payload: Dict[str, Any]):
    return H.resolve_goals(payload)

@router.get("/priors")
def read_priors(cluster: str, top_k: int = 5):
    """
    Returns priors set (static & dynamic) for UI visualization.
    """
    return H.read_dynamic_priors(cluster, top_k=top_k)

@router.get("/priors/{process}/{roast}/{permeability}")
def read_priors_by_path(process: str, roast: str, permeability: str, top_k: int = 5):
    """
    Path-form variant used by tests:
      /brew/priors/washed/light/fast
    """
    return H.priors_by_path(process, roast, permeability, top_k=top_k)
