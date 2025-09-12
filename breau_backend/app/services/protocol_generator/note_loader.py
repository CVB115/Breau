# breau_backend/app/services/protocol_generator/note_loader.py

from __future__ import annotations
from typing import List, Tuple, Dict, Iterable, Optional

from .note_loader_data import PRIOR_NOTES_BY_CLUSTER
from .note_blend import blend_predicted_notes as _blend_semantic


# ----------- Basics -----------

def cluster_key(process: Optional[str], roast: Optional[str], filt_perm: Optional[str]) -> str:
    return f"{(process or 'unknown').strip().lower()}:{(roast or 'unknown').strip().lower()}:{(filt_perm or 'unknown').strip().lower()}"

def goals_to_tags(phrases: Iterable[str]) -> List[str]:
    tags: List[str] = []
    for ph in phrases or []:
        s = (ph or "").strip().lower()
        if not s:
            continue
        if "floral" in s or "flower" in s:
            t = "increase florality"
        elif "clarity" in s or "clean" in s:
            t = "more clarity"
        elif "body" in s and "less" in s:
            t = "less body"
        elif "body" in s:
            t = "more body"
        elif "sweet" in s:
            t = "more sweetness"
        elif "bitter" in s and "less" in s:
            t = "less bitterness"
        else:
            t = s
        if t not in tags:
            tags.append(t)
    return tags

def get_prior_notes(cluster: str) -> List[str]:
    return list(PRIOR_NOTES_BY_CLUSTER.get(cluster, []))

def slurry_offset_c(filter_=None, brewer=None) -> int:
    try:
        filt_perm = getattr(filter_, "permeability", None)
        filt_perm = getattr(filt_perm, "value", filt_perm)
    except Exception:
        filt_perm = None
    if isinstance(filter_, dict):
        filt_perm = filter_.get("permeability") or filt_perm
    if (filt_perm or "").lower() == "fast":
        return -1
    elif (filt_perm or "").lower() == "slow":
        return +1
    return 0


# ----------- Core Candidate Selector -----------

def select_candidate_notes(
    *,
    priors_for_cluster: Optional[List[str]] = None,
    predicted: Optional[List[Tuple[str, float]]] = None,
    goal_tags: Optional[List[str]] = None,
    top_k: int = 6,
    **kwargs,
) -> List[Tuple[str, float, Dict]]:
    priors = list(priors_for_cluster or [])
    cands: List[Tuple[str, float, Dict]] = [(n, 0.50, {"src": "prior"}) for n in priors]

    if predicted:
        seen = {n for n, _, _ in cands}
        for name, score in predicted:
            if not name:
                continue
            s = float(score or 0.60)
            if name in seen:
                idx = next(i for i, (nn, _, _) in enumerate(cands) if nn == name)
                oldn, olds, dbg = cands[idx]
                cands[idx] = (oldn, max(olds, s), {**dbg, "why": "predicted+prior"})
            else:
                cands.insert(0, (name, s, {"src": "pred"}))
                seen.add(name)

    return cands[:max(3, top_k)]


# ----------- Legacy-Compatible Blender -----------

def blend_predicted_notes(*args, **kwargs):
    """
    This wrapper handles:
    - New-style calls: cands=..., mg_goals=..., goal_tags=..., priors_notes=...
    - Legacy-style calls: priors_for_cluster=..., predicted=..., goal_tags=..., top_k=...
    """

    # New-style detected
    if "cands" in kwargs and "mg_goals" in kwargs and "priors_notes" in kwargs:
        return _blend_semantic(
            kwargs["cands"],
            kwargs.get("mg_goals") or [],
            kwargs.get("goal_tags") or [],
            kwargs["priors_notes"]
        )

    # Legacy-style fallback
    priors = kwargs.get("priors_for_cluster") or []
    predicted = kwargs.get("predicted") or []
    goal_tags = kwargs.get("goal_tags") or kwargs.get("goals") or []
    top_k = int(kwargs.get("top_k", 6))

    cands = select_candidate_notes(
        priors_for_cluster=priors,
        predicted=predicted,
        goal_tags=goal_tags,
        top_k=top_k,
        **kwargs,
    )

    mg_goals = [(t, 1.0) for t in goal_tags]
    return _blend_semantic(cands, mg_goals, goal_tags, priors)
