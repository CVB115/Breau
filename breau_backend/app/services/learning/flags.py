# breau_backend/app/services/learning/flags.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# Feature flag manager with global + per-user overrides.
# Used to enable/disable individual subsystems:
#   - use_model_planner
#   - use_practice
#   - use_cohort_seed
#   - use_dynamic_priors, etc.

@dataclass
class FlagsConfig:
    state_dir: Path

# Purpose:
# Global fallback flags (applied when no user override exists).
_DEFAULTS = {
    "use_dynamic_priors": True,
    "use_learned_edges": True,
    "use_user_personalisation": True,
    "use_practice": True,
    "use_model_planner": False,   # L5 planner
    "use_curriculum": True,
    "use_cohort_seed": True,
}

class Flags:
    def __init__(self, cfg: FlagsConfig):
        self.cfg = cfg
        ensure_dir(self._gdir())
        ensure_dir(self._udir())

    # Helpers for file locations
    def _gdir(self) -> Path: return self.cfg.state_dir
    def _udir(self) -> Path: return self.cfg.state_dir / "flags_users"
    def _gpath(self) -> Path: return self._gdir() / "flags_global.json"
    def _upath(self, user_id: str) -> Path: return self._udir() / f"{user_id}.json"

    # Purpose:
    # Read global flags merged with defaults.
    def get_global(self) -> Dict[str, Any]:
        return read_json(self._gpath(), _DEFAULTS)

    # Purpose:
    # Overwrite and persist global flags.
    def set_global(self, flags: Dict[str, Any]) -> Dict[str, Any]:
        cur = self.get_global()
        cur.update(flags or {})
        write_json(self._gpath(), cur)
        return cur

    # Purpose:
    # Read per-user flags (partial dict allowed).
    def get_user(self, user_id: str) -> Dict[str, Any]:
        return read_json(self._upath(user_id), {})

    # Purpose:
    # Update and save user-specific flags.
    def set_user(self, user_id: str, flags: Dict[str, Any]) -> Dict[str, Any]:
        cur = self.get_user(user_id)
        cur.update(flags or {})
        write_json(self._upath(user_id), cur)
        return cur

    # Purpose:
    # Query a feature flag (user → global → default).
    def is_on(self, user_id: Optional[str], key: str) -> bool:
        u = self.get_user(user_id) if user_id else {}
        g = self.get_global()
        return bool(u.get(key, g.get(key, _DEFAULTS.get(key, True))))
