from __future__ import annotations
from fastapi import APIRouter
from typing import Any

# File-based, self-contained helpers (no external services required).
from breau_backend.app.services.router_helpers.sessions_helpers import (
    list_all as _list_all,
    read_one as _read_one,
    drop_one as _drop_one,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

# What it does: liveness for sessions.
@router.get("/")
def probe() -> dict[str, str]:
    return {"ok": "sessions"}

# What it does: list recorded sessions (id, user_id, size, mtime); newest first.
@router.get("/list")
def get_sessions() -> dict[str, Any]:
    return _list_all()

# What it does: read one session by ID (supports `{user}__{sid}` or `{sid}` filenames).
@router.get("/{sid}")
def get_session(sid: str) -> dict[str, Any]:
    return _read_one(sid)

# What it does: delete one session by ID.
@router.delete("/{sid}")
def drop_session(sid: str) -> dict[str, Any]:
    return _drop_one(sid)
