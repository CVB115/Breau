from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter, defaultdict
from math import log2
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# Heuristic association mining from recent session logs: infer (goal_tag → variable sign)
# using PMI‑like co‑occurrence. Output is a small, human‑reviewable proposal list that can
# be promoted into dynamic priors after manual review.

# Purpose:
# Map numeric deltas to a coarse sign bucket with a dead‑zone.
def _sign(v: float) -> str:
    if v >  0.02: return "+"
    if v < -0.02: return "-"
    return "0"

# Purpose:
# Convert a numeric overlay into sign features like ["temp_delta+","grind_delta-"].
def _var_signs(nudges: Dict[str, float]) -> List[str]:
    out = []
    for k in ("temp_delta","grind_delta","agitation_delta"):
        s = _sign(float(nudges.get(k, 0.0)))
        if s != "0":
            out.append(f"{k}{s}")
    return out

# Purpose:
# Scan ./data/history/sessions/*.json and build PMI‑style association scores.
# window_days is currently unused in this lightweight pass but kept for parity with future filters.
def suggest_from_sessions(data_dir: Path, window_days: int = 30, min_count: int = 6) -> Dict:
    sess_dir = data_dir / "history" / "sessions"
    if not sess_dir.exists():
        return {"proposals": []}

    # naive scan: each file contains FeedbackIn‑like dicts
    co = Counter()  # pair counts (goal_tag, var_sign)
    cg = Counter()  # goal tag counts
    cv = Counter()  # var_sign counts

    for p in sess_dir.glob("*.json"):
        js = read_json(p, default=None)
        if not js: continue
        fb = js.get("feedback", {})
        goals = fb.get("goals", [])
        goal_tags = []
        for g in goals:
            for t in g.get("tags", []):
                if t not in goal_tags:
                    goal_tags.append(t)

        # approximate variable deltas from protocol snapshot
        proto = fb.get("protocol", {})
        temp = float(proto.get("temperature_c", 92.0))
        grind_label = str(proto.get("grind_label","")).lower()
        agi = str(proto.get("agitation_overall","moderate")).lower()
        nudges = {
            "temp_delta": (temp - 92.0) / 10.0,
            "grind_delta": (+0.2 if "coarse" in grind_label else (-0.2 if "fine" in grind_label else 0.0)),
            "agitation_delta": (0.2 if "high" in agi else (-0.2 if "gentle" in agi else 0.0)),
        }
        vs = _var_signs(nudges)
        if not goal_tags or not vs: continue

        for t in goal_tags:
            cg[t] += 1
            for v in vs:
                co[(t, v)] += 1
                cv[v] += 1

    # Purpose:
    # Turn counts into confidence‑scored proposals using PMI; keep the top few.
    total = sum(cg.values())
    props = []
    for (t, v), c in co.items():
        if c < min_count: continue
        p_t = cg[t] / total
        p_v = cv[v] / total
        p_tv = c / total
        pmi = log2(p_tv / (p_t * p_v + 1e-9))
        conf = min(0.99, max(0.0, (pmi / 4.0) + 0.5))  # squash to [0, 1)
        props.append({
            "id": f"{t}->{v}",
            "proposed": f"{t} -> {v}",
            "confidence": round(conf, 3),
            "counts": {"pair": c, "t": cg[t], "v": cv[v]},
        })

    props.sort(key=lambda x: x["confidence"], reverse=True)
    return {"proposals": props[:40]}

# Purpose:
# Persist a batch of proposals for later manual triage.
def save_pending(data_dir: Path, proposals: List[Dict]) -> Path:
    out_dir = data_dir / "priors" / "discovered"
    ensure_dir(out_dir)
    path = out_dir / "pending.json"
    write_json(path, {"proposals": proposals})
    return path

# Purpose:
# (Sketch) Accept a proposal and merge it as a small prior into dynamic edges.
# Caller identifies the proposal by id "goal_tag->var_sign" and we nudge score slightly.
def accept_proposal(data_dir: Path, proposal_id: str) -> Dict:
    edges_path = data_dir / "priors" / "dynamic_edges.json"
    js = read_json(edges_path, {"schema_version":"2025-09-03","edges":{}})
    edges = js.get("edges", {})
    # tiny initial score; use "::" keying to match learner format
    goal, var = proposal_id.split("->", 1)
    key = f"{goal}::{var.replace('+','_pos').replace('-','_neg')}"
    node = edges.get(key, {"score": 0.0, "pos": 0.0, "neg": 0.0})
    node["score"] = float(node.get("score", 0.0)) + 0.02
    edges[key] = node
    js["edges"] = edges
    write_json(edges_path, js)
    return {"ok": True, "merged": key}
