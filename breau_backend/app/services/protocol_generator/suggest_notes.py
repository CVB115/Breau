# breau_backend/app/services/protocol_generator/suggest_notes.py
from __future__ import annotations
from typing import List, Tuple

from breau_backend.app.schemas import (
    BrewSuggestRequest, PredictedNote,
    Agitation, PourStepIn
)

# Prior + selection utilities
from .note_loader import select_candidate_notes, cluster_key, get_prior_notes
from .note_blend import blend_predicted_notes
from .priors_dynamic import get_dynamic_notes_for


# Build dynamic + static priors with safe fallbacks
def collect_priors_with_fallbacks(
    process: str | None,
    roast: str | None,
    filt_perm: str | None,
) -> tuple[list[str], list[str], list[str]]:
    dynamic_priors: list[str] = []
    static_priors: list[str] = []

    exact_cluster = cluster_key(process, roast, filt_perm)
    dyn_pairs = get_dynamic_notes_for(exact_cluster, top_k=5) or []
    dynamic_priors = [str(n[0]) for n in dyn_pairs if n and n[0]]
    static_priors = get_prior_notes(exact_cluster) or []

    if (not dynamic_priors or not static_priors) and (process and roast):
        for fp in ("fast", "medium", "slow"):
            c = cluster_key(process, roast, fp)
            if not dynamic_priors:
                d2 = get_dynamic_notes_for(c, top_k=5) or []
                for name, _cnt in d2:
                    if name and name not in dynamic_priors:
                        dynamic_priors.append(str(name))
            if not static_priors:
                s2 = get_prior_notes(c) or []
                for name in s2:
                    if name and name not in static_priors:
                        static_priors.append(str(name))
            if dynamic_priors and static_priors:
                break

    combined = list(dict.fromkeys(dynamic_priors + static_priors))
    return dynamic_priors, static_priors, combined


# Main prediction pipeline for builder
# Main prediction pipeline for builder
def select_candidates_and_predict(
    *,
    req: BrewSuggestRequest,
    goal_pairs: list[tuple[str, float]],
    goal_tags: list[str],
    trait_weights: dict,
    priors_for_cluster: list[str],
) -> tuple[
    list[tuple[str, float, dict]],
    list[PourStepIn],
    Agitation,
    Agitation,
    list[PredictedNote],
]:
    """
    Returns:
      cands: [(note, score, dbg)]
      pours: []  (intentionally empty here to avoid invalid PourStepIn validation)
      early_enum, late_enum: reasonable defaults
      predicted_notes: List[PredictedNote]
    """
    # --- 1) build phrases for legacy selectors ---
    phrases = [g for (g, _w) in (goal_pairs or [])]

    # --- 2) call selector (support both old & new shapes) ---
    sel_result = select_candidate_notes(
        priors_for_cluster=priors_for_cluster,
        predicted=[],
        goal_tags=goal_tags,
        top_k=6,
        goals=phrases,
        req=req,
        trait_weights=trait_weights,
    )

    # normalize result shape
    if isinstance(sel_result, list):
        # new shape: just candidates
        cands = sel_result
        early_enum = Agitation.MODERATE
        late_enum = Agitation.MODERATE
    elif isinstance(sel_result, tuple):
        # legacy 4‑tuple: (cands, pours, early_enum, late_enum)
        cands = sel_result[0] if len(sel_result) >= 1 else []
        early_enum = sel_result[2] if len(sel_result) >= 3 else Agitation.MODERATE
        late_enum = sel_result[3] if len(sel_result) >= 4 else Agitation.MODERATE
    else:
        cands = []
        early_enum = Agitation.MODERATE
        late_enum = Agitation.MODERATE

    # --- IMPORTANT: never pass through half‑formed pours from this stage ---
    pours: list[PourStepIn] = []

    # --- 3) predict up to 3 notes (semantic blend + priors) ---
    mg_goals = [(g, w) for (g, w) in (goal_pairs or [])]
    predicted_notes = blend_predicted_notes(
        cands=cands,
        mg_goals=mg_goals,
        goal_tags=goal_tags or [],
        priors_notes=priors_for_cluster,
    )

    return cands, pours, early_enum, late_enum, predicted_notes
