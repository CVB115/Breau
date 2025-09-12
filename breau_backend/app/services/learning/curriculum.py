from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# Lightweight spaced‑repetition curriculum over micro‑skills.
# Skills: clarity, body, acidity_control, bitterness_control, texture
# Each task yields: tiny overlay deltas + 1‑line coaching tip.
# Scheduling uses an SM‑2‑lite model: ease factor (ef), interval days (ivl), reps (n), due_ts.

SKILLS = ("clarity", "body", "acidity_control", "bitterness_control", "texture")

@dataclass
class CurriculumConfig:
    root_dir: Path
    default_ef: float = 2.4
    min_ivl: int = 1
    max_ivl: int = 21

def _now() -> float:
    return time.time()

# Purpose:
# Create a default per‑user curriculum state file on first use.
def _default_user(user_id: str, cfg: CurriculumConfig) -> Dict:
    ts = _now()
    return {
        "schema_version": "2025-09-03",
        "user_id": user_id,
        "items": {
            s: {"ef": cfg.default_ef, "ivl": cfg.min_ivl, "n": 0, "due_ts": ts, "status": "new"}
            for s in SKILLS
        },
        "active": None,   # currently assigned skill
        "history": [],    # recent completions
    }

# Purpose:
# One‑liner coaching copy per skill (shown to the user).
def _coaching(skill: str) -> str:
    if skill == "clarity":
        return "Lower temp 0.2°C; gentle early pours. Notice citrus brightness."
    if skill == "body":
        return "Raise temp 0.2°C; stronger late agitation. Watch for syrupy texture."
    if skill == "acidity_control":
        return "To tame sourness: +0.2°C, extend contact slightly."
    if skill == "bitterness_control":
        return "To reduce bitterness: −0.2°C, gentler late agitation."
    if skill == "texture":
        return "Even flow; avoid channeling. Slightly coarser if stall."
    return "Small tweak—compare and notice the change."

# Purpose:
# Tiny overlays aligned to trust‑region caps. Returned alongside coaching.
def _overlay(skill: str) -> Dict[str, float]:
    if skill == "clarity":
        return {"temp_delta": -0.2, "agitation_delta": -0.1}
    if skill == "body":
        return {"temp_delta": +0.2, "agitation_delta": +0.1}
    if skill == "acidity_control":
        return {"temp_delta": +0.2, "agitation_delta": +0.05}
    if skill == "bitterness_control":
        return {"temp_delta": -0.2, "agitation_delta": -0.05}
    if skill == "texture":
        return {"grind_delta": +0.1}  # slightly coarser → more even flow
    return {}

# Purpose:
# Map skill to a hint tag that helps the L2/L4 explain string.
def _goal_hint(skill: str) -> str:
    return "clarity" if skill in ("clarity", "acidity_control") else (
        "body" if skill in ("body", "texture", "bitterness_control") else None
    )

