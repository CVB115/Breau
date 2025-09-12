# breau_backend/app/services/router_helpers/discover_helpers.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
import os, json

def _read_json(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def find_notes(q: str) -> Dict[str, Any]:
    """Toy full‑text search over DATA_DIR/library/notes.json (if present)."""
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    notes = _read_json(base / "library" / "notes.json", {"notes": []}) or {"notes": []}
    ql = (q or "").strip().lower()
    res: List[dict] = []
    for n in notes.get("notes", []):
        text = " ".join([str(n.get("title","")), str(n.get("body",""))]).lower()
        if ql in text:
            res.append(n)
    return {"query": q, "results": res}

def find_beans(q: str | None = None) -> Dict[str, Any]:
    """Simple search in DATA_DIR/library/beans.json by id/alias/origin."""
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    beans = _read_json(base / "library" / "beans.json", {"beans": []}) or {"beans": []}
    ql = (q or "").strip().lower()
    res: List[dict] = []
    for b in beans.get("beans", []):
        hay = " ".join([
            str(b.get("id","")), " ".join(b.get("aliases",[]) or []),
            str(b.get("origin","")), str(b.get("process","")), str(b.get("roast_level","")),
        ]).lower()
        if ql in hay: res.append(b)
    return {"query": q, "results": res}

def find_goals() -> Dict[str, Any]:
    """Return canonical goal tags if available; else a small default set."""
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    js = _read_json(base / "taxonomy" / "goals.json", {"goals": []}) or {"goals": []}
    if js["goals"]:
        return {"results": js["goals"]}
    # tiny default
    return {"results": ["increase_florality", "reduce_bitterness", "more_body", "more_clarity"]}
