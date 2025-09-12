# breau_backend/app/observability/suggestion_trace.py
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

class SuggestionTrace:
    """
    Lightweight, structured trace for how a brew suggestion was produced.
    Collects steps, overlays, priors, policy clamps, and final notes.
    Safe to return in API responses (no secrets).
    """
    def __init__(self, request_id: Optional[str] = None) -> None:
        self._t0 = time.time()
        self.request_id = request_id or f"req-{int(self._t0*1000)}"
        self.meta: Dict[str, Any] = {}
        self.steps: List[Dict[str, Any]] = []
        self.goals: List[Dict[str, Any]] = []
        self.policy_clamps: List[Dict[str, Any]] = []
        self.overlays: List[Dict[str, Any]] = []
        self.note_biases: List[Dict[str, Any]] = []
        self.selected_notes: List[str] = []
        self.outputs: Dict[str, Any] = {}

    # -------- meta & goals --------
    def set_meta(self, **kwargs: Any) -> None:
        self.meta.update(kwargs)

    def set_goals(self, goals: List[Dict[str, Any]]) -> None:
        self.goals = goals or []

    # -------- narrative steps (free-form) --------
    def add_step(self, label: str, **detail: Any) -> None:
        self.steps.append({"t": time.time(), "label": label, **detail})

    # -------- policy clamps --------
    def add_policy_clamp(self, field: str, value_before: Any, value_after: Any, reason: str) -> None:
        self.policy_clamps.append({
            "t": time.time(), "field": field, "before": value_before, "after": value_after, "reason": reason
        })

    # -------- overlays (goal → variable nudges) --------
    def add_overlay(self, name: str, weight: float, variables: Dict[str, Any]) -> None:
        self.overlays.append({
            "t": time.time(), "name": name, "weight": float(weight), "variables": variables
        })

    # -------- priors / edges / neighbor biases --------
    def add_note_bias(self, source: str, note: str, weight: float, why: str) -> None:
        self.note_biases.append({
            "t": time.time(), "source": source, "note": note, "weight": float(weight), "why": why
        })

    # -------- final note selection --------
    def set_selected_notes(self, notes: List[str]) -> None:
        self.selected_notes = list(notes or [])

    # -------- final outputs snapshot (e.g., plan dict) --------
    def set_outputs(self, **kwargs: Any) -> None:
        self.outputs.update(kwargs)

    # -------- export --------
    def to_public(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "elapsed_ms": int((time.time() - self._t0) * 1000),
            "meta": self.meta,
            "goals": self.goals,
            "steps": self.steps,
            "policy_clamps": self.policy_clamps,
            "overlays": self.overlays,
            "note_biases": self.note_biases,
            "selected_notes": self.selected_notes,
            "outputs": self.outputs,
        }
