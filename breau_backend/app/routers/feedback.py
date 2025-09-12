# breau_backend/app/routers/feedback.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from breau_backend.app.models.feedback import FeedbackIn
from breau_backend.app.services.learning.feedback_flow import handle_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])

# What it does:
# Persist a feedback session, derive features, and update learners
# (edge, personalizer, shadow, bandit, evaluator). Also imprints bandit
# decision, trains the surrogate, and updates metrics; warm-up gated.
@router.post("", response_model=dict)
def submit_feedback(payload: FeedbackIn):
    try:
        return handle_feedback(payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"submit feedback failed: {e}")
