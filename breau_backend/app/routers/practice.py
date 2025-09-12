from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from typing import Dict
from ..services.learning.practice import PracticeManager, PracticeConfig
from ..services.learning.edge_learner import EdgeLearner, EdgeLearnerConfig

router = APIRouter(prefix="/practice", tags=["practice"])

DATA_DIR = Path("./data")
PRACTICE_DIR = DATA_DIR / "practice"
EDGES_PATH = DATA_DIR / "priors" / "dynamic_edges.json"

pm = PracticeManager(PracticeConfig(practice_dir=PRACTICE_DIR))
edge = EdgeLearner(EdgeLearnerConfig(data_dir=DATA_DIR, edges_path=EDGES_PATH))

# What it does:
# Enable/disable a user focus area (e.g., clarity) for guided practice.
@router.put("/focus/{user_id}", response_model=dict)
def set_focus(user_id: str, body: Dict):
    try:
        focus = body.get("focus")
        enabled = bool(body.get("enabled", True))
        return pm.set_focus(user_id, focus, enabled)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"set focus failed: {e}")

# What it does:
# Read user's current practice state.
@router.get("/focus/{user_id}", response_model=dict)
def get_focus(user_id: str):
    try:
        return pm.get_state(user_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"get focus failed: {e}")

# What it does:
# Micro‑adjustment suggestion (tiny nudge for next brew).
@router.get("/micro/{user_id}", response_model=dict)
def get_micro(user_id: str):
    try:
        return pm.micro_adjustment(user_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"micro failed: {e}")

# What it does:
# Simple A/B variants for quick side‑by‑side tasting.
@router.get("/ab/{user_id}", response_model=dict)
def get_ab(user_id: str):
    try:
        return pm.ab_variants()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"ab variants failed: {e}")

# What it does:
# Attribute user choice back to the learner to reinforce overlays.
@router.post("/ab_feedback/{user_id}", response_model=dict)
def ab_feedback(user_id: str, body: Dict):
    try:
        choice = body.get("choice")
        goal_tags = body.get("goal_tags", []) or []
        ab = pm.ab_variants()
        if choice not in ab:
            return {"ok": False, "msg": "choice must be 'A' or 'B'."}
        overlay = ab[choice]["overlay"]
        edge.register_feedback(goal_tags=goal_tags, var_nudges=overlay, sentiment=+0.5)
        return {"ok": True, "reinforced": overlay, "goal_tags": goal_tags}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"ab feedback failed: {e}")
