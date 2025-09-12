# breau_backend/app/services/router_helpers/profile_helpers.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Tuple, List
import os, json
from ...utils.storage import data_dir, read_json
from fastapi import HTTPException, status

# ---- small IO helpers ----
def _profiles_dir() -> Path:
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    p = base / "profiles"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _profile_path() -> Path:
    return _profiles_dir() / "profile.json"

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

# ---- public helpers used by router ----
def get_profile() -> dict:
    """Load current user profile from DATA_DIR/profiles/profile.json."""
    try:
        return _read_json(_profile_path(), default={"profile": None}) or {"profile": None}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"load profile failed: {e}")

def post_profile(p: dict) -> dict:
    """Create/update current user profile (atomic write)."""
    try:
        if not isinstance(p, dict):
            raise HTTPException(status_code=400, detail="profile payload must be an object")
        _write_json(_profile_path(), p)
        return p
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"save profile failed: {e}")

def clear_profile() -> dict[str, bool]:
    """Delete the stored profile file (no error if absent)."""
    try:
        path = _profile_path()
        if path.exists():
            path.unlink(missing_ok=True)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"delete profile failed: {e}")

# ---- personalizer-backed, read-only views ----
def _load_personalizer_profile(user_id: str) -> Dict[str, Any]:
    """
    Look for:
      - <DATA_DIR>/profiles/<user_id>.json
      - CWD/data/profiles/<user_id>.json
      - (fallback) <DATA_DIR>/profiles/profiles.json or CWD/data/profiles/profiles.json keyed by user_id
    """
    def _candidates():
        base = []
        env = os.getenv("DATA_DIR")
        if env:
            base.append(Path(env))
        base.append(Path.cwd() / "data")
        return base

    # per-user file first
    for base in _candidates():
        p = (base / "profiles" / f"{user_id}.json").resolve()
        if p.exists():
            try:
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}

    # shared profiles.json keyed by user_id (optional fallback)
    for base in _candidates():
        p = (base / "profiles" / "profiles.json").resolve()
        if p.exists():
            try:
                with p.open("r", encoding="utf-8") as f:
                    blob = json.load(f)
                if isinstance(blob, dict):
                    if user_id in blob and isinstance(blob[user_id], dict):
                        return blob[user_id]
                    users = blob.get("users")
                    if isinstance(users, dict) and isinstance(users.get(user_id), dict):
                        return users[user_id]
            except Exception:
                return {}

    return {}

def _top_k_abs(d: Dict[str, float], k: int = 6) -> List[Tuple[str, float]]:
    try:
        return sorted(
            ((k_, float(v)) for k_, v in (d or {}).items()),
            key=lambda kv: abs(kv[1]),
            reverse=True
        )[:k]
    except Exception:
        return []

def get_preferences_view(user_id: str) -> Dict[str, Any]:
    """
    Public, read-only aggregation for UI/QA.
    Pulls from the Personalizer snapshot only (non-authoritative view).
    Does NOT mutate any state.
    """
    snap = _load_personalizer_profile(user_id) or {}
    out = {
        "user_id": user_id,
        "enabled": True,
        "updated_at": snap.get("updated_at"),
        "trait_response": snap.get("trait_response") or {},
        "note_sensitivity": snap.get("note_sensitivity") or {},
    }
    # optional context for clarity
    if "history_count" in snap:
        out["history_count"] = snap["history_count"]
    if "min_sessions_for_effect" in snap:
        out["min_sessions_for_effect"] = snap["min_sessions_for_effect"]

    # summary (top traits/notes) for UI list views
    out["summary"] = {
        "top_traits": _top_k_abs(out["trait_response"], k=6),
        "top_notes": _top_k_abs(out["note_sensitivity"], k=10),
    }
    return out

def get_preferences_index(limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """
    Read-only view of ./data/profiles/profiles.json (the indexed mirror).
    Returns a dict of user_id -> compact entry. Safe for QA/diagnostics.
    """
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    idx = base / "profiles" / "profiles.json"
    if not idx.exists():
        return {}

    try:
        blob = json.loads(idx.read_text(encoding="utf-8"))
        if not isinstance(blob, dict):
            return {}
        items = sorted(blob.items(), key=lambda kv: kv[0])
        page = items[offset : offset + limit]
        return {k: v for (k, v) in page}
    except Exception:
        return {}
