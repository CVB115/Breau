from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter

# File-based, self-contained helpers.
from breau_backend.app.services.router_helpers.sessions_helpers import (
    list_all as _list_all,
    read_one as _read_one,
    drop_one as _drop_one,
    create_one as _create_one,   # new
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.get("/")
def probe() -> dict[str, str]:
    return {"ok": "sessions"}

@router.get("/list")
def get_sessions() -> dict[str, Any]:
    return _list_all()

@router.get("/{sid}")
def get_session(sid: str) -> dict[str, Any]:
    return _read_one(sid)

@router.delete("/{sid}")
def drop_session(sid: str) -> dict[str, Any]:
    return _drop_one(sid)

# --- new: create ---
@router.post("/create")
def create_session(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persist a session snapshot and return {session_id}.
    doc may include: user_id, bean_id, gear_combo_id, session_plan, pours, rating
    """
    return _create_one(doc)
