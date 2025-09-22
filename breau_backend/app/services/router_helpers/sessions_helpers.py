# breau_backend/app/services/router_helpers/sessions_helpers.py
from __future__ import annotations
import os, json
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone

from ...config.paths import DATA_DIR
from ...utils.storage import ensure_dir
from ...utils.profile_store import append_session  # reuse your existing writer

def enrich_session(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(doc, dict):
        return {"error": "invalid_session"}

    # Basic aliases/consistency
    sid = str(doc.get("id") or doc.get("session_id") or "").strip()
    created_utc = int(doc.get("created_utc") or 0)  # stored as seconds epoch
    finished_utc = doc.get("finished_utc")
    finished_utc = int(finished_utc) if isinstance(finished_utc, (int, float, str)) and str(finished_utc).isdigit() else None

    def _iso(ts: int | None) -> str | None:
        if not ts: return None
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()

    # Start with a shallow clone so unknown keys are preserved
    out = dict(doc)
    out["session_id"]  = sid
    out["started_at"]  = _iso(created_utc)
    out["finished_at"] = _iso(finished_utc) if finished_utc else None
    out["duration_ms"] = (max(0, (finished_utc - created_utc)) * 1000) if (finished_utc and created_utc) else None

    # Normalize recipe and bloom
    recipe = dict(out.get("recipe") or {})
    pours  = list(out.get("pours") or [])
    events = list(out.get("events") or [])

    # Derive total_water_g if absent from max cumulative to_g
    if recipe.get("total_water_g") is None:
        try:
            max_to = max([p.get("to_g") or 0 for p in pours], default=0)
            if max_to:
                recipe["total_water_g"] = float(max_to)
        except Exception:
            pass

    # Extract bloom from the first bloom pour, if present
    bloom = dict(recipe.get("bloom") or {})
    try:
        first_bloom = next((p for p in pours if (p.get("type") or "").lower() == "bloom"), None)
    except Exception:
        first_bloom = None
    if first_bloom:
        bloom["water_g"] = first_bloom.get("to_g")
        # relative time will be set below once we compute t0; keep raw ms for now
        bloom["_at_ms"] = first_bloom.get("at_ms")
        # no temp available in stored pours; leave temp_c absent
        recipe["bloom"] = bloom
    out["recipe"] = recipe

    # Build timeline[] from pours (cumulative → incremental) and events
    # time base: earliest at_ms across pours/events
    all_ms = []
    try:
        all_ms += [int(p.get("at_ms")) for p in pours if p.get("at_ms") is not None]
    except Exception:
        pass
    try:
        all_ms += [int(e.get("at_ms")) for e in events if e.get("at_ms") is not None]
    except Exception:
        pass
    t0 = min(all_ms) if all_ms else None

    def _rel_s(ms: int | None) -> float | None:
        if ms is None or t0 is None: return None
        return max(0.0, (int(ms) - int(t0)) / 1000.0)

    timeline: List[Dict[str, Any]] = []
    # pours: convert cumulative to per-step deltas
    prev_to = 0.0
    pour_rows: List[Dict[str, Any]] = []
    for i, p in enumerate(sorted([pp for pp in pours if (pp.get("at_ms") is not None)], key=lambda x: x.get("at_ms"))):
        to_g = float(p.get("to_g") or 0.0)
        delta = max(0.0, to_g - prev_to)
        prev_to = to_g
        end_s = _rel_s(p.get("at_ms"))
        # start_s heuristic: last row's end or same as end if unknown
        start_s = pour_rows[-1]["end_s"] if (pour_rows and pour_rows[-1].get("end_s") is not None) else end_s
        row = {
            "index": len(pour_rows),
            "start_s": start_s,
            "end_s": end_s,
            "water_g": delta if delta > 0 else None,
            "temp_c": None,
            "agitation": None,
            "style": p.get("style"),
            "note": p.get("note"),
            "kind": p.get("type") or "pour",
        }
        pour_rows.append(row)

    # events: map to instantaneous timeline points (stir/swirl/etc.)
    event_rows: List[Dict[str, Any]] = []
    for e in sorted([ee for ee in events if (ee.get("at_ms") is not None)], key=lambda x: x.get("at_ms")):
        label = (e.get("event") or "").strip().lower() or "event"
        r = {
            "index": len(pour_rows) + len(event_rows),
            "start_s": _rel_s(e.get("at_ms")),
            "end_s": _rel_s(e.get("at_ms")),
            "water_g": None,
            "temp_c": None,
            "agitation": label if label in ("stir","swirl","agitate","tap","shake") else None,
            "style": None,
            "note": (e.get("meta") or {}).get("note") if isinstance(e.get("meta"), dict) else None,
            "kind": "event",
        }
        event_rows.append(r)

    # Interleave by time (pours & events already sorted by at_ms)
    # To keep it simple (and stable for UI), just concatenate: pours first, then events by time;
    # if you prefer exact chronological, you can merge-join by start_s.
    timeline = pour_rows + event_rows

    # Populate bloom.time_s relative now that t0 is known
    if "bloom" in recipe and isinstance(recipe.get("bloom"), dict):
        at_ms = recipe["bloom"].pop("_at_ms", None)
        if at_ms is not None:
            recipe["bloom"]["time_s"] = _rel_s(at_ms)

    out["timeline"] = timeline
    return out

def _sessions_dir() -> Path:
    p = (DATA_DIR / "history" / "sessions")
    ensure_dir(p)
    return p

def _read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def list_all() -> Dict[str, Any]:
    """
    Return newest-first list of sessions: { sessions: [{id,user_id,size,mtime,created_utc,rating?}, ...] }
    """
    root = _sessions_dir()
    items: List[Dict[str, Any]] = []
    for p in root.glob("*.json"):
        try:
            st = p.stat()
            js = _read_json(p, default={}) or {}
            items.append({
                "id": js.get("id") or p.stem,   # id inside file or filename
                "user_id": js.get("user_id"),
                "size": st.st_size,
                "mtime": int(st.st_mtime),
                "created_utc": js.get("created_utc"),
                "rating": js.get("rating"),
            })
        except Exception:
            continue
    items.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    return {"sessions": items}

def read_one(sid: str) -> Dict[str, Any]:
    root = _sessions_dir()
    candidates = [root / f"{sid}.json"] + list(root.glob(f"*__{sid}.json"))
    path = next((p for p in candidates if p.exists()), None)
    if not path:
        return {"error": "not_found"}
    data = _read_json(path, default=None)
    if data is None:
        return {"error": "read_failed"}
    enriched = enrich_session(data)
    return {"session": enriched, "path": str(path)}

def drop_one(sid: str) -> Dict[str, Any]:
    root = _sessions_dir()
    candidates = [root / f"{sid}.json"] + list(root.glob(f"*__{sid}.json"))
    path = next((p for p in candidates if p.exists()), None)
    if not path:
        return {"error": "not_found"}
    path.unlink(missing_ok=True)
    return {"ok": True, "deleted": path.name}

# --- new: create session ---
def create_one(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts a dict with keys like:
    { user_id, bean_id?, gear_combo_id?, session_plan?, pours?, rating? }
    Writes a JSON file via append_session and returns {session_id}.
    """
    user_id = (doc or {}).get("user_id") or "local"
    # let append_session assign id + created_utc if missing
    sid_path = append_session(user_id, doc or {})
    # extract id from filename
    sid = Path(sid_path).stem.split("__", 1)[-1] if "__" in Path(sid_path).stem else Path(sid_path).stem
    return {"session_id": sid}
