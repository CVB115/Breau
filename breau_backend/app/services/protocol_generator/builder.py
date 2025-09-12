from __future__ import annotations
from breau_backend.app.schemas import BrewSuggestRequest, BrewSuggestion

# Step modules (all behavior implemented in these tiny files)
from .suggest_profile import resolve_cluster_and_baselines
from .suggest_goals import resolve_goals_and_traits
from .suggest_notes import collect_priors_with_fallbacks, select_candidates_and_predict
from .suggest_recipe import personalize_overlays_and_tweaks
from .suggest_out import finalize_pours_and_plan, make_alternative_variant, assemble_response


def build_suggestion(req: BrewSuggestRequest) -> BrewSuggestion:
    # 1) Cluster + baselines
    process, roast, filt_perm, ratio_den, temperature_c, expected_dd, method, filter_hint, _style = \
        resolve_cluster_and_baselines(req)

    # 2) Goals/tags/traits
    goal_pairs, goal_tags, trait_weights = resolve_goals_and_traits(req)

    # 3) Priors (dynamic + static, with robust fallbacks)
    dyn_priors, static_priors, priors_for_cluster = collect_priors_with_fallbacks(process, roast, filt_perm)

    # 4) Note candidates + up-to-3 predicted notes (semantic + prior rebalance)
    cands, pours_from_cands, early_enum, late_enum, predicted_notes = select_candidates_and_predict(
        req=req,
        goal_pairs=goal_pairs,
        goal_tags=goal_tags,
        trait_weights=trait_weights,
        priors_for_cluster=priors_for_cluster,
    )

    # 5) Optional overlays + safe agitation tweaks (never fatal)
    temperature_c, expected_dd, early_enum, late_enum = personalize_overlays_and_tweaks(
        req=req,
        temperature_c=temperature_c,
        expected_dd=expected_dd,
        goal_tags=goal_tags,
        ratio_den=ratio_den,
        filt_perm=filt_perm,
        dyn_priors=bool(dyn_priors),
    )

    # 6) Pours, plan, summary line, display fields
    pours, session_plan, notes_text, ratio_str, agitation_overall = finalize_pours_and_plan(
        req=req,
        ratio_den=ratio_den,
        temperature_c=temperature_c,
        early_enum=early_enum,
        late_enum=late_enum,
        filter_hint=filter_hint,
        pours_from_candidates=pours_from_cands,
    )

    # 7) Conservative alternative (clarity_plus/body_plus)
    alt = make_alternative_variant(
        req=req,
        method=method,
        ratio_str=ratio_str,
        temperature_c=temperature_c,
        agitation_overall=agitation_overall,
        filter_hint=filter_hint,
        expected_dd=expected_dd,
        pours=pours,
        notes_text=notes_text,
    )

    # 8) Final response assembly
    return assemble_response(
        req=req,
        method=method,
        ratio_str=ratio_str,
        total_water_g=int(getattr(req, "total_water_g", 240) or 240),
        temperature_c=int(temperature_c),
        agitation_overall=agitation_overall,
        filter_hint=filter_hint,
        expected_dd=expected_dd,
        pours=pours,
        notes_text=notes_text,
        session_plan=session_plan,
        alternative=alt,
        predicted_notes=(predicted_notes or [])[:3],
    )
