# breau_backend/app/routers/feedback.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from pathlib import Path
import json, os
from typing import Dict, Any

from breau_backend.app.models.feedback import FeedbackIn
from breau_backend.app.services.learning.feedback_flow import handle_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])

# ---------- small file I/O helpers (reuse the same folder as sessions) ----------
DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
SESSIONS_DIR = DATA_DIR / "history" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def _session_path(sid: str) -> Path:
    return SESSIONS_DIR / f"{sid}.json"

def _read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

# -----------------------------------------------------------------------------
# Unified feedback → learning (kept as-is)
# -----------------------------------------------------------------------------
@router.post("", response_model=dict)
def submit_feedback(payload: FeedbackIn):
    try:
        return handle_feedback(payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"submit feedback failed: {e}")

# -----------------------------------------------------------------------------
# NEW: Quick “Suggest → Rate” (tolerant, offline-friendly)
# POST /api/feedback/{session_id}/suggest
# Body: { suggest_rating: number, suggest_comment?: string }
# Writes a light stamp into the same session file under: session.feedback.suggest_*
# -----------------------------------------------------------------------------
@router.post("/{session_id}/suggest", response_model=dict)
def submit_suggest_rating(session_id: str, body: Dict[str, Any]):
    sid = (session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id missing")

    p = _session_path(sid)
    if not p.exists():
        raise HTTPException(status_code=404, detail="session not found")

    js = _read_json(p, default={}) or {}
    fb = js.setdefault("feedback", {})
    # Accept 1–5 (allow halves); tolerate strings
    try:
        rating = body.get("suggest_rating")
        rating = None if rating is None else float(rating)
    except Exception:
        rating = None
    comment = body.get("suggest_comment")
    if rating is not None:
        fb["suggest_rating"] = rating
    if isinstance(comment, str):
        fb["suggest_comment"] = comment.strip()

    _write_json(p, js)
    return {"ok": True, "session_id": sid}
