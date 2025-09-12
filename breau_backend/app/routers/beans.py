from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from typing import Any

from breau_backend.app.schemas import BeanListOut
from breau_backend.app.services.data_stores.beans import (
    list_beans, upsert_bean, delete_bean, import_beans_json, export_beans_json
)

router = APIRouter(prefix="/library/beans", tags=["library"])

# What it does:
# List beans in the library (optional query filter).
@router.get("/", response_model=BeanListOut)
def get_beans(q: str | None = None) -> BeanListOut:
    try:
        return list_beans(query=q)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"list beans failed: {e}")

# What it does:
# Create or update a bean entry (idempotent).
@router.post("/")
def post_bean(bean: dict[str, Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "bean": upsert_bean(bean)}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"upsert bean failed: {e}")

# What it does:
# Delete a bean by id or alias.
@router.delete("/{bean_id}")
def remove_bean(bean_id: str) -> dict[str, Any]:
    try:
        delete_bean(bean_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"delete bean failed: {e}")

# What it does:
# Bulk import beans from a JSON payload (array or mapping).
@router.post("/import")
def import_beans(payload: Any) -> dict[str, Any]:
    try:
        n = import_beans_json(payload)
        return {"ok": True, "imported": n}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"import beans failed: {e}")

# What it does:
# Export all beans as JSON.
@router.get("/export")
def export_beans() -> dict[str, Any]:
    try:
        return export_beans_json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"export beans failed: {e}")
