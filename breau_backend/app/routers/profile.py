from __future__ import annotations
from fastapi import APIRouter
from typing import Dict, Any

# Keep routers skinny; all persistence lives in helpers.
from breau_backend.app.services.router_helpers.profile_helpers import (
    get_profile as _get,
    post_profile as _post,
    clear_profile as _clear,
    get_preferences_view as _prefs_view,
    get_preferences_index as _prefs_index,
)

router = APIRouter(prefix="/profile", tags=["profile"])

# Liveness check for this router (useful in smoke tests).
@router.get("/")
def probe() -> Dict[str, str]:
    return {"ok": "profile"}

# Upsert current profile – tests call POST /profile (root).
@router.post("", response_model=Dict[str, Any])
def post_profile_root(p: Dict[str, Any]) -> Dict[str, Any]:
    return _post(p)

# Read current profile – allow GET /profile (root).
@router.get("", response_model=Dict[str, Any])
def get_profile_root() -> Dict[str, Any]:
    return _get()

# Optional canonical endpoints (kept for compatibility).
@router.post("/current", response_model=Dict[str, Any])
def post_profile(p: Dict[str, Any]) -> Dict[str, Any]:
    return _post(p)

@router.get("/current", response_model=Dict[str, Any])
def get_profile() -> Dict[str, Any]:
    return _get()

@router.delete("/current", response_model=Dict[str, bool])
def clear_profile() -> Dict[str, bool]:
    return _clear()

# --- Read-only preferences endpoints (delegate to helpers) ---
@router.get("/preferences/{user_id}")
def get_preferences_readonly(user_id: str):
    """Personalizer snapshot view (trait_response, note_sensitivity, etc.)."""
    return _prefs_view(user_id)

@router.get("/preferences_index")
def get_preferences_index(limit: int = 100, offset: int = 0):
    """Indexed mirror (fast QA view)."""
    return _prefs_index(limit=limit, offset=offset)
