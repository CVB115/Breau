from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from typing import Optional
from ..services.learning.watchdog import scan_anomalies

router = APIRouter(prefix="/watchdog", tags=["watchdog"])

# What it does:
# Scan recent data for anomalies (e.g., metric drift spikes).
@router.get("/scan", response_model=dict)
def scan(window_days: Optional[int] = 60):
    try:
        return scan_anomalies(window_days or 60)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"scan failed: {e}")
