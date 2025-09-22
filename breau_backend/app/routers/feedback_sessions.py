# app/routers/feedback_sessions.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
from pathlib import Path
import json, os

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

router = APIRouter(prefix="/feedback", tags=["feedback"])

class SuggestBody(BaseModel):
    suggest_rating: float
    suggest_comment: Optional[str] = None

class CupBody(BaseModel):
    rating: Optional[float] = None
    perceived_notes: Optional[list[str]] = None
    comments: Optional[str] = None
    sliders: Optional[Dict[str, float]] = None

@router.post("/{session_id}/suggest")
def quick_suggest(session_id: str, body: SuggestBody):
    p = _session_path(session_id)
    if not p.exists():
        raise HTTPException(404, "session not found")
    js = _read_json(p, default={}) or {}
    fb = js.setdefault("feedback", {})
    fb["suggest_rating"] = float(body.suggest_rating)
    fb["suggest_comment"] = (body.suggest_comment or "").strip()
    _write_json(p, js)
    return {"ok": True}

@router.post("/{session_id}")
def cup_assess(session_id: str, body: CupBody):
    p = _session_path(session_id)
    if not p.exists():
        raise HTTPException(404, "session not found")
    js = _read_json(p, default={}) or {}
    fb = js.setdefault("feedback", {})
    if body.rating is not None: fb["rating"] = float(body.rating)
    if body.perceived_notes is not None: fb["perceived_notes"] = list(body.perceived_notes)
    if body.comments is not None: fb["comments"] = body.comments
    if body.sliders is not None:
        fb.setdefault("sliders", {}).update({k: float(v) for k, v in body.sliders.items()})
    _write_json(p, js)
    return {"ok": True}
