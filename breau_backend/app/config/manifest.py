# breau_backend/app/config/manifest.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

# ---- DB settings and environment mode ----
from .paths import REPO_ROOT

_DEFAULT_SQLITE_PATH: Path = (REPO_ROOT / "breau.sqlite3").resolve()
_env_db_url = os.getenv("DATABASE_URL", "").strip()

# Exported DB_URL (used by db/session.py)
DB_URL: str = _env_db_url or f"sqlite:///{_DEFAULT_SQLITE_PATH}"

# Optional env flags
APP_ENV: str = os.getenv("APP_ENV", "development")
DEBUG_MODE: bool = os.getenv("DEBUG", "0") not in ("", "0", "false", "False")

# ---- Rulebook validation manifest (your original logic) ----
from breau_backend.app.flavour.library_loader import (
    has_rules_file, has_priors_file, inventory,
)

RULES_REQUIRED: List[str] = [
    "note_profiles.json",
    "decision_policy.yaml",
]

RULES_OPTIONAL: List[str] = [
    "default_recipes.json",
]

PRIORS_OPTIONAL: List[str] = [
    "note_neighbors_prior.json",
    "note_edges.json",
]

def validate_manifest() -> Dict[str, object]:
    inv = inventory()  # {"rules": {...}, "priors": {...}}

    missing_required: List[str] = []
    for name in RULES_REQUIRED:
        if not has_rules_file(name):
            missing_required.append(name)

    missing_optional: List[str] = []
    for name in RULES_OPTIONAL:
        if not has_rules_file(name):
            missing_optional.append(name)
    for name in PRIORS_OPTIONAL:
        if not has_priors_file(name):
            missing_optional.append(name)

    status = "ok" if not missing_required else "missing_required"
    return {
        "status": status,
        "inventory": inv,
        "required": RULES_REQUIRED,
        "optional": RULES_OPTIONAL + PRIORS_OPTIONAL,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
    }

LEARNING_THRESHOLD: int = int(os.getenv("LEARNING_THRESHOLD", "5"))  # or 3, or whatever


__all__ = ["DB_URL", "APP_ENV", "DEBUG_MODE", "LEARNING_MODE", "LEARNING_THRESHOLD", "validate_manifest"]
