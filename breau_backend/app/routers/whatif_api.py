from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from typing import Dict
from ..services.learning.surrogate import Surrogate, SurrogateConfig, featurize

router = APIRouter(prefix="/whatif", tags=["whatif"])

DATA_DIR = Path("./data")
SUR_DIR = DATA_DIR / "models" / "surrogate"
sur = Surrogate(SurrogateConfig(model_dir=SUR_DIR))

# What it does:
# Predict effect of a proposed delta on the surrogate model (before/after).
@router.post("/predict", response_model=dict)
def predict(body: Dict):
    try:
        user_id = body.get("user_id")
        goal_tags = body.get("goal_tags", [])
        context = body.get("context", {})
        protocol = body.get("protocol", {"temperature_c": 92, "grind_label": "medium", "agitation_overall": "moderate"})
        delta = body.get("delta", {})  # {"temp_delta": +0.3, "grind_delta": -0.1, ...}

        x0 = featurize(context, protocol, goal_tags)
        y0 = sur.predict(user_id, x0)

        p1 = dict(protocol)
        if "temp_delta" in delta:
            p1["temperature_c"] = float(p1["temperature_c"]) + float(delta["temp_delta"])
        if "grind_delta" in delta:
            p1["grind_label"] = "fine" if delta["grind_delta"] < 0 else ("coarse" if delta["grind_delta"] > 0 else "medium")
        if "agitation_delta" in delta:
            p1["agitation_overall"] = "gentle" if delta["agitation_delta"] < 0 else ("high" if delta["agitation_delta"] > 0 else "moderate")

        y1 = sur.predict(user_id, featurize(context, p1, goal_tags))
        return {"ok": True, "delta": delta, "before": y0, "after": y1}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"what-if predict failed: {e}")
