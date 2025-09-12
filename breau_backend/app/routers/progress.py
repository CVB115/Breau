from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from ..services.learning.progress import progress_nudge

router = APIRouter(prefix="/progress", tags=["progress"])

DATA_DIR = Path("./data")

# What it does:
# Gentle practice nudge for a user (e.g., “work on clarity this week”).
@router.get("/nudge/{user_id}", response_model=dict)
def get_nudge(user_id: str, days: int = 7):
    try:
        return progress_nudge(DATA_DIR, user_id, days=days)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"progress nudge failed: {e}")