class Curriculum:
    # Purpose:
    # IO plumbing for per‑user curriculum state.
    def __init__(self, cfg: CurriculumConfig):
        self.cfg = cfg
        ensure_dir(self.cfg.root_dir)

    def _path(self, user_id: str) -> Path:
        return self.cfg.root_dir / f"{user_id}.json"

    def _load(self, user_id: str) -> Dict:
        p = self._path(user_id)
        if not p.exists():
            js = _default_user(user_id, self.cfg)
            write_json(p, js)
            return js
        return read_json(p, _default_user(user_id, self.cfg))

    def _save(self, user_id: str, js: Dict) -> None:
        write_json(self._path(user_id), js)

    # ------- Public API -------

    # Purpose:
    # Return the current curriculum snapshot for this user.
    def status(self, user_id: str) -> Dict:
        return self._load(user_id)

    # Purpose:
    # Pick the next task: if anything is due, pick the most overdue; otherwise pick the least‑practiced.
    # Returns the task bundle (skill, overlay, coaching, hint, due_ts) and sets it as active.
    def next_task(self, user_id: str) -> Dict:
        js = self._load(user_id)
        now = _now()
        items = js.get("items", {})
        due = [(k, v) for k, v in items.items() if v.get("due_ts", 0) <= now]
        if due:
            skill = sorted(due, key=lambda kv: kv[1].get("due_ts", 0))[0][0]
        else:
            skill = sorted(items.items(), key=lambda kv: kv[1].get("n", 0))[0][0]
        js["active"] = skill
        self._save(user_id, js)
        return {
            "user_id": user_id,
            "skill": skill,
            "overlay": _overlay(skill),
            "coaching": _coaching(skill),
            "hint": _goal_hint(skill),
            "due_ts": items.get(skill, {}).get("due_ts"),
        }

    # Purpose:
    # Advance scheduler for the (active or provided) skill using a simplified SM‑2 update.
    # success=True corresponds to high quality (q≈5); otherwise we degrade EF/IVL appropriately.
    def advance(self, user_id: str, skill: Optional[str], success: bool, confidence: int = 2) -> Dict:
        js = self._load(user_id)
        skill = skill or js.get("active")
        if not skill:
            return {"ok": False, "msg": "no active skill"}
        item = js["items"].setdefault(skill, {"ef": self.cfg.default_ef, "ivl": self.cfg.min_ivl, "n": 0, "due_ts": _now()})

        # SM‑2‑lite updates
        ef = float(item.get("ef", self.cfg.default_ef))
        n  = int(item.get("n", 0))
        ivl = int(item.get("ivl", self.cfg.min_ivl))

        # Map success/confidence to a 0..5 quality; here: 5 for success, else 2/3 depending on confidence.
        q = 5 if success else (3 if confidence >= 2 else 2)
        ef_new = max(1.3, ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
        if q < 3:
            n = 0
            ivl = self.cfg.min_ivl
        else:
            n += 1
            if n == 1:
                ivl = self.cfg.min_ivl
            elif n == 2:
                ivl = 3
            else:
                ivl = int(round(ivl * ef_new))
                ivl = max(self.cfg.min_ivl, min(self.cfg.max_ivl, ivl))

        item.update({"ef": ef_new, "n": n, "ivl": ivl, "due_ts": _now() + ivl * 86400})
        js["history"] = (js.get("history") or [])[-49:] + [{"skill": skill, "q": q, "ivl": ivl}]
        self._save(user_id, js)
        return {"ok": True, "skill": skill, "next_due_ts": item["due_ts"], "ef": ef_new, "ivl": ivl, "n": n}
    
def _skill_hint(skill: str) -> str:
    # Optional: tiny tag used by explain()
    if skill == "clarity":
        return "clarity"
    if skill == "body":
        return "body"
    return ""

def peek_due(user_id: str) -> Dict:
    """
    Purpose:
    Non-destructive peek: if any skill item is due, return its overlay & coaching.
    Does not set 'active' or advance scheduling.
    """
    ensure_dir(cfg.root_dir)  # type: ignore  # uses enclosing module's cfg via functions below if preferred
    # safer: re-open using a local loader
    import json, os, time as _t
    path = CurriculumConfig.root_dir if isinstance(CurriculumConfig, type) else None  # no-op fallback

    # Re-load via helper like in next_task(); rewritten to avoid refactor:
    # (Below is a light reimplementation that mirrors file layout)
    # If your module already has a loader, call it instead.
    p = CurriculumConfig.root_dir / f"{user_id}.json"  # type: ignore
    if not p.exists():
        return {}

    js = read_json(p, None)
    if not js:
        return {}

    now = _now()
    due_skill = None
    for s, it in (js.get("items") or {}).items():
        if float(it.get("due_ts", 0)) <= now:
            due_skill = s
            break
    if not due_skill:
        return {}

    return {
        "skill": due_skill,
        "overlay": _overlay(due_skill),
        "coaching": _coaching(due_skill),
        "hint": _skill_hint(due_skill),
    }