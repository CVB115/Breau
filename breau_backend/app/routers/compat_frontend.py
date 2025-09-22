# breau_backend/app/routers/compat_frontend.py
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Any, Dict, List, Optional
from pathlib import Path
import os, json, time, secrets

import logging
logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["compat-fe"])

# ---------- bring in YOUR OCR helpers (correct names) ----------
try:
    from breau_backend.app.services.router_helpers.ocr_helpers import (
        save_upload_temp as _save_tmp,          # (filename:str, content:bytes) -> Path
        extract_label_fields as _extract_fields # (lines: List[str]) -> Dict[str, Any]
    )
except Exception:
    _save_tmp = None
    _extract_fields = None

# ---------- simple file-based storage for dev ----------
DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()

def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def _profiles_dir() -> Path:
    return _ensure_dir(DATA_DIR / "profiles")

def _user_dir(uid: str) -> Path:
    safe = "".join(ch for ch in (uid or "local") if ch.isalnum() or ch in ("-", "_")) or "local"
    return _ensure_dir(_profiles_dir() / safe)

def _beans_path(uid: str) -> Path:
    return _user_dir(uid) / "beans.json"

def _sessions_dir() -> Path:
    return _ensure_dir(DATA_DIR / "history" / "sessions")

def _session_path(sid: str) -> Path:
    return _sessions_dir() / f"{sid}.json"

def _read_json(p: Path, default: Any = None) -> Any:
    try:
        if p.exists(): return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _write_json(p: Path, obj: Any):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

# =====================================================================
# OCR — FE calls POST /ocr/extract with an image; we return {text, fields}
# =====================================================================
@router.post("/ocr/extract")
async def ocr_extract(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"Expected image/*, got {file.content_type!r}")

    content = await file.read()
    saved_path: Optional[Path] = None
    if _save_tmp:
        try:
            saved_path = _save_tmp(file.filename or "label.jpg", content)
        except Exception:
            saved_path = None

    # We don't have a text-OCR function here; return empty text but try to parse fields
    fields: Dict[str, Any] = {}
    if _extract_fields:
        try:
            # Your helper appears to take a list of text lines. With no OCR, pass [].
            fields = _extract_fields([]) or {}
        except Exception:
            fields = {}

    return {
        "text": "",           # no OCR text yet (you can wire a real OCR later)
        "fields": {
            "name": fields.get("name"),
            "roaster": fields.get("roaster"),
            "origin": fields.get("origin"),
            "process": fields.get("process"),
            "variety": fields.get("variety"),
            "notes": fields.get("notes"),
            "roast_level": fields.get("roast_level"),
        },
        "raw": {
            "saved_path": str(saved_path) if saved_path else None,
        },
    }

# =====================================================================
# Profile / Beans — FE calls GET/POST /profile/{user}/beans
# =====================================================================
@router.get("/profile/{user_id}/beans")
def list_profile_beans(user_id: str) -> List[Dict[str, Any]]:
    arr = _read_json(_beans_path(user_id), default=[]) or []
    # ensure id field is present
    for it in arr:
        it.setdefault("id", it.get("_id") or f"bean_{secrets.token_hex(4)}")
    return arr

