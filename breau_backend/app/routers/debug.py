from __future__ import annotations
from fastapi import APIRouter
from typing import Any

# Self-contained debug helpers (env + basic info).
from breau_backend.app.services.router_helpers.debug_helpers import (
    probe as _probe,
    get_trace as _trace,
    ping as _ping,
)

router = APIRouter(prefix="/debug", tags=["debug"])

# What it does: health + minimal environment info.
@router.get("/")
def probe() -> dict[str, Any]:
    return _probe()

# What it does: last suggestion trace (placeholder unless you wire tracing).
@router.get("/trace")
def get_trace() -> dict[str, Any]:
    return _trace()

# What it does: ping external/local dependencies (placeholder OK).
@router.get("/ping")
def ping() -> dict[str, Any]:
    return _ping()
