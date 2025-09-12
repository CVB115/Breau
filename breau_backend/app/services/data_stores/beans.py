from __future__ import annotations

import json, os, re, time, uuid
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

from breau_backend.app.config.paths import path_under_data, ensure_data_dir_exists
from .io_utils import atomic_write, read_json

_IO_LOCK = RLock()
_slug_pat = re.compile(r"[^a-z0-9]+")

ensure_data_dir_exists("library")
BEANS_PATH = Path(os.getenv("BREAU_BEAN_PATH", str(path_under_data("library", "beans.json")))).resolve()

def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = _slug_pat.sub("-", s).strip("-")
    return re.sub(r"-{2,}", "-", s)

def _normalize_tags(v):
    if not isinstance(v, list):
        return v
    out, seen = [], set()
    for t in v:
        if t is None:
            continue
        s = str(t).strip().lower()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out

def _normalize_bean_data(d: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(d or {})
    if "alias" in d and d["alias"]:
        d["alias"] = _slugify(str(d["alias"]))
    if "tags" in d:
        d["tags"] = _normalize_tags(d["tags"])
    return d

def _coerce_item(item: Any, now: float) -> Optional[Tuple[str, Dict[str, Any], float, float]]:
    if not isinstance(item, dict):
        return None
    if "data" in item and isinstance(item["data"], dict):
        data = _normalize_bean_data(item["data"])
        rid = str(item.get("id") or data.get("id") or "").strip() or str(uuid.uuid4())
        data["id"] = rid
        ca = float(item.get("created_at") or now)
        ua = float(item.get("updated_at") or now)
        return rid, data, ca, ua
    data = _normalize_bean_data(item)
    rid = str(data.get("id") or "").strip()
    if not rid:
        base = str(data.get("alias") or data.get("name") or data.get("label") or "").strip()
        rid = _slugify(base) if base else str(uuid.uuid4())
        data["id"] = rid
    return rid, data, now, now

def _to_canonical(obj: Any) -> Dict[str, Dict[str, Any]]:
    now = time.time()
    canonical: Dict[str, Dict[str, Any]] = {}

    if isinstance(obj, dict) and not any(k in obj for k in ("beans", "items")):
        for k, v in obj.items():
            if not isinstance(v, dict):
                continue
            if "data" in v and isinstance(v["data"], dict):
                rid = str(v.get("id") or k)
                ca = float(v.get("created_at") or now)
                ua = float(v.get("updated_at") or now)
                data = _normalize_bean_data({**v["data"], "id": rid})
                canonical[rid] = {"id": rid, "created_at": ca, "updated_at": ua, "data": data}
            else:
                coerced = _coerce_item(v, now)
                if coerced:
                    rid, data, ca, ua = coerced
                    canonical[rid] = {"id": rid, "created_at": ca, "updated_at": ua, "data": data}
        return canonical

    if isinstance(obj, dict) and ("beans" in obj or "items" in obj):
        items = obj.get("beans") if "beans" in obj else obj.get("items")
        if isinstance(items, list):
            for it in items:
                coerced = _coerce_item(it, now)
                if coerced:
                    rid, data, ca, ua = coerced
                    canonical[rid] = {"id": rid, "created_at": ca, "updated_at": ua, "data": data}
        return canonical

    if isinstance(obj, list):
        for it in obj:
            coerced = _coerce_item(it, now)
            if coerced:
                rid, data, ca, ua = coerced
                canonical[rid] = {"id": rid, "created_at": ca, "updated_at": ua, "data": data}
        return canonical

    return canonical

def _beans_blob() -> Dict[str, Dict[str, Any]]:
    with _IO_LOCK:
        raw = read_json(BEANS_PATH, default={})
        blob = _to_canonical(raw)
        atomic_write(BEANS_PATH, json.dumps(blob, ensure_ascii=False, indent=2))
        return blob

def _save_beans_blob(blob: Dict[str, Dict[str, Any]]) -> None:
    with _IO_LOCK:
        atomic_write(BEANS_PATH, json.dumps(blob, ensure_ascii=False, indent=2))

def _alias_in_use(blob: Dict[str, Any], alias: str, *, exclude_id: Optional[str] = None) -> bool:
    alias = _slugify(str(alias))
    for bid, rec in blob.items():
        if exclude_id and bid == exclude_id:
            continue
        data = rec.get("data") or {}
        if (data.get("alias") or "").strip().lower() == alias:
            return True
    return False

def create_bean(record: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(record, dict):
        raise TypeError("bean must be a dict")
    now = time.time()
    data = _normalize_bean_data(record)

    rid = str(data.get("id") or "").strip()
    if not rid:
        base = str(data.get("alias") or data.get("name") or data.get("label") or "").strip()
        rid = _slugify(base) if base else str(uuid.uuid4())
        data["id"] = rid

    blob = _beans_blob()
    alias = data.get("alias")
    if alias and _alias_in_use(blob, alias):
        raise ValueError(f"alias already exists: {alias}")
    if rid in blob:
        raise ValueError(f"bean id already exists: {rid}")

    rec = {"id": rid, "created_at": now, "updated_at": now, "data": data}
    blob[rid] = rec
    _save_beans_blob(blob)
    return rec

def get_bean(bean_id: str) -> Dict[str, Any]:
    blob = _beans_blob()
    rec = blob.get(bean_id)
    if not rec:
        raise KeyError(f"bean not found: {bean_id}")
    return rec

def get_bean_by_alias(alias: str) -> Dict[str, Any]:
    a = _slugify(str(alias))
    blob = _beans_blob()
    for rec in blob.values():
        if (rec.get("data") or {}).get("alias") == a:
            return rec
    raise KeyError(f"bean alias not found: {a}")

def update_bean(bean_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(patch, dict):
        raise TypeError("patch must be a dict")
    blob = _beans_blob()
    rec = blob.get(bean_id)
    if not rec:
        raise KeyError(f"bean not found: {bean_id}")

    data = dict(rec.get("data") or {})
    norm = _normalize_bean_data(patch)

    new_alias = norm.get("alias")
    if new_alias is not None:
        if new_alias and _alias_in_use(blob, new_alias, exclude_id=bean_id):
            raise ValueError(f"alias already exists: {new_alias}")
        if not new_alias:
            data.pop("alias", None)
        else:
            data["alias"] = new_alias

    for k, v in norm.items():
        if k in ("id", "alias"):
            continue
        if v is not None:
            data[k] = v

    rec["data"] = data
    rec["updated_at"] = time.time()
    blob[bean_id] = rec
    _save_beans_blob(blob)
    return rec

def list_beans(q: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    qnorm = (q or "").strip().lower()
    blob = _beans_blob()
    rows = list(blob.values())

    if qnorm:
        def match(rec: Dict[str, Any]) -> bool:
            d = rec.get("data") or {}
            hay = " ".join(str(d.get(k, "")) for k in ("alias","roaster","name","origin","variety","process","roast_level")).lower()
            tags = " ".join(d.get("tags", [])).lower() if isinstance(d.get("tags"), list) else ""
            return (qnorm in hay) or (qnorm in tags)
        rows = [r for r in rows if match(r)]

    rows.sort(key=lambda r: r.get("updated_at", 0), reverse=True)
    return rows[: max(1, min(limit, 200))]

def export_beans() -> Dict[str, Any]:
    blob = _beans_blob()
    return {"version": 1, "count": len(blob), "items": list(blob.values())}

def import_beans(payload: Dict[str, Any], mode: str = "merge") -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    items = payload.get("items") or payload.get("beans")
    if not isinstance(items, list):
        raise ValueError("payload.items/beans must be a list")

    blob = _beans_blob()
    if mode == "replace":
        blob = {}

    added = updated = 0
    now = time.time()

    for item in items:
        if isinstance(item, dict) and "data" in item and isinstance(item["data"], dict):
            data = _normalize_bean_data(item["data"])
            id_hint = item.get("id") or data.get("id")
            ca = float(item.get("created_at") or now)
            ua = float(item.get("updated_at") or now)
        elif isinstance(item, dict):
            data = _normalize_bean_data(item)
            id_hint = data.get("id")
            ca = ua = now
        else:
            continue

        alias = data.get("alias")
        target_id = None
        if id_hint and id_hint in blob:
            target_id = id_hint
        elif alias:
            for bid, rec in blob.items():
                if (rec.get("data") or {}).get("alias") == alias:
                    target_id = bid
                    break

        if target_id is None:
            new_id = id_hint or _slugify(str(alias or "")) or str(uuid.uuid4())
            if alias and _alias_in_use(blob, alias):
                alias = f"{_slugify(alias)}-{new_id[:6]}"
                data["alias"] = alias
            blob[new_id] = {"id": new_id, "created_at": ca, "updated_at": ua, "data": {**data, "id": new_id}}
            added += 1
        else:
            rec = blob[target_id]
            if alias and _alias_in_use(blob, alias, exclude_id=target_id):
                alias = f"{_slugify(alias)}-{target_id[:6]}"
                data["alias"] = alias
            merged = rec.get("data", {})
            for k, v in data.items():
                if k == "id":
                    continue
                if v is not None:
                    merged[k] = v
            rec["data"] = merged
            rec["updated_at"] = ua
            blob[target_id] = rec
            updated += 1

    atomic_write(BEANS_PATH, json.dumps(blob, ensure_ascii=False, indent=2))
    return {"ok": True, "mode": mode, "added": added, "updated": updated}
def upsert_bean(bean: Dict[str, Any]) -> Dict[str, Any]:
    """
    Router adapter:
    - If bean.id exists -> update_bean
    - Else -> create_bean
    Returns the canonical record (with id/created_at/updated_at/data).
    """
    bid = str((bean or {}).get("id") or "").strip()
    try:
        if bid:
            # try update; falls back to create if not found
            try:
                return update_bean(bid, bean)
            except KeyError:
                return create_bean(bean)
        else:
            return create_bean(bean)
    except Exception:
        # last resort: create path
        return create_bean(bean)

def delete_bean(bean_id: str) -> bool:
    """
    Router adapter: delete by id.
    Returns True if removed, False if not found.
    """
    from typing import Any
    blob = _beans_blob()
    if bean_id in blob:
        del blob[bean_id]
        _save_beans_blob(blob)
        return True
    return False

def import_beans_json(payload: Any) -> int:
    """
    Router adapter for bulk import:
    Accepts either {"beans":[...]} or a bare list of beans.
    Merges by id/alias. Returns count processed (added + updated).
    """
    # unify to dict payload for import_beans(...)
    if isinstance(payload, list):
        payload = {"beans": payload}
    if not isinstance(payload, dict):
        payload = {"beans": []}
    res = import_beans(payload, mode="merge")
    # best-effort count
    return int(res.get("added", 0)) + int(res.get("updated", 0))

def export_beans_json() -> Dict[str, Any]:
    """
    Router adapter: expose the full beans document.
    """
    return export_beans()