# breau_backend/app/flavour/library_loader.py
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # PyYAML
except Exception as e:  # pragma: no cover
    yaml = None  # We handle None gracefully for YAML loaders.

from breau_backend.app.config.paths import (
    resolve_rules_file,
    resolve_priors_file,
)

# -----------------------------------------------------------------------------
# Logger
# -----------------------------------------------------------------------------
log = logging.getLogger("breau.library_loader")
if not log.handlers:
    handler = logging.StreamHandler()
    log.addHandler(handler)
    log.setLevel(logging.INFO)

# -----------------------------------------------------------------------------
# Internal IO helpers
# -----------------------------------------------------------------------------
def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def _load_json_from(path: Path) -> Any:
    try:
        txt = _read_text(path)
        return json.loads(txt)
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e

def _load_yaml_from(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError(
            "PyYAML is not installed but a YAML file was requested. "
            "Install with: pip install pyyaml"
        )
    try:
        txt = _read_text(path)
        return yaml.safe_load(txt)
    except FileNotFoundError:
        raise
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path}: {e}") from e

# -----------------------------------------------------------------------------
# Public loader API (rules)
# -----------------------------------------------------------------------------
@lru_cache(maxsize=64)
def load_json_rules(filename: str) -> Any:
    """
    Load a JSON rulebook from flavour/rules (with legacy fallback handled in paths).
    Raises FileNotFoundError if not present in either location.
    """
    path = resolve_rules_file(filename)
    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")
    obj = _load_json_from(path)
    log.info(f"[rules] loaded {filename} from {path}")
    return obj

@lru_cache(maxsize=64)
def load_yaml_rules(filename: str) -> Any:
    """
    Load a YAML rulebook from flavour/rules (with legacy fallback handled in paths).
    Raises FileNotFoundError if not present in either location.
    """
    path = resolve_rules_file(filename)
    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")
    obj = _load_yaml_from(path)
    log.info(f"[rules] loaded {filename} from {path}")
    return obj

# -----------------------------------------------------------------------------
# Public loader API (priors)
# -----------------------------------------------------------------------------
@lru_cache(maxsize=64)
def load_json_priors(filename: str, *, required: bool = False, default: Any = None) -> Any:
    """
    Load a JSON prior from flavour/priors (with legacy fallback handled in paths).
    If required is False and file is missing, return `default` and log at INFO.
    If required is True and file is missing, raise FileNotFoundError.
    """
    path = resolve_priors_file(filename)
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Priors file not found: {path}")
        log.info(f"[priors] optional file missing: {filename} (looked at {path}); using default.")
        return default
    obj = _load_json_from(path)
    log.info(f"[priors] loaded {filename} from {path}")
    return obj

def has_priors_file(filename: str) -> bool:
    """
    True if a priors file exists (after applying legacy fallback in resolver).
    """
    path = resolve_priors_file(filename)
    return path.exists()

def has_rules_file(filename: str) -> bool:
    """
    True if a rules file exists (after applying legacy fallback in resolver).
    """
    path = resolve_rules_file(filename)
    return path.exists()

# -----------------------------------------------------------------------------
# Convenience accessors for well-known files
# -----------------------------------------------------------------------------
_RULES_NOTE_PROFILES = "note_profiles.json"
_RULES_DECISION_POLICY = "decision_policy.yaml"
_RULES_DEFAULT_RECIPES = "default_recipes.json"  # optional

_PRIORS_NEIGHBORS = "note_neighbors_prior.json"  # optional
_PRIORS_EDGES = "note_edges.json"                # optional

@lru_cache(maxsize=1)
def get_note_profiles() -> Dict[str, Any]:
    """
    Returns the full note profiles dictionary (required).
    """
    return load_json_rules(_RULES_NOTE_PROFILES)

@lru_cache(maxsize=1)
def get_decision_policy() -> Dict[str, Any]:
    """
    Returns the decision policy structure (required).
    """
    return load_yaml_rules(_RULES_DECISION_POLICY)

@lru_cache(maxsize=1)
def get_default_recipes() -> Dict[str, Any]:
    """
    Returns default recipes if present, else {}.
    """
    return load_json_rules(_RULES_DEFAULT_RECIPES) if has_rules_file(_RULES_DEFAULT_RECIPES) else {}

