from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from typing import Dict
from ..services.learning.optimizer import Planner, PlannerConfig
from ..services.learning.surrogate import Surrogate, SurrogateConfig, featurize

router = APIRouter(prefix="/optimize", tags=["optimize"])

DATA_DIR = Path("./data")
SUR_DIR = DATA_DIR / "models" / "surrogate"

planner = Planner(PlannerConfig(model_dir=SUR_DIR))
sur = Surrogate(SurrogateConfig(model_dir=SUR_DIR))

# What it does:
# Suggest small protocol deltas; also return surrogate's before/after score.
@router.post("/plan", response_model=dict)
def plan(body: Dict):
    try:
        user_id = body.get("user_id")
        goal_tags = body.get("goal_tags", [])
        context = body.get("context", {})
        protocol = body.get("protocol", {"temperature_c": 92, "grind_label": "medium", "agitation_overall": "moderate"})

        delta = planner.suggest(user_id, goal_tags, context, protocol)

        # Rough expected gain with the surrogate model
        x0 = featurize(context, protocol, goal_tags)
        y0 = sur.predict(user_id, x0)

        p1 = dict(protocol)
        if "temperature_c" in p1 and "temp_delta" in delta:
            p1["temperature_c"] = float(p1["temperature_c"]) + float(delta["temp_delta"])
        if "grind_delta" in delta:
            p1["grind_label"] = "fine" if delta["grind_delta"] < 0 else ("coarse" if delta["grind_delta"] > 0 else "medium")
        if "agitation_delta" in delta:
            p1["agitation_overall"] = "gentle" if delta["agitation_delta"] < 0 else ("high" if delta["agitation_delta"] > 0 else "moderate")

        y1 = sur.predict(user_id, featurize(context, p1, goal_tags))
        return {"ok": True, "delta": delta, "pred_before": y0, "pred_after": y1}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"optimize plan failed: {e}")
