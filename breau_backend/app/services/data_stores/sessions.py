# breau_backend/app/services/data_stores/sessions.py
from __future__ import annotations

import json, time, datetime as dt
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from breau_backend.app.config.paths import path_under_data, ensure_data_dir_exists
from .io_utils import append_jsonl

# Directory: ./data/sessions/
ensure_data_dir_exists("sessions")

def _date_str(ts: Optional[float] = None) -> str:
    return dt.datetime.fromtimestamp(ts or time.time()).strftime("%Y-%m-%d")

def _session_path_for_date(date_str: str) -> Path:
    return path_under_data("sessions", f"{date_str}.jsonl")

def append_session(session_obj: Dict[str, Any], date_str: Optional[str] = None) -> Path:
    """
    Append a brew session plan/result to the day's JSONL file.
    """
    payload = dict(session_obj or {})
    payload.setdefault("_ts", time.time())
    payload.setdefault("_type", "session")
    date = date_str or _date_str(payload["_ts"])
    path = _session_path_for_date(date)
    append_jsonl(path, payload)
    return path

def list_sessions(date_str: Optional[str] = None, limit: int = 200, newest_first: bool = True) -> List[Dict[str, Any]]:
    """
    Read sessions from one day (if provided) or all files. Returns at most `limit` items.
    """
    out: List[Dict[str, Any]] = []
    base = path_under_data("sessions")
    files: List[Path] = []
    if date_str:
        files = [ _session_path_for_date(date_str) ]
    else:
        if base.exists():
            files = sorted(base.glob("*.jsonl"))

    for p in files:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                out.append(obj)
            except Exception:
                continue

    out.sort(key=lambda x: x.get("_ts", 0), reverse=newest_first)
    return out[: max(1, min(limit, 2000))]
