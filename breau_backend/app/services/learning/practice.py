# breau_backend/app/services/learning/practice.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# Very lightweight “practice mode” state per user with two features:
# 1) a focused micro-adjustment hint (clarity vs body, etc.)
# 2) simple A/B overlays for taste exploration

@dataclass
class PracticeConfig:
    practice_dir: Path

def _default_state() -> Dict:
    return {"schema_version": "2025-09-03", "focus": None, "enabled": False}

class PracticeManager:
    def __init__(self, cfg: PracticeConfig):
        self.cfg = cfg
        ensure_dir(self.cfg.practice_dir)

    def _path(self, user_id: str) -> Path:
        return self.cfg.practice_dir / f"{user_id}.json"

    def get_state(self, user_id: str) -> Dict:
        # Purpose: read-or-init user practice state.
        p = self._path(user_id)
        if not p.exists():
            write_json(p, _default_state())
        return read_json(p, _default_state())

    def set_focus(self, user_id: str, focus: Optional[str], enabled: bool) -> Dict:
        # Purpose: update practice focus and toggle enable flag.
        st = self.get_state(user_id)
        st["focus"] = focus
        st["enabled"] = bool(enabled and focus)
        write_json(self._path(user_id), st)
        return st

    def micro_adjustment(self, user_id: str) -> Dict[str, object]:
        # Purpose:
        # Return a tiny overlay + coaching line based on current focus, or noop.
        st = self.get_state(user_id)
        if not st.get("enabled") or not st.get("focus"):
            return {"prompt": "Practice mode off.", "overlay": {}}

        f = st["focus"]
        if f in ("clarity", "floral", "citrus_acidity"):
            overlay = {"temp_delta": -0.1, "agitation_delta": -0.05}
            prompt = "Lower temp ~0.1 °C, gentle early agitation; compare citrus/clarity."
        elif f in ("body", "syrupy_body"):
            overlay = {"grind_delta": -0.05, "temp_delta": +0.1}
            prompt = "Slightly finer and a touch hotter; watch for syrupier texture."
        else:
            overlay, prompt = {}, "Focus set, but no recipe hint for this focus yet."

        return {"prompt": prompt, "overlay": overlay}

    def ab_variants(self) -> Dict[str, Dict]:
        # Purpose:
        # Two simple variants for manual A/B exploration.
        return {
            "A": {
                "label": "Clarity+",
                "overlay": {"temp_delta": -0.15, "agitation_delta": -0.1},
                "what_to_look_for": "Thinner body, higher clarity, brighter top-notes."
            },
            "B": {
                "label": "Body+",
                "overlay": {"grind_delta": -0.1, "temp_delta": +0.15},
                "what_to_look_for": "Heavier texture, rounder sweetness, muted highs."
            }
        }
