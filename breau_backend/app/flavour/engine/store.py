# breau_backend/app/flavour/engines/store.py
from __future__ import annotations

"""
Purpose:
Lightweight rule/priors store with caching. Centralizes how flavour engines
load their JSON assets (rules & priors) and exposes a minimal ontology dict
for loaders/builders that need note profiles (and optionally policies).
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from breau_backend.app.config.paths import (
    FLAVOUR_RULES_DIR,
    FLAVOUR_PRIORS_DIR,
    resolve_rules_file,
    resolve_priors_file,
)

# ──────────────────────────────────────────────────────────────────────────────
# IO helpers

def _read_json(path: Path) -> Any:
    # Purpose:
    # Read & parse JSON with UTF‑8. Raise if file cannot be opened.
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

# If you later support YAML in rules/priors, add a safe YAML loader here.

# ──────────────────────────────────────────────────────────────────────────────
# Public loaders

def load_rules_json(name: str) -> Any:
    """
    Purpose:
    Load a JSON rules file by name from the rules directory
    (e.g., 'note_profiles.json'). Validates existence via resolver.
    """
    path = resolve_rules_file(name)
    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")
    return _read_json(path)

def load_priors_json(name: str) -> Any:
    """
    Purpose:
    Load a JSON priors file by name from the priors directory
    (e.g., 'note_edges.json'). Validates existence via resolver.
    """
    path = resolve_priors_file(name)
    if not path.exists():
        raise FileNotFoundError(f"Priors file not found: {path}")
    return _read_json(path)

# ──────────────────────────────────────────────────────────────────────────────
# Ontology entrypoint

@lru_cache(maxsize=1)
def get_ontology() -> Dict[str, Any]:
    """
    Purpose:
    Return a minimal shared ontology dict consumed by note loaders/builders.
    Currently includes:
      - note_profiles: master dictionary keyed by note id.
    Extend with additional rulebooks as needed (e.g., decision_policy).
    """
    note_profiles = load_rules_json("note_profiles.json")
    ontology = {
        "note_profiles": note_profiles,
        # "decision_policy": load_rules_json("decision_policy.json")  # if present
    }
    return ontology

# Purpose:
# Backward‑compat alias for an earlier misspelling.
def get_ontolgy() -> Dict[str, Any]:
    return get_ontology()
