# breau_backend/app/config/__init__.py
from __future__ import annotations

# Re-export config surface expected by callers across the app.

# DB and misc settings live in manifest.py
from .manifest import (
    DB_URL,LEARNING_THRESHOLD  # <-- re-export so callers can do: from breau_backend.app.config import DB_URL
    # add other user/env settings here as needed
)

# Path helpers live in paths.py
from .paths import (
    REPO_ROOT,
    APP_ROOT,
    DATA_DIR,
    FLAVOUR_RULES_DIR,
    FLAVOUR_PRIORS_DIR,
    resolve_rules_file,
    resolve_priors_file,
    resolve_data_file,
    path_under_data,
    ensure_data_dir_exists,
)

__all__ = [
    # manifest
    "DB_URL",
    # paths
    "REPO_ROOT",
    "APP_ROOT",
    "DATA_DIR",
    "FLAVOUR_RULES_DIR",
    "FLAVOUR_PRIORS_DIR",
    "resolve_rules_file",
    "resolve_priors_file",
    "resolve_data_file",
    "path_under_data",
    "ensure_data_dir_exists",
    "LEARNING_THRESHOLD"
]