@router.post("/profile/{user_id}/beans")
def upsert_profile_bean(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    arr: List[Dict[str, Any]] = _read_json(_beans_path(user_id), default=[]) or []
    _id = str(payload.get("id") or f"bean_{secrets.token_hex(4)}")

    bean = {
        "id": _id,
        "name": payload.get("name") or "Unnamed Bean",
        "roaster": payload.get("roaster"),
        "origin": payload.get("origin"),
        "process": payload.get("process"),
        "variety": payload.get("variety"),
        "notes": payload.get("notes") or "",
        "roast_level": payload.get("roast_level"),
    }

    # replace by id or insert at top
    idx = next((i for i, it in enumerate(arr) if str(it.get("id")) == _id), None)
    if idx is None:
        arr.insert(0, bean)
    else:
        arr[idx] = bean

    _write_json(_beans_path(user_id), arr)
    return {"ok": True, "bean": bean}

# =====================================================================
# Brew sessions — FE calls these for guide + history
# =====================================================================
@router.post("/brew/start")
def brew_start(payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = payload.get("user_id") or "local"
    sid = payload.get("session_id") or secrets.token_hex(8)
    bean = payload.get("bean")
    gear = payload.get("gear")
    recipe = payload.get("recipe") or {}
    doc = {
        "id": sid,
        "user_id": user_id,
        "created_utc": int(time.time()),
        "status": "in_progress",
        "mode": payload.get("mode") or "manual",
        "source": payload.get("source") or "ui",
        "bean": bean,
        "gear": gear,
        "recipe": recipe,
        "pours": [],
        # tiny summary used by history/home cards
        "summary": {
            "bean": (bean or {}).get("name"),
            "roaster": (bean or {}).get("roaster"),
            "brewer": (gear or {}).get("brewer", {}).get("name") if isinstance(gear, dict) else None,
            "dose_g": recipe.get("dose_g"),
            "water_g": recipe.get("water_g"),
            "ratio": recipe.get("ratio"),
        },
    }
    _write_json(_session_path(sid), doc)
    return {"session_id": sid}

@router.post("/brew/step")
def brew_step(payload: Dict[str, Any]) -> Dict[str, Any]:
    sid = payload.get("session_id")
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    p = _session_path(sid)
    if not p.exists():
        raise HTTPException(status_code=404, detail="session not found")
    js = _read_json(p, default={}) or {}
    pours = js.get("pours") or []
    step = payload.get("step") or {}
    pours.append(step)
    js["pours"] = pours
    _write_json(p, js)
    return {"ok": True, "step_index": len(pours) - 1}

@router.post("/brew/finish")
def brew_finish(payload: Dict[str, Any]) -> Dict[str, Any]:
    sid = payload.get("session_id")
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    p = _session_path(sid)
    if not p.exists():
        raise HTTPException(status_code=404, detail="session not found")
    js = _read_json(p, default={}) or {}
    js["status"] = "finished"
    if "rating" in payload:
        js["rating"] = payload["rating"]
    if "notes" in payload:
        js["notes"] = payload["notes"]
    _write_json(p, js)
    return {"ok": True}

@router.post("/brew/start")
def brew_start(payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = payload.get("user_id") or "local"
    sid = payload.get("session_id") or secrets.token_hex(8)
    bean = payload.get("bean")
    gear = payload.get("gear")
    recipe = payload.get("recipe") or {}
    doc = {
        "id": sid,
        "user_id": user_id,
        "created_utc": int(time.time()),
        "status": "in_progress",
        "mode": payload.get("mode") or "manual",
        "source": payload.get("source") or "ui",
        "bean": bean,
        "gear": gear,
        "recipe": recipe,
        "pours": [],
        # tiny summary used by history/home cards
        "summary": {
            "bean": (bean or {}).get("name"),
            "roaster": (bean or {}).get("roaster"),
            "brewer": (gear or {}).get("brewer", {}).get("name") if isinstance(gear, dict) else None,
            "dose_g": recipe.get("dose_g"),
            "water_g": recipe.get("water_g"),
            "ratio": recipe.get("ratio"),
        },
    }
    _write_json(_session_path(sid), doc)
    return {"session_id": sid}

@router.get("/brew/session/{user_id}/{session_id}")
def brew_session_detail(user_id: str, session_id: str) -> Dict[str, Any]:
    try:
        p = _session_path(session_id)
        if not p.exists():
            return {"session": None}
        js = _read_json(p, default=None)
        if js is None:
            return {"session": None}
        return {"session": js}
    except Exception as e:
        logger.exception("Session detail failed for %s/%s", user_id, session_id)
        return {"session": None}

@router.get("/brew/history/{user_id}")
def brew_history(user_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """Safe, compact history. Never raises—returns [] on any issue."""
    try:
        d = _sessions_dir()  # ensures dir exists
        items: List[Dict[str, Any]] = []
        for p in d.glob("*.json"):
            try:
                js = _read_json(p, default={}) or {}
                if (js.get("user_id") or user_id) != user_id:
                    continue
                st = p.stat()
                # minimal summary so Home can render even if file is sparse
                rec = {
                    "id": js.get("id") or p.stem,
                    "user_id": js.get("user_id") or user_id,
                    "mtime": int(getattr(st, "st_mtime", time.time())),
                    "created_utc": int(js.get("created_utc") or getattr(st, "st_mtime", time.time())),
                    "status": js.get("status") or "unknown",
                    "rating": js.get("rating"),
                    "summary": js.get("summary") or {
                        "bean": (js.get("bean") or {}).get("name"),
                        "roaster": (js.get("bean") or {}).get("roaster"),
                        "brewer": (js.get("gear") or {}).get("brewer", {}).get("name") if isinstance(js.get("gear"), dict) else None,
                        "dose_g": (js.get("recipe") or {}).get("dose_g"),
                        "water_g": (js.get("recipe") or {}).get("water_g"),
                        "ratio": (js.get("recipe") or {}).get("ratio"),
                    },
                }
                items.append(rec)
            except Exception as e:
                logger.warning("Skip bad session file %s: %s", p, e)
                continue

        items.sort(key=lambda x: x.get("mtime", 0), reverse=True)
        if isinstance(limit, int) and limit > 0:
            items = items[:limit]
        return {"sessions": items}
    except Exception as e:
        logger.exception("History failed for user %s", user_id)
        return {"sessions": []}

@router.get("/brew/session/{user_id}/{session_id}")
def brew_session_detail(user_id: str, session_id: str) -> Dict[str, Any]:
    """Safe detail. Returns {'session': None} if missing/corrupt."""
    try:
        p = _session_path(session_id)
        if not p.exists():
            return {"session": None}
        js = _read_json(p, default=None)
        return {"session": js or None}
    except Exception as e:
        logger.exception("Session detail failed for %s/%s", user_id, session_id)
        return {"session": None}