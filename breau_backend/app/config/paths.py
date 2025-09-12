# breau_backend/app/config/paths.py
from __future__ import annotations

"""
Central path resolution for Breau.

Env overrides:
    DATA_DIR
    FLAVOUR_RULES_DIR
    FLAVOUR_PRIORS_DIR

Defaults:
    <repo_root>/data
    <repo_root>/breau_backend/app/flavour/rules
    <repo_root>/breau_backend/app/flavour/priors

Exports:
    - constants: DATA_DIR, FLAVOUR_RULES_DIR, FLAVOUR_PRIORS_DIR, REPO_ROOT, APP_ROOT
    - getters: get_*()
    - resolvers: resolve_rules_file(), resolve_priors_file(), resolve_data_file()
    - legacy shims: get_paths(), path_under_data(), ensure_data_dir_exists()
"""

import os
from pathlib import Path
from typing import Dict

# ──────────────────────────────────────────────────────────────────────────────
_THIS_FILE = Path(__file__).resolve()

def _resolve_repo_root() -> Path:
    p = _THIS_FILE
    for _ in range(6):
        if (p.parent / "breau_backend" / "app").exists():
            return p.parent
        p = p.parent
    return _THIS_FILE.parents[3]

REPO_ROOT: Path = _resolve_repo_root()
APP_ROOT: Path = REPO_ROOT / "breau_backend" / "app"

def _clean_env(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip().strip('"').strip("'")
    return v or None

def _env_path(name: str) -> Path | None:
    raw = _clean_env(os.getenv(name))
    if not raw:
        return None
    return Path(raw).expanduser().resolve()

def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

_default_data = REPO_ROOT / "data"
_default_rules = APP_ROOT / "flavour" / "rules"
_default_priors = APP_ROOT / "flavour" / "priors"

_env_data = _env_path("DATA_DIR")
_env_rules = _env_path("FLAVOUR_RULES_DIR")
_env_priors = _env_path("FLAVOUR_PRIORS_DIR")

DATA_DIR: Path = (_env_data or _default_data).resolve()
FLAVOUR_RULES_DIR: Path = (_env_rules or _default_rules).resolve()
FLAVOUR_PRIORS_DIR: Path = (_env_priors or _default_priors).resolve()

# Create directories for smoother dev
_ensure_dir(DATA_DIR)
_ensure_dir(FLAVOUR_RULES_DIR)
_ensure_dir(FLAVOUR_PRIORS_DIR)

# ── Getters
def get_repo_root() -> Path: return REPO_ROOT
def get_app_root()  -> Path: return APP_ROOT
def get_data_dir()  -> Path: return DATA_DIR
def get_rules_dir() -> Path: return FLAVOUR_RULES_DIR
def get_priors_dir()-> Path: return FLAVOUR_PRIORS_DIR

# ── Resolvers
def resolve_rules_file(name: str) -> Path:
    """Return absolute path under rules dir for a given filename."""
    return FLAVOUR_RULES_DIR / name

def resolve_priors_file(name: str) -> Path:
    """Return absolute path under priors dir for a given filename."""
    return FLAVOUR_PRIORS_DIR / name

def resolve_data_file(*parts: str) -> Path:
    """Return absolute path under DATA_DIR for nested parts and ensure parent exists."""
    p = DATA_DIR.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

# ── Backward‑compat shims expected by older modules
def get_paths() -> Dict[str, Path]:
    return {
        "DATA_DIR": DATA_DIR,
        "FLAVOUR_RULES_DIR": FLAVOUR_RULES_DIR,
        "FLAVOUR_PRIORS_DIR": FLAVOUR_PRIORS_DIR,
        "REPO_ROOT": REPO_ROOT,
        "APP_ROOT": APP_ROOT,
    }

def path_under_data(*parts: str) -> Path:
    """Alias for old helper used by priors_dynamic.py and data stores."""
    return resolve_data_file(*parts)

def ensure_data_dir_exists(*parts: str) -> Path:
    """
    Ensure DATA_DIR (and optional subpaths) exist.
    Examples:
        ensure_data_dir_exists() -> <DATA_DIR>
        ensure_data_dir_exists("library") -> <DATA_DIR>/library
        ensure_data_dir_exists("sessions") -> <DATA_DIR>/sessions
    """
    p = DATA_DIR.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p

__all__ = [
    # constants
    "DATA_DIR", "FLAVOUR_RULES_DIR", "FLAVOUR_PRIORS_DIR", "REPO_ROOT", "APP_ROOT",
    # getters
    "get_repo_root", "get_app_root", "get_data_dir", "get_rules_dir", "get_priors_dir",
    # resolvers
    "resolve_rules_file", "resolve_priors_file", "resolve_data_file",
    # shims
    "get_paths", "path_under_data", "ensure_data_dir_exists",
]
