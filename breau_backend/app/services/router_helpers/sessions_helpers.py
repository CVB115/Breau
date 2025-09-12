# breau_backend/app/services/router_helpers/sessions_helpers.py
from __future__ import annotations
import os, json
from pathlib import Path
from typing import Any, Dict, List

def _sessions_dir() -> Path:
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    p = base / "history" / "sessions"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def list_all() -> Dict[str, Any]:
    root = _sessions_dir()
    items: List[Dict[str, Any]] = []
    for p in sorted(root.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        name = p.stem
        user_id, session_id = (name.split("__", 1) + [""])[:2] if "__" in name else ("", name)
        stat = p.stat()
        items.append({"session_id": session_id, "user_id": user_id, "filename": p.name,
                      "bytes": stat.st_size, "mtime": int(stat.st_mtime)})
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
    return {"session": data, "path": str(path)}

def drop_one(sid: str) -> Dict[str, Any]:
    root = _sessions_dir()
    candidates = [root / f"{sid}.json"] + list(root.glob(f"*__{sid}.json"))
    path = next((p for p in candidates if p.exists()), None)
    if not path:
        return {"error": "not_found"}
    path.unlink(missing_ok=True)
    return {"ok": True, "deleted": path.name}
