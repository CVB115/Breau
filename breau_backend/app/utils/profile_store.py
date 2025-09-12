# breau_backend/app/utils/profile_store.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict
from datetime import datetime

# -----------------------
# Paths & file utilities
# -----------------------

DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
PROFILES_DIR = DATA_DIR / "profiles"
HISTORY_DIR = DATA_DIR / "history"
SESSIONS_DIR = HISTORY_DIR / "sessions"

# Tests may override with a single-file path
PROFILE_PATH = Path(os.getenv("BREAU_PROFILE_PATH", PROFILES_DIR / "profiles.json"))

def _ensure_dirs() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Corrupt/empty → start fresh to avoid crashes
        return {}

def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    tmp.replace(path)

# On-disk structure:
# {
#   "profiles": {
#       "<user_id>": { ...profile dict... }
#   }
# }

def _load_all() -> Dict[str, Any]:
    _ensure_dirs()
    blob = _read_json(PROFILE_PATH)
    if not isinstance(blob.get("profiles"), dict):
        blob = {"profiles": {}}
    return blob

def _save_all(blob: Dict[str, Any]) -> None:
    _write_json(PROFILE_PATH, blob)

# -----------------------
# Public API
# -----------------------

def get_profile(user_id: str) -> Dict[str, Any]:
    blob = _load_all()
    try:
        rec = blob["profiles"][user_id]
    except KeyError as e:
        raise KeyError(f"profile not found for user_id='{user_id}'") from e
    out = dict(rec)
    out.setdefault("user_id", user_id)
    return out

def upsert_profile(user_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    blob = _load_all()
    rec = dict(profile or {})
    rec["user_id"] = user_id
    blob["profiles"][user_id] = rec
    _save_all(blob)
    return rec

def delete_profile(user_id: str) -> bool:
    blob = _load_all()
    existed = user_id in blob["profiles"]
    if existed:
        del blob["profiles"][user_id]
        _save_all(blob)
    return existed

def list_profiles() -> Dict[str, Any]:
    blob = _load_all()
    return {"profiles": dict(blob["profiles"])}

def append_session(user_id: str, session: Dict[str, Any]) -> str:
    """
    Append a brew/telemetry session JSON to data/history/sessions.
    Returns the saved file path as a string.
    """
    _ensure_dirs()
    sid = (session or {}).get("session_id")
    if not sid:
        now = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
        sid = f"{user_id}__{now}"

    payload = dict(session or {})
    payload.setdefault("user_id", user_id)
    payload.setdefault("created_utc", datetime.utcnow().isoformat(timespec="seconds") + "Z")

    out_path = SESSIONS_DIR / f"{sid}.json"
    _write_json(out_path, payload)
    return str(out_path)
