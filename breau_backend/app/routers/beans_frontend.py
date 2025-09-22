# app/routers/beans_frontend.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from uuid import uuid4

# Optional delegation into your helpers (preferred)
_list_beans = _upsert_bean = _get_bean = _update_bean = _delete_bean = None
try:
    from breau_backend.app.services.router_helpers.profile_helpers import (
        list_beans as _list_beans,
        upsert_bean as _upsert_bean,
        get_bean as _get_bean,
        update_bean as _update_bean,
        delete_bean as _delete_bean,
    )
except Exception:
    try:
        from app.services.router_helpers.profile_helpers import (
            list_beans as _list_beans,
            upsert_bean as _upsert_bean,
            get_bean as _get_bean,
            update_bean as _update_bean,
            delete_bean as _delete_bean,
        )
    except Exception:
        pass  # fall back to in-memory below

router = APIRouter(prefix="/profile", tags=["beans"])

# ---------------- In-memory fallback (only if helpers missing) ----------------
_BEANS_BY_USER: Dict[str, Dict[str, Dict[str, Any]]] = {}  # user -> id -> bean


class Bean(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    roaster: Optional[str] = None
    origin: Optional[str] = None
    process: Optional[str] = None
    variety: Optional[str] = None
    roast_level: Optional[str] = None
    harvest: Optional[str] = None
    altitude_m: Optional[float] = None
    notes: Optional[str] = None
    inventory_g: Optional[float] = None
    density_g_per_l: Optional[float] = None  # if you capture density
    # add any extra fields you already use on FE


def _bucket(user_id: str) -> Dict[str, Dict[str, Any]]:
    return _BEANS_BY_USER.setdefault(user_id, {})


# ----------------------------------- Routes ----------------------------------- #

@router.get("/{user_id}/beans")
def list_user_beans(user_id: str) -> Dict[str, Any]:
    if callable(_list_beans):
        try:
            items = _list_beans(user_id)  # expected to return List[dict]
            return {"beans": items or []}
        except Exception as e:
            raise HTTPException(500, f"failed to list beans: {e}")

    # Fallback: in-memory
    items = list(_bucket(user_id).values())
    return {"beans": items}


@router.post("/{user_id}/beans")
def create_or_upsert(user_id: str, bean: Bean) -> Dict[str, Any]:
    if callable(_upsert_bean):
        try:
            doc = _upsert_bean(user_id, bean.model_dump(exclude_none=True))
            return {"bean": doc}
        except Exception as e:
            raise HTTPException(500, f"failed to save bean: {e}")

    # Fallback: in-memory
    bucket = _bucket(user_id)
    bean_id = bean.id or uuid4().hex
    doc = {**(bucket.get(bean_id) or {}), **bean.model_dump(exclude_none=True), "id": bean_id}
    bucket[bean_id] = doc
    return {"bean": doc}


@router.get("/{user_id}/beans/{bean_id}")
def get_user_bean(user_id: str, bean_id: str) -> Dict[str, Any]:
    if callable(_get_bean):
        try:
            doc = _get_bean(user_id, bean_id)
            if not doc:
                raise HTTPException(404, "bean not found")
            return {"bean": doc}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"failed to get bean: {e}")

    # Fallback: in-memory
    doc = _bucket(user_id).get(bean_id)
    if not doc:
        raise HTTPException(404, "bean not found")
    return {"bean": doc}


@router.put("/{user_id}/beans/{bean_id}")
def update_user_bean(user_id: str, bean_id: str, bean: Bean) -> Dict[str, Any]:
    if callable(_update_bean):
        try:
            doc = _update_bean(user_id, bean_id, bean.model_dump(exclude_none=True))
            return {"bean": doc}
        except Exception as e:
            raise HTTPException(500, f"failed to update bean: {e}")

    # Fallback: in-memory
    bucket = _bucket(user_id)
    if bean_id not in bucket:
        raise HTTPException(404, "bean not found")
    doc = {**bucket[bean_id], **bean.model_dump(exclude_none=True), "id": bean_id}
    bucket[bean_id] = doc
    return {"bean": doc}


@router.delete("/{user_id}/beans/{bean_id}")
def delete_user_bean(user_id: str, bean_id: str) -> Dict[str, Any]:
    if callable(_delete_bean):
        try:
            _delete_bean(user_id, bean_id)
            return {"ok": True}
        except Exception as e:
            raise HTTPException(500, f"failed to delete bean: {e}")

    # Fallback: in-memory
    bucket = _bucket(user_id)
    if bean_id not in bucket:
        raise HTTPException(404, "bean not found")
    del bucket[bean_id]
    return {"ok": True}
