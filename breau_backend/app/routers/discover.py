from __future__ import annotations
from fastapi import APIRouter
from typing import Any

# Self-contained discovery helpers (read DATA_DIR/library/*).
from breau_backend.app.services.router_helpers.discover_helpers import (
    find_notes as _find_notes,
    find_beans as _find_beans,
    find_goals as _find_goals,
)

router = APIRouter(prefix="/discover", tags=["discover"])

# What it does: liveness for discovery routes.
@router.get("/")
def probe() -> dict[str, str]:
    return {"ok": "discover"}

# What it does: toy full‑text search over notes library (if present).
@router.get("/notes")
def find_notes(q: str) -> dict[str, Any]:
    return _find_notes(q)

# What it does: simple bean search by id/aliases/origin/process/roast.
@router.get("/beans")
def find_beans(q: str | None = None) -> dict[str, Any]:
    return _find_beans(q)

# What it does: return canonical goal tags (or a small default set).
@router.get("/goals")
def find_goals() -> dict[str, Any]:
    return _find_goals()
