from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from typing import Optional

from ..services.learning.drift import decay_edges, prune_edges

router = APIRouter(prefix="/drift", tags=["drift"])

# What it does:
# Apply exponential decay to learned edges (regularization).
@router.post("/decay", response_model=dict)
def decay(factor: Optional[float] = 0.995):
    try:
        return decay_edges(factor or 0.995)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"decay failed: {e}")

# What it does:
# Prune small edges and cap per-goal fan-out to keep the graph lean.
@router.post("/prune", response_model=dict)
def prune(threshold: Optional[float] = 0.02, top_n_per_goal: Optional[int] = 20):
    try:
        return prune_edges(threshold or 0.02, int(top_n_per_goal or 20))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"prune failed: {e}")
