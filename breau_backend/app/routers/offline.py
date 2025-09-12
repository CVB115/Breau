from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from typing import Dict
from ..services.learning.offline_eval import eval_ips_dr

router = APIRouter(prefix="/offline", tags=["offline"])

# What it does:
# Offline evaluation: IPS/DR estimates for target arm over recent sessions.
@router.post("/eval", response_model=dict)
def eval_offline(body: Dict):
    try:
        target = (body or {}).get("target", "baseline")  # "baseline" | "shadow" | "planner" | "all"
        window_days = (body or {}).get("window_days", 30)
        return eval_ips_dr(target, window_days=window_days)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"offline eval failed: {e}")
