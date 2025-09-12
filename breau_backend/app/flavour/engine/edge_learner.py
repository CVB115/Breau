# breau_backend/app/flavour/engines/edge_learner.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple
import json, math, time, os
from pathlib import Path

# Path helpers (A1/A3)
from breau_backend.app.config.paths import (
    resolve_priors_file, path_under_data, ensure_data_dir_exists,
)

EdgeKey = str  # "noteA|noteB" (sorted)

@dataclass
class LearnCfg:
    lam_cm: float = 0.01   # co-mention
    lam_cs: float = 0.02   # co-selection
    lam_go: float = 0.03   # good outcome
    lam_emb: float = 0.02  # embedding similarity centered at 0.5
    decay: float = 0.985
    min_delta: float = -0.10
    max_delta: float =  0.15
    min_final_w: float = 0.40
    max_final_w: float = 0.95
    min_serve_w: float = 0.50  # drop edges below this when exporting serving

@dataclass
class LearnRow:
    delta: float = 0.0
    cm: int = 0
    cs: int = 0
    go: int = 0
    last_seen: float = 0.0

def _ek(a: str, b: str) -> EdgeKey:
    a, b = a.strip(), b.strip()
    return f"{a}|{b}" if a <= b else f"{b}|{a}"

def clip(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))

def now() -> float:
    return time.time()

def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, obj: dict):
    _atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=2))

def _prior_weight(prior: Dict[str, List[dict]], a: str, b: str) -> float:
    for nb in prior.get(a, []):
        if nb.get("id") == b:
            return float(nb.get("weight", 0.0))
    return 0.0

def _bump_counts(row: LearnRow, signals: dict):
    row.cm += int(signals.get("co_mention", 0))
    row.cs += int(signals.get("co_select", 0))
    row.go += int(signals.get("good_outcome", 0))

def decay_delta(row: LearnRow, cfg: LearnCfg, weeks_since: float):
    row.delta *= (cfg.decay ** max(0.0, weeks_since))

def update_edge(a: str, b: str, signals: dict, row: LearnRow, cfg: LearnCfg) -> LearnRow:
    weeks = 0.0
    if row.last_seen:
        weeks = max(0.0, (now() - row.last_seen) / (7*24*3600))
    decay_delta(row, cfg, weeks)

    delta = 0.0
    delta += cfg.lam_cm * float(signals.get("co_mention", 0))
    delta += cfg.lam_cs * float(signals.get("co_select", 0))
    delta += cfg.lam_go * float(signals.get("good_outcome", 0))
    emb = signals.get("embed_sim", None)
    if emb is not None:
        delta += cfg.lam_emb * (float(emb) - 0.5)

    row.delta = clip(row.delta + delta, cfg.min_delta, cfg.max_delta)
    _bump_counts(row, signals)
    row.last_seen = now()
    return row

def merge_serving(prior: Dict[str, List[dict]], learned: Dict[EdgeKey, dict], cfg: LearnCfg) -> Dict[str, List[dict]]:
    serving: Dict[str, List[dict]] = {k: [] for k in prior.keys()}
    nodes = set(prior.keys())
    for k, lst in prior.items():
        nodes.update([nb["id"] for nb in lst])

    def _append(a: str, b: str, final_w: float, reasons: List[str]):
        if final_w >= cfg.min_serve_w:
            serving.setdefault(a, [])
            serving[a].append({"id": b, "weight": round(final_w, 3), "reasons": reasons})

    candidate_pairs = set()
    for a, lst in prior.items():
        for nb in lst:
            candidate_pairs.add(_ek(a, nb["id"]))
    for ek in learned.keys():
        a, b = ek.split("|")
        if a in nodes and b in nodes:
            candidate_pairs.add(ek)

    for ek in candidate_pairs:
        a, b = ek.split("|")
        pw_ab = _prior_weight(prior, a, b)
        pw_ba = _prior_weight(prior, b, a)
        ld = float(learned.get(ek, {}).get("delta", 0.0))
        final_ab = clip(pw_ab + ld, cfg.min_final_w, cfg.max_final_w) if pw_ab > 0 or ld != 0 else 0.0
        final_ba = clip(pw_ba + ld, cfg.min_final_w, cfg.max_final_w) if pw_ba > 0 or ld != 0 else 0.0

        rs = []
        if pw_ab > 0 or pw_ba > 0: rs.append("prior")
        if abs(ld) > 1e-9: rs.append("learned_delta")

        if final_ab > 0:
            _append(a, b, final_ab, rs)
        if final_ba > 0:
            _append(b, a, final_ba, rs)

    for a in serving:
        serving[a] = sorted(serving[a], key=lambda x: x["weight"], reverse=True)
    return serving

# -------- Public API --------

def learn_from_session(seed_pairs: List[Tuple[str,str]],
                       selected_pairs: List[Tuple[str,str]],
                       good_outcomes: List[Tuple[str,str]],
                       embeds: Dict[Tuple[str,str], float],
                       prior_path: str | None = None,
                       learned_path: str | None = None,
                       serving_path: str | None = None,
                       cfg: LearnCfg = LearnCfg()):
    # Resolve paths
    if prior_path is None:
        prior_path = str(resolve_priors_file("note_neighbors_prior.json"))
    if learned_path is None:
        ensure_data_dir_exists("learning")
        learned_path = str(path_under_data("learning", "note_neighbors_learned.json"))
    if serving_path is None:
        ensure_data_dir_exists("learning")
        serving_path = str(path_under_data("learning", "note_neighbors_serving.json"))

    prior = load_json(Path(prior_path))
    learned_raw = load_json(Path(learned_path))
    learned: Dict[EdgeKey, LearnRow] = {k: LearnRow(**v) for k, v in learned_raw.items()}

    def _apply(pair_list, sig_key):
        for a, b in pair_list:
            ek = _ek(a, b)
            row = learned.get(ek, LearnRow())
            signals = {sig_key: 1}
            if (a, b) in embeds: signals["embed_sim"] = embeds[(a, b)]
            if (b, a) in embeds: signals["embed_sim"] = embeds[(b, a)]
            row = update_edge(a, b, signals, row, cfg)
            learned[ek] = row

    _apply(seed_pairs, "co_mention")
    _apply(selected_pairs, "co_select")
    _apply(good_outcomes, "good_outcome")

    # Persist learned deltas and merged serving (under ./data/learning/)
    save_json(Path(learned_path), {k: asdict(v) for k, v in learned.items()})
    serving = merge_serving(prior, {k: asdict(v) for k, v in learned.items()}, cfg)
    save_json(Path(serving_path), serving)
