# app/routers/gear_frontend.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from uuid import uuid4

# --- tolerant imports (support both breau_backend.app.* and app.*) ---
try:
    from breau_backend.app.services.gear_norm import normalize_gear_combo  # flexible normalizer
except Exception:
    try:
        from app.services.gear_norm import normalize_gear_combo
    except Exception:
        normalize_gear_combo = None  # type: ignore

# Optional delegation into your profile helpers (preferred if present)
_get_active_gear = _set_active_gear = _list_gear_combos = _create_gear_combo = None
try:
    from breau_backend.app.services.router_helpers.profile_helpers import (
        get_active_gear as _get_active_gear,
        set_active_gear as _set_active_gear,
        list_gear_combos as _list_gear_combos,
        create_gear_combo as _create_gear_combo,
    )
except Exception:
    try:
        from app.services.router_helpers.profile_helpers import (
            get_active_gear as _get_active_gear,
            set_active_gear as _set_active_gear,
            list_gear_combos as _list_gear_combos,
            create_gear_combo as _create_gear_combo,
        )
    except Exception:
        pass  # fall back to in-memory below

router = APIRouter(prefix="/profile", tags=["gear"])

# ---------------- In-memory fallback (used only if helpers missing) ----------------
_ACTIVE_BY_USER: Dict[str, Dict[str, Any]] = {}
_COMBOS_BY_USER: Dict[str, Dict[str, Dict[str, Any]]] = {}  # user -> id -> combo


class GearCombo(BaseModel):
    id: Optional[str] = None
    label: Optional[str] = None
    brewer: Optional[Dict[str, Any]] = None
    grinder: Optional[Dict[str, Any]] = None
    filter: Optional[Dict[str, Any]] = None
    water: Optional[Dict[str, Any]] = None


def _norm_combo(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize any incoming payload shape into a canonical combo dict.
    """
    if normalize_gear_combo is None:
        raise HTTPException(500, "gear normalizer unavailable")
    combo = normalize_gear_combo(body)
    if not combo:
        raise HTTPException(400, "invalid gear payload")
    return combo


# ----------------------------------- Routes ----------------------------------- #

@router.get("/{user_id}/gear/active")
def get_active(user_id: str) -> Dict[str, Any]:
    # Prefer your helper if available
    if callable(_get_active_gear):
        try:
            return {"gear": _get_active_gear(user_id)}
        except Exception as e:
            raise HTTPException(500, f"failed to read active gear: {e}")

    # Fallback: in-memory
    return {"gear": _ACTIVE_BY_USER.get(user_id)}


@router.post("/{user_id}/gear/active")
def set_active(user_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Body can be:
      - {"gear_combo_id": "..."} → load saved combo and set active
      - {"gear": {...}} or {"combo": {...}} or top-level fields → normalize & set active
    """
    combo_id = body.get("gear_combo_id")
    # Prefer your helper if available
    if callable(_set_active_gear):
        try:
            if combo_id:
                gear = _set_active_gear(user_id, combo_id=combo_id, gear=None)
                return {"gear": gear}
            # normalize then set
            gear = _norm_combo(body)
            gear = _set_active_gear(user_id, combo_id=None, gear=gear)
            return {"gear": gear}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"failed to set active gear: {e}")

    # Fallback: in-memory
    if combo_id:
        combo = (_COMBOS_BY_USER.get(user_id) or {}).get(combo_id)
        if not combo:
            raise HTTPException(404, "combo not found")
        _ACTIVE_BY_USER[user_id] = combo
        return {"gear": combo}

    gear = _norm_combo(body)
    _ACTIVE_BY_USER[user_id] = gear
    return {"gear": gear}


@router.get("/{user_id}/gear/combos")
def list_combos(user_id: str) -> Dict[str, Any]:
    if callable(_list_gear_combos):
        try:
            combos = _list_gear_combos(user_id)
            return {"combos": combos or []}
        except Exception as e:
            raise HTTPException(500, f"failed to list combos: {e}")

    # Fallback: in-memory
    combos = list((_COMBOS_BY_USER.get(user_id) or {}).values())
    return {"combos": combos}


@router.post("/{user_id}/gear/combos")
def create_combo(user_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    if callable(_create_gear_combo):
        try:
            combo = _norm_combo(body)
            return {"combo": _create_gear_combo(user_id, gear=combo)}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"failed to create combo: {e}")

    # Fallback: in-memory
    combo = _norm_combo(body)
    cid = combo.get("id") or uuid4().hex
    combo["id"] = cid
    bucket = _COMBOS_BY_USER.setdefault(user_id, {})
    bucket[cid] = combo
    return {"combo": combo}