def has_neighbors_prior() -> bool:
    return has_priors_file(_PRIORS_NEIGHBORS)

def has_note_edges() -> bool:
    return has_priors_file(_PRIORS_EDGES)

# -----------------------------------------------------------------------------
# Higher-level helpers for priors (neighbors & edges)
# -----------------------------------------------------------------------------
def _norm_note_key(note: str) -> str:
    # Normalization strategy: lower-case; callers can keep their own mapping if needed.
    return (note or "").strip().lower()

@lru_cache(maxsize=1)
def _neighbors_map() -> Dict[str, List[Dict[str, Any]]]:
    """
    Schema (recommended):
    {
      "jasmine": [{"note":"orange_blossom","w":0.2}, {"note":"bergamot","w":0.15}],
      ...
    }
    """
    data = load_json_priors(_PRIORS_NEIGHBORS, required=False, default={})
    # Normalize keys to lowercase for consistent lookup
    if isinstance(data, dict):
        return { _norm_note_key(k): v for k, v in data.items() }
    log.info(f"[priors] neighbors file had unexpected schema; ignoring.")
    return {}

def get_neighbors(note: str) -> List[Dict[str, Any]]:
    """
    Return neighbor list for a note. If the file is missing or schema is unexpected, returns [].
    """
    return _neighbors_map().get(_norm_note_key(note), [])

@lru_cache(maxsize=1)
def _edges_map() -> Dict[str, List[Dict[str, Any]]]:
    """
    Schema (recommended, undirected expressed as symmetric lists or handled upstream):
    {
      "red_grape": [
         {"note":"cassis","w":0.1,"label":"shared_family"},
         {"note":"cinnamon","w":0.05,"label":"supporting"}
      ],
      ...
    }
    """
    data = load_json_priors(_PRIORS_EDGES, required=False, default={})
    if isinstance(data, dict):
        return { _norm_note_key(k): v for k, v in data.items() }
    log.info(f"[priors] edges file had unexpected schema; ignoring.")
    return {}

def edges_for(note: str) -> List[Dict[str, Any]]:
    """
    Return conceptual edges for a note. If the file is missing or schema is unexpected, returns [].
    """
    return _edges_map().get(_norm_note_key(note), [])

# -----------------------------------------------------------------------------
# Debug / inventory helpers
# -----------------------------------------------------------------------------
def inventory() -> Dict[str, Any]:
    """
    Return a light inventory of what’s available. Safe to call from a health or debug route.
    """
    return {
        "rules": {
            "note_profiles": has_rules_file(_RULES_NOTE_PROFILES),
            "decision_policy": has_rules_file(_RULES_DECISION_POLICY),
            "default_recipes": has_rules_file(_RULES_DEFAULT_RECIPES),
        },
        "priors": {
            "note_neighbors_prior": has_neighbors_prior(),
            "note_edges": has_note_edges(),
        },
    }

# -----------------------------------------------------------------------------
# Back-compat shims for older routers expecting demo/toolset helpers.
# These keep legacy imports alive while you migrate routers to services.data_stores.
# -----------------------------------------------------------------------------
def get_toolset(toolset_id: str) -> Dict[str, Any]:
    """
    Compatibility shim. Replace with a real implementation
    (e.g., services.data_stores.get_toolset) when ready.
    """
    # You can implement a real lookup here if you want:
    # from breau_backend.app.services.data_stores import get_toolset as _gt
    # return _gt(toolset_id)
    raise KeyError(f"toolset '{toolset_id}' not found")

def get_bean(alias_or_id: str) -> Dict[str, Any]:
    """
    Compatibility shim for demo library bean lookup. Replace with
    a real demo/library fetch if you keep this flow.
    """
    # Example of delegating to a user/demos store (uncomment if available):
    # try:
    #     from breau_backend.app.services.data_stores import get_bean as _user_bean
    #     rec = _user_bean(alias_or_id)
    #     return rec.get('data', {})
    # except Exception:
    #     pass
    raise KeyError(f"demo bean '{alias_or_id}' not found")
