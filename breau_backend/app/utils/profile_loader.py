from __future__ import annotations
from pathlib import Path
import json
from ..config.paths import DATA_DIR

_PREFS_PATH = DATA_DIR / "user_prefs.json"

def load_user_prefs(user_id: str) -> dict:
    """
    Returns {"trait_biases": {...}} for this user if present, else {}.
    """
    if not _PREFS_PATH.exists():
        return {}
    try:
        all_prefs = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
        return all_prefs.get(user_id, {})
    except Exception:
        return {}
