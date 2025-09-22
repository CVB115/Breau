# app/routers/sessions_frontend.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from uuid import uuid4
from pathlib import Path
import json, time, os

# Optional active gear snapshot
try:
    from breau_backend.app.routers.gear_frontend import _ACTIVE_BY_USER, _COMBOS_BY_USER  # type: ignore
except Exception:
    _ACTIVE_BY_USER, _COMBOS_BY_USER = {}, {}

# Optional grind recommender
try:
    from breau_backend.app.services.router_helpers.grind_recommender import recommend_grind
except Exception:
    recommend_grind = None  # type: ignore

DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
SESSIONS_DIR = DATA_DIR / "history" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def _session_path(sid: str) -> Path:
    return SESSIONS_DIR / f"{sid}.json"

def _read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def now_utc_ts() -> int:
    return int(time.time())

def _norm_style(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    t = str(s).strip().lower()
    if t in ("straight", "center", "centre", "centered"):
        return "center"
    if t in ("spiral", "circle", "swirl", "spiralling", "spiraling"):
        return "spiral"
    return t

def _resolve_gear_for_session(user_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    combo_id = body.get("gear_combo_id")
    if combo_id:
        combo = (_COMBOS_BY_USER.get(user_id) or {}).get(combo_id)
        if combo:
            return combo
        raise HTTPException(404, "gear combo not found")
    if isinstance(body.get("gear"), dict):
        return dict(body["gear"])
    active = _ACTIVE_BY_USER.get(user_id)
    if active:
        return active
    return {
        "label": "Default Combo",
        "brewer": {"name": "Brewer"},
        "grinder": {"name": "Grinder"},
        "filter": {"name": "Filter"},
        "water": {"name": "Water", "temp_c": 96},
    }

def _start_doc(user_id: str, sid: str, mode: str, source: str,
               bean: Optional[dict], gear: dict, recipe: dict) -> dict:
    return {
        "schema_version": "2025-09-18",
        "id": sid,
        "user_id": user_id,
        "created_utc": now_utc_ts(),
        "status": "in_progress",
        "mode": mode or "manual",
        "source": source or "ui",
        "bean": bean,
        "gear": gear,
        "recipe": recipe or {},
        "pours": [],
        "events": [],
        "rating": None,
        "notes": None,
        "finished_utc": None,
        "summary": {
            "bean": (bean or {}).get("name"),
            "roaster": (bean or {}).get("roaster"),
            "brewer": (gear or {}).get("brewer", {}).get("name") if isinstance(gear, dict) else None,
            "dose_g": (recipe or {}).get("dose_g"),
            "water_g": (recipe or {}).get("water_g"),
            "ratio": (recipe or {}).get("ratio"),
        },
    }

def _append_step_file(sid: str, step: Dict[str, Any]) -> None:
    p = _session_path(sid)
    if not p.exists():
        raise HTTPException(status_code=404, detail="session not found")

    js = _read_json(p, default={}) or {}
    s = dict(step or {})
    t = (s.get("type") or s.get("event") or "event").strip().lower()

    if t == "pour":
        to_g = s.get("target_g") or s.get("water_to") or s.get("grams")
        at_ms = s.get("end_ms") or s.get("at_ms") or int(time.time() * 1000)
        style = _norm_style(s.get("style") or s.get("pour_style"))
        js.setdefault("pours", []).append({
            "type": "pour",
            "to_g": float(to_g) if to_g is not None else None,
            "at_ms": int(at_ms),
            "style": style,
            "note": s.get("note") or s.get("comment"),
        })
    elif t == "bloom":
        to_g = s.get("target_g") or s.get("water_g") or s.get("grams")
        at_ms = s.get("end_ms") or s.get("at_ms") or int(time.time() * 1000)
        style = _norm_style(s.get("style") or s.get("pour_style")) or "center"
        js.setdefault("pours", []).append({
            "type": "bloom",
            "to_g": float(to_g) if to_g is not None else None,
            "at_ms": int(at_ms),
            "style": style,
        })
    else:
        at_ms = s.get("at_ms") or int(time.time() * 1000)
        meta = {k: v for k, v in s.items() if k not in ("type", "event", "at_ms")}
        js.setdefault("events", []).append({
            "event": t,
            "at_ms": int(at_ms),
            "meta": meta,
        })

    _write_json(p, js)

def _finish_file(sid: str, rating: Optional[int], notes: Optional[str]) -> None:
    p = _session_path(sid)
    if not p.exists():
        raise HTTPException(status_code=404, detail="session not found")
    js = _read_json(p, default={}) or {}
    js["status"] = "finished"
    js["finished_utc"] = now_utc_ts()
    if rating is not None:
        js["rating"] = rating
    if notes is not None:
        js["notes"] = notes
    _write_json(p, js)

def _list_recent(user_id: str, limit: int) -> List[dict]:
    items: List[dict] = []
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            js = _read_json(path, default={}) or {}
            if (js.get("user_id") or user_id) != user_id:
                continue
            st = path.stat()
            items.append({
                "id": js.get("id") or path.stem,
                "user_id": js.get("user_id") or user_id,
                "mtime": int(getattr(st, "st_mtime", time.time())),
                "created_utc": int(js.get("created_utc") or getattr(st, "st_mtime", time.time())),
                "status": js.get("status") or "unknown",
                "rating": js.get("rating"),
                "summary": js.get("summary") or {},
            })
        except Exception:
            continue
    items.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    return items[:limit]

class StartBody(BaseModel):
    user_id: str
    mode: Optional[str] = "manual"
    source: Optional[str] = "ui"
    bean_id: Optional[str] = None
    bean: Optional[Dict[str, Any]] = None
    recipe: Optional[Dict[str, Any]] = None
    gear_combo_id: Optional[str] = None
    gear: Optional[Dict[str, Any]] = None

class StepBody(BaseModel):
    session_id: str
    step: Dict[str, Any]

class FinishBody(BaseModel):
    session_id: str
    rating: Optional[int] = None
    notes: Optional[str] = None

router = APIRouter(tags=["brew", "history"])

@router.post("/brew/start")
@router.post("/sessions/start")
def start_brew(body: StartBody):
    user_id = (body.user_id or "").strip()
    if not user_id:
        raise HTTPException(400, "missing user_id")

    gear_snapshot = _resolve_gear_for_session(user_id, body.model_dump(exclude_none=True))
    recipe = dict(body.recipe or {})
    bean = body.bean or None

    if recommend_grind:
        try:
            rec = recommend_grind(bean, gear_snapshot)
            recipe.setdefault("grind_target_micron", rec.get("target_micron"))
            recipe.setdefault("grind_setting", rec.get("setting"))
            recipe.setdefault("grind_label", rec.get("label"))
            if rec.get("scale"):
                recipe.setdefault("grind_scale", rec.get("scale"))
        except Exception:
            pass

    sid = uuid4().hex
    doc = _start_doc(user_id, sid, body.mode or "manual", body.source or "ui", bean, gear_snapshot, recipe)
    _write_json(_session_path(sid), doc)
    return {"session_id": sid}

@router.post("/brew/step")
@router.post("/sessions/step")
def log_step(body: StepBody):
    _append_step_file(body.session_id, dict(body.step or {}))
    return {"ok": True}

@router.post("/brew/finish")
@router.post("/sessions/finish")
def finish_brew(body: FinishBody):
    _finish_file(body.session_id, body.rating, body.notes)
    return {"ok": True}

@router.get("/brew/session/{user_id}/{session_id}")
def get_session(user_id: str, session_id: str):
    p = _session_path(session_id)
    if not p.exists():
        return {"session": None}
    return {"session": _read_json(p, default=None)}

@router.get("/history/{user_id}")
@router.get("/brew/history/{user_id}")
def history(user_id: str, limit: int = Query(10, ge=1, le=200)):
    return {"sessions": _list_recent(user_id, limit)}
