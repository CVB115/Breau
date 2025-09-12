# breau_backend/app/services/learning/drift.py
from __future__ import annotations
from pathlib import Path
from typing import Dict
from breau_backend.app.utils.storage import read_json, write_json

# Purpose:
# Housekeeping for the global learned edges graph (dynamic_edges.json).
# - decay_edges: time‑decay scores/pos/neg counts to avoid stale dominance
# - prune_edges: drop weak tails and cap per‑goal fan‑out to keep model lean

DATA_DIR = Path("./data")
EDGES_PATH = DATA_DIR / "priors" / "dynamic_edges.json"

# Purpose:
# Apply multiplicative decay to every edge's (score, pos, neg).
# Use this in a periodic job (e.g., daily) to gently forget old signals.
def decay_edges(factor: float = 0.995) -> Dict:
    js = read_json(EDGES_PATH, {"schema_version":"2025-09-03","edges":{}})
    edges = js.get("edges", {})
    for k, node in edges.items():
        node["score"] = float(node.get("score", 0.0)) * factor
        node["pos"]   = float(node.get("pos",   0.0)) * factor
        node["neg"]   = float(node.get("neg",   0.0)) * factor
        edges[k] = node
    js["edges"] = edges
    write_json(EDGES_PATH, js)
    return {"ok": True, "count": len(edges)}

# Purpose:
# Remove tiny/low‑value edges and cap the number kept per goal tag.
# Strategy:
#   1) bucket edges by goal (split "goal::var")
#   2) drop edges with |score| < threshold
#   3) keep only top‑N by |score| per goal (prevents fan‑out explosions)
def prune_edges(threshold: float = 0.02, top_n_per_goal: int = 20) -> Dict:
    js = read_json(EDGES_PATH, {"schema_version":"2025-09-03","edges":{}})
    edges = js.get("edges", {})

    # bucket by goal tag
    buckets: Dict[str, list] = {}
    for k, node in edges.items():
        if "::" not in k:
            continue
        g, var = k.split("::", 1)
        buckets.setdefault(g, []).append((k, float(node.get("score", 0.0))))

    removed = []
    kept: Dict[str, Dict] = {}

    for g, pairs in buckets.items():
        # drop below threshold
        pairs = [(k, s) for (k, s) in pairs if abs(s) >= threshold]
        # keep top‑N by absolute score
        pairs.sort(key=lambda x: abs(x[1]), reverse=True)
        for i, (k, s) in enumerate(pairs):
            if i < top_n_per_goal:
                kept[k] = edges[k]
            else:
                removed.append(k)

    js["edges"] = kept
    write_json(EDGES_PATH, js)
    return {"ok": True, "removed": removed, "kept": len(kept)}
