# breau_backend/app/routers/brew.py
from typing import Dict,Any
from fastapi import APIRouter, HTTPException
from breau_backend.app.schemas import BrewSuggestRequest, BrewSuggestion
from breau_backend.app.services.protocol_generator import build_suggestion
from ..flavour.library_loader import get_toolset, get_bean

router = APIRouter()

def _drop_nones(x):
    if isinstance(x, dict):
        return {k: _drop_nones(v) for k, v in x.items() if v is not None}
    if isinstance(x, list):
        return [_drop_nones(v) for v in x if v is not None]
    return x


@router.post("/suggest")
def suggest(req: BrewSuggestRequest):
    patch: dict[str, Any] = {}

    if req.toolset_id:
        try:
            ts = get_toolset(req.toolset_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        if not req.brewer:  patch["brewer"]  = ts["brewer"]
        if not req.filter:  patch["filter"]  = ts["filter"]
        if not req.grinder: patch["grinder"] = ts["grinder"]
        if not req.water:   patch["water"]   = ts["water"]

    if req.bean_id:
        try:
            bean = get_bean(req.bean_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        if not req.bean: patch["bean"] = bean

    if patch:
        base = _drop_nones(req.model_dump(mode="json", round_trip=True))
        patch = _drop_nones(patch)
        base.update(patch)
        req = BrewSuggestRequest.model_validate(base)   # re-parse to enums/models

    return build_suggestion(req)
