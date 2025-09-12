# breau_backend/app/services/learning/personalizer.py
from __future__ import annotations
from typing import Dict, List
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# Per-user taste model with:
# - note_sensitivity (e.g., "jasmine" +, "cocoa" -)
# - trait_response by goal tags (e.g., "floral", "body")
# EMA updates with small caps; time-decay on load (half-life days).

@dataclass
class PersonalizerConfig:
    profiles_dir: Path
    ema_alpha: float = 0.25
    score_clip: float = 0.6
    min_sessions_for_effect: int = 3
    half_life_days: int = 28  # time-decay half-life

def _default_profile(user_id: str) -> Dict:
    return {
        "schema_version": "2025-09-03",
        "user_id": user_id,
        "note_sensitivity": {},   # {"jasmine": +0.2, ...}
        "trait_response": {},     # {"floral": +0.15, "body": -0.1}
        "overrides": {},
        "history_count": 0,
        "last_seen_iso": datetime.utcnow().isoformat()
    }

def _clip(v: float, c: float) -> float:
    return -c if v < -c else (c if v > c else v)

def _apply_decay(mapf: Dict[str, float], factor: float) -> Dict[str, float]:
    # Purpose:
    # Multiply each key by decay factor (in-place safe over copy).
    if not mapf:
        return mapf
    for k in list(mapf.keys()):
        mapf[k] *= factor
    return mapf

class Personalizer:
    def __init__(self, cfg: PersonalizerConfig):
        self.cfg = cfg
        ensure_dir(self.cfg.profiles_dir)

    def _path(self, user_id: str) -> Path:
        return self.cfg.profiles_dir / f"{user_id}.json"

    def _load(self, user_id: str) -> Dict:
        # Purpose:
        # Fetch profile, initialize if missing, apply time-decay on read.
        p = self._path(user_id)
        if not p.exists():
            prof = _default_profile(user_id)
            write_json(p, prof)
            return prof
        prof = read_json(p, _default_profile(user_id))

        # time decay on read
        last_seen = prof.get("last_seen_iso")
        try:
            last_dt = datetime.fromisoformat(last_seen) if last_seen else datetime.utcnow()
        except Exception:
            last_dt = datetime.utcnow()

        days = max(0.0, (datetime.utcnow() - last_dt).total_seconds() / 86400.0)
        if days > 0 and self.cfg.half_life_days > 0:
            factor = 0.5 ** (days / float(self.cfg.half_life_days))
            prof["note_sensitivity"] = _apply_decay(prof.get("note_sensitivity", {}), factor)
            prof["trait_response"]  = _apply_decay(prof.get("trait_response", {}), factor)
        return prof

    def _save(self, user_id: str, prof: Dict) -> None:
        prof["last_seen_iso"] = datetime.utcnow().isoformat()
        write_json(self._path(user_id), prof)

    def update_from_feedback(
        self,
        user_id: str,
        notes_confirmed: List[str],
        notes_missing: List[str],
        goal_tags: List[str],
        sentiment: float
    ) -> Dict:
        # Purpose:
        # EMA updates from a session:
        # - confirmed notes push sensitivity up (min +0.1 if sentiment > 0)
        # - missing notes push slightly down
        # - goal tags adjust trait_response toward session sentiment
        prof = self._load(user_id)
        a = self.cfg.ema_alpha

        # note sensitivities
        for n in notes_confirmed:
            val = prof["note_sensitivity"].get(n, 0.0)
            val = (1 - a) * val + a * max(0.1, sentiment)
            prof["note_sensitivity"][n] = _clip(val, self.cfg.score_clip)

        for n in notes_missing:
            val = prof["note_sensitivity"].get(n, 0.0)
            val = (1 - a) * val + a * (-0.05)
            prof["note_sensitivity"][n] = _clip(val, self.cfg.score_clip)

        # trait responses (by goal tags)
        for t in goal_tags:
            val = prof["trait_response"].get(t, 0.0)
            val = (1 - a) * val + a * sentiment
            prof["trait_response"][t] = _clip(val, self.cfg.score_clip)

        prof["history_count"] = int(prof.get("history_count", 0)) + 1
        self._save(user_id, prof)
        return prof

    def overlays_for_user(self, user_id: str, goal_tags: List[str]) -> Dict[str, float]:
        # Purpose:
        # Translate user trait preferences into tiny, safe overlays.
        prof = self._load(user_id)
        if int(prof.get("history_count", 0)) < self.cfg.min_sessions_for_effect:
            return {}

        trait = prof.get("trait_response", {})
        floral_score = trait.get("floral", 0.0)
        body_score = trait.get("body", 0.0) or trait.get("syrupy_body", 0.0)

        overlays: Dict[str, float] = {}
        if floral_score > 0:
            overlays["temp_delta"] = overlays.get("temp_delta", 0.0) - min(0.3, 0.3 * floral_score)
            overlays["agitation_delta"] = overlays.get("agitation_delta", 0.0) - min(0.1, 0.1 * floral_score)
        if body_score > 0:
            overlays["grind_delta"] = overlays.get("grind_delta", 0.0) - min(0.3, 0.3 * body_score)
            overlays["temp_delta"] = overlays.get("temp_delta", 0.0) + min(0.2, 0.2 * body_score)

        # Final cap (belt-and-suspenders—compose_overlay caps again)
        for k in list(overlays.keys()):
            overlays[k] = _clip(overlays[k], 0.3)
        return overlays
