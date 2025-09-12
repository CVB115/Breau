from __future__ import annotations
from fastapi import APIRouter
from typing import Any

# Self-contained metrics readers (read from DATA_DIR/metrics/*)
from breau_backend.app.services.router_helpers.dash_helpers import (
    overview as _overview,
    progress as _progress,
)

router = APIRouter(prefix="/dash", tags=["dash"])

# What it does: liveness for dashboards.
@router.get("/")
def probe() -> dict[str, str]:
    return {"ok": "dash"}

# What it does: global dashboard snapshot (alignment, learning gain, etc.).
@router.get("/overview")
def overview() -> dict[str, Any]:
    return _overview()

# What it does: very light rollup of per-user progress counts.
@router.get("/progress")
def progress() -> dict[str, Any]:
    return _progress()
