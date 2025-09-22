from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException

# Keep routers skinny; all persistence lives in helpers.
from breau_backend.app.services.router_helpers.profile_helpers import (
    get_profile as _get,
    post_profile as _post,
    clear_profile as _clear,
    get_preferences_view as _prefs_view,
    get_preferences_index as _prefs_index,
)

# OCR helper (new)
from breau_backend.app.services.router_helpers.ocr_helpers import (
    save_upload_temp as _save_tmp,
    extract_label_fields as _extract_ocr,
)

router = APIRouter(prefix="/profile", tags=["profile"])

# --- liveness ---
@router.get("/", response_model=Dict[str, str])
def probe() -> Dict[str, str]:
    return {"ok": "profile"}

# --- root GET/POST (delegated) ---
@router.get("")
def get_profile(user_id: str = "local"):
    return _get(user_id)

@router.post("")
def post_profile(payload: Dict[str, Any]):
    """
    Upsert-style: accepts the full profile object and persists it.
    """
    return _post(payload)

# --- current alias (delegated) ---
@router.get("/current")
def get_profile_current(user_id: str = "local"):
    return _get(user_id)

@router.post("/current")
def post_profile_current(payload: Dict[str, Any]):
    return _post(payload)

@router.delete("/current", response_model=Dict[str, bool])
def clear_profile() -> Dict[str, bool]:
    return _clear()

# --- preferences (delegated) ---
@router.get("/preferences/{user_id}")
def get_preferences_readonly(user_id: str):
    """Personalizer snapshot view (trait_response, note_sensitivity, etc.)."""
    return _prefs_view(user_id)

@router.get("/preferences_index")
def get_preferences_index(limit: int = 100, offset: int = 0):
    """Indexed mirror (fast QA view)."""
    return _prefs_index(limit=limit, offset=offset)

# --- OCR (new) ---
@router.post("/ocr")
async def profile_ocr(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"Expected image/*, got {file.content_type!r}")
    path = _save_tmp(file.filename or "label.jpg", await file.read())
    return _extract_ocr(path)
