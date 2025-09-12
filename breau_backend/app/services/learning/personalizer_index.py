# breau_backend/app/services/learning/personalizer_index.py
from __future__ import annotations
from typing import Dict, Any , Iterable
from pathlib import Path
import os
import json

# Prefer your canonical profile_store index writer if available.
try:
    from ...utils.profile_store import upsert_profile as _upsert_profile  # type: ignore
    HAVE_PROFILE_STORE = True
except Exception:  # pragma: no cover
    _upsert_profile = None
    HAVE_PROFILE_STORE = False

# Prefer your storage utils; fall back to local IO if not importable in some contexts.
try:
    from ...utils.storage import data_dir, read_json, write_json  # type: ignore
except Exception:  # pragma: no cover
    def data_dir(*parts: str) -> Path:
        base = Path(os.getenv("DATA_DIR", "./data")).resolve()
        p = base
        for part in parts:
            p = p / part
        p.mkdir(parents=True, exist_ok=True)
        return p

    def read_json(p: Path, default=None):
        try:
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def write_json(p: Path, data: Any) -> None:
        tmp = p.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)

def _load_personalizer_snapshot(user_id: str) -> Dict[str, Any]:
    """Load ./data/profiles/<user_id>.json; return {} if missing."""
    p = data_dir("profiles") / f"{user_id}.json"
    if not p.exists():
        return {}
    snap = read_json(p, {})
    return snap if isinstance(snap, dict) else {}

def _build_index_entry(snap: Dict[str, Any]) -> Dict[str, Any]:
    """Pick only stable, useful fields for the index."""
    return {
        "trait_response": snap.get("trait_response") or {},
        "note_sensitivity": snap.get("note_sensitivity") or {},
        "updated_at": snap.get("updated_at") or snap.get("last_seen_iso"),
        "history_count": int(snap.get("history_count", 0)),
    }

def _fallback_upsert(user_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """If profile_store isn't available, merge into ./data/profiles/profiles.json."""
    idx_path = data_dir("profiles") / "profiles.json"
    blob = read_json(idx_path, {}) or {}
    if not isinstance(blob, dict):
        blob = {}

    cur = blob.get(user_id, {})
    if not isinstance(cur, dict):
        cur = {}
    cur.update(entry)
    blob[user_id] = cur

    write_json(idx_path, blob)
    return cur

def sync_personalizer_index(user_id: str) -> Dict[str, Any]:
    """
    Read per-user personalizer snapshot and upsert a compact, indexed mirror.
    Returns the entry written to the index (or {} if no snapshot exists yet).
    """
    snap = _load_personalizer_snapshot(user_id)
    if not snap:
        return {}
    entry = _build_index_entry(snap)

    # 1) Write via canonical store if available
    if HAVE_PROFILE_STORE and _upsert_profile:
        _upsert_profile(user_id, entry)

    # 2) Always update the local mirror ./data/profiles/profiles.json
    try:
        _fallback_upsert(user_id, entry)
    except Exception:
        # never block on mirror creation
        pass

    return entry



def backfill_all(user_ids: Iterable[str] | None = None) -> int:
    """
    Scan ./data/profiles for per-user *.json snapshots (except profiles.json)
    and sync each into the indexed mirror. Returns count of entries written.
    """
    base = data_dir("profiles")
    written = 0

    if user_ids is None:
        # Discover all user snapshot files
        for p in base.glob("*.json"):
            if p.name == "profiles.json":
                continue
            uid = p.stem
            if sync_personalizer_index(uid):
                written += 1
    else:
        for uid in user_ids:
            if sync_personalizer_index(str(uid)):
                written += 1
    return written

if __name__ == "__main__":  # pragma: no cover
    import sys
    # Usage:
    #   python -m breau_backend.app.services.learning.personalizer_index
    #   python -m breau_backend.app.services.learning.personalizer_index u1 u2 u3
    args = sys.argv[1:]
    if args:
        n = backfill_all(args)
    else:
        n = backfill_all()
    print(f"Backfilled {n} profile index entr{'y' if n==1 else 'ies'}.")