# breau_backend/app/services/protocol_generator/note_blend.py
from __future__ import annotations
from typing import List, Dict, Tuple
from breau_backend.app.schemas import PredictedNote
from breau_backend.app.services.nlp.note_ranker import rank_notes as _semantic_rank
from .weighting import goal_pairs_to_dicts

# Why priors matter:
# When goals are sparse or ambiguous, priors stabilize predictions.
# We seed / boost prior notes so suggestions remain familiar + explainable.
PRIOR_SEED_CONF: float = 0.40
PRIOR_BOOST_X: float   = 1.30

# Purpose:
# Rebalance predicted notes with priors:
# - If nothing predicted, seed with top priors at a base confidence.
# - If predicted exists, boost any prior hits (cap at 0.99), keep rationale.
def _rebalance_with_priors(
    predicted: List[PredictedNote] | List[Dict],
    priors_list: List[str],
) -> List[PredictedNote]:
    # normalize to list[dict]
    dicts: List[Dict] = []
    for it in predicted or []:
        if hasattr(it, "model_dump"):
            dicts.append(it.model_dump())
        elif isinstance(it, dict):
            dicts.append(it)
        else:
            try:
                dicts.append(dict(it))
            except Exception:
                pass

    # nothing predicted? seed from priors
    if not dicts:
        seeded = [{"label": n, "confidence": PRIOR_SEED_CONF, "rationale": "prior"}
                  for n in (priors_list or [])][:3]
        return [PredictedNote(**d) for d in seeded]

    boost = set(priors_list or [])
    out: List[Dict] = []
    for it in dicts:
        c = float(it.get("confidence", 0.2))
        lab = it.get("label", "")
        if lab in boost:
            c = max(c, PRIOR_SEED_CONF)
            c = min(c * PRIOR_BOOST_X, 0.99)
            it["rationale"] = ((it.get("rationale") or "") + " · prior+").strip()
        it["confidence"] = round(c, 3)
        out.append(it)

    # ensure at least 3 outputs by backfilling missing priors
    have = {x.get("label") for x in out}
    for n in priors_list or []:
        if len(out) >= 3:
            break
        if n not in have:
            out.append({"label": n, "confidence": PRIOR_SEED_CONF, "rationale": "prior seed"})

    out.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
    return [PredictedNote(**d) for d in out[:3]]

# Purpose:
# Blend candidate notes with semantic re-ranking and prior boosts.
# Inputs:
#   - cands: [(note, score, dbg), ...] from note_loader
#   - mg_goals: [("increase florality", weight), ...]
#   - goal_tags: tag list guiding similarity
#   - priors_notes: prior note labels for the cluster
def blend_predicted_notes(
    cands: List[Tuple[str, float, Dict]],
    mg_goals: List[tuple[str, float]],
    goal_tags: List[str],
    priors_notes: List[str],
) -> List[PredictedNote]:
    # normalize candidate scores to [0..1] for downstream ranker
    if cands:
        min_s = min(s for _, s, _ in cands)
        max_s = max(s for _, s, _ in cands)
        rng = max(1e-9, max_s - min_s)
        norm = [(n, (s - min_s) / rng, dbg) for (n, s, dbg) in cands]
    else:
        norm = []

    # light semantic re-rank using deterministic features
    goal_dicts = goal_pairs_to_dicts(mg_goals)
    sem = _semantic_rank(goal_dicts, goal_tags, note_profiles=None)


    # fuse into PredictedNote list, then rebalance with priors
    top = [{"label": n, "confidence": float(s), "rationale": (dbg.get("why") if isinstance(dbg, dict) else None)}
           for (n, s, dbg) in sem]
    return _rebalance_with_priors(top, priors_notes)
