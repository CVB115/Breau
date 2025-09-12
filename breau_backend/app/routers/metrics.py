from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from ..breau_backend.app.utils.storage import read_json

router = APIRouter(prefix="/metrics", tags=["metrics"])

DATA_DIR = Path("./data")
USR_DIR = DATA_DIR / "metrics" / "users"
GLB_PATH = DATA_DIR / "metrics" / "global.json"

# What it does:
# Per‑user aggregate metrics snapshot (alignment, recent ratings, calibration).
@router.get("/user/{user_id}", response_model=dict)
def user_metrics(user_id: str):
    try:
        default = {"samples": 0, "alignment_hits": 0, "overall_ratings": [], "firstN": [], "lastN": [],
                   "calib_bitter": 0, "calib_sour": 0, "calib_total": 0, "N": 5}
        return read_json(USR_DIR / f"{user_id}.json", default)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"user metrics failed: {e}")

# What it does:
# Global metrics rollup across users.
@router.get("/global", response_model=dict)
def global_metrics():
    try:
        return read_json(GLB_PATH, {"users": 0, "alignment_rate": 0.0, "learning_gain": 0.0, "calibration_hit": 0.0})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"global metrics failed: {e}")
