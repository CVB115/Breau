from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from typing import Dict

from ..services.learning.evaluator import Evaluator, EvalConfig
from ..services.learning.shadow import ShadowModel, ShadowConfig
from ..breau_backend.app.utils.storage import read_json

router = APIRouter(prefix="/learn", tags=["learn"])

DATA_DIR = Path("./data")
STATE_DIR = DATA_DIR / "state"
BANDIT_DIR = DATA_DIR / "metrics"
SHADOW_DIR = DATA_DIR / "models" / "shadow"

evalr = Evaluator(EvalConfig(state_dir=STATE_DIR, metrics_dir=BANDIT_DIR))
shadow = ShadowModel(ShadowConfig(root_dir=SHADOW_DIR))

# What it does:
# Get current learner state + bandit metrics snapshot for a user.
@router.get("/status/{user_id}", response_model=dict)
def status(user_id: str):
    try:
        s = evalr.get_state(user_id)
        bandit_metrics = read_json(BANDIT_DIR / f"{user_id}.json", default={"arms": {}})
        return {"state": s, "bandit": bandit_metrics}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"status failed: {e}")

# What it does:
# Promote a user to ACTIVE mode.
@router.post("/promote/{user_id}", response_model=dict)
def promote(user_id: str):
    try:
        s = evalr.set_mode(user_id, "ACTIVE")
        return {"ok": True, "state": s}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"promote failed: {e}")

# What it does:
# Demote a user to SHADOW mode.
@router.post("/demote/{user_id}", response_model=dict)
def demote(user_id: str):
    try:
        s = evalr.set_mode(user_id, "SHADOW")
        return {"ok": True, "state": s}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"demote failed: {e}")

# What it does:
# Snapshot of a user's shadow model goals (if any).
@router.get("/snapshots/{user_id}", response_model=dict)
def snapshots(user_id: str):
    try:
        js = read_json(SHADOW_DIR / f"{user_id}.json", default=None)
        if not js:
            return {"user_id": user_id, "has_model": False, "goals": []}
        goals = list((js.get("goals") or {}).keys())
        return {"user_id": user_id, "has_model": True, "goals": goals}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"snapshots failed: {e}")
