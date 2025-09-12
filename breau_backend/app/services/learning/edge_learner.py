# breau_backend/app/services/learning/edge_learner.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
from pathlib import Path
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# Learn soft associations between goal tags (e.g., "clarity", "body") and small
# variable nudges (temp/grind/agitation). Produces gentle overlays used by the
# protocol nudger. Writes under ./data/priors/dynamic edges.
# Notes: small positive/negative “evidence” accumulates with decay; caps prevent runaway.

@dataclass
class EdgeLearnerConfig:
    data_dir: Path
    edges_path: Path
    alpha_pos: float = 0.12   # Purpose: learning rate for positive signals
    alpha_neg: float = 0.06   # Purpose: smaller step for negative to stay conservative
    decay: float = 0.995      # Purpose: per-update exponential decay on stored evidence
    score_clip: float = 0.75  # Purpose: guardrail to avoid runaway updates

# Purpose:
# Default JSON shape for the dynamic edge store.
def _default_edges() -> Dict:
    return {"schema_version": "2025-09-03", "edges": {}}

# Purpose:
# Compose a unique edge key: "goal_tag::var_key" (e.g., "clarity::temp_delta").
def _key(goal_tag: str, var_key: str) -> str:
    return f"{goal_tag}::{var_key}"

class EdgeLearner:
    # Purpose:
    # Init store and ensure directory exists; do not write under app/.
    def __init__(self, cfg: EdgeLearnerConfig):
        self.cfg = cfg
        ensure_dir(self.cfg.edges_path.parent)
        if not self.cfg.edges_path.exists():
            write_json(self.cfg.edges_path, _default_edges())

    # Purpose:
    # Load dynamic edges (tolerant to missing file).
    def _load(self) -> Dict:
        return read_json(self.cfg.edges_path, _default_edges())

    # Purpose:
    # Persist dynamic edges atomically.
    def _save(self, data: Dict) -> None:
        write_json(self.cfg.edges_path, data)

    # Purpose:
    # Register a feedback sample. Positive sentiment increases edge score
    # in proportion to |delta|, negative sentiment decreases it (smaller alpha).
    def register_feedback(self, goal_tags: List[str], var_nudges: Dict[str, float], sentiment: float) -> None:
        data = self._load()
        edges = data["edges"]
        for g in goal_tags:
            for vk, vdelta in var_nudges.items():
                k = _key(g, vk)
                node = edges.get(k, {"score": 0.0, "pos": 0.0, "neg": 0.0})
                if sentiment >= 0:
                    node["pos"] += abs(vdelta) * sentiment
                    node["score"] += self.cfg.alpha_pos * (abs(vdelta) * sentiment)
                else:
                    node["neg"] += abs(vdelta) * (-sentiment)
                    node["score"] -= self.cfg.alpha_neg * (abs(vdelta) * (-sentiment))

                # Purpose: clamp to keep trust-region small and reversible.
                node["score"] = max(-self.cfg.score_clip, min(self.cfg.score_clip, node["score"]))
                edges[k] = node
        self._save(data)

    # Purpose:
    # Apply exponential decay to all edges (use in periodic maintenance or after batches).
    def decay_once(self) -> None:
        data = self._load()
        edges = data["edges"]
        d = self.cfg.decay
        for _, node in edges.items():
            node["score"] *= d
            node["pos"] *= d
            node["neg"] *= d
        self._save(data)

    # Purpose:
    # Aggregate overlays for a set of goal tags (sum their edge scores per variable).
    # Gentle cap keeps final overlay within safe limits.
    def overlays_for_goals(self, goal_tags: List[str]) -> Dict[str, float]:
        data = self._load()
        edges = data["edges"]
        agg: Dict[str, float] = {}
        for g in goal_tags:
            prefix = f"{g}::"
            for k, node in edges.items():
                if not k.startswith(prefix):
                    continue
                _, var_key = k.split("::", 1)
                agg[var_key] = agg.get(var_key, 0.0) + node["score"]
        # Purpose: final safety cap, consistent with other overlays.
        for vk in list(agg.keys()):
            agg[vk] = max(-0.25, min(0.25, agg[vk]))
        return agg
