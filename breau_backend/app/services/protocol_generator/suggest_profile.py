# breau_backend/app/services/protocol_generator/suggest_profile.py
from __future__ import annotations
from typing import Optional, Tuple
from breau_backend.app.schemas import BrewSuggestRequest, PourStyle, Agitation
from .parser import parse_ratio_den
from .note_loader import slurry_offset_c


from .note_loader import blend_predicted_notes as _blend_predicted_notes

def blend_predicted_notes(*args, **kwargs):
    """
    Accepts any of these call shapes (positional or keyword):
      blend_predicted_notes(priors_for_cluster, predicted, goal_tags, top_k=6, filter_=..., brewer=...)
      blend_predicted_notes(priors_for_cluster=..., predicted=..., goal_tags=..., top_k=6, ...)
      blend_predicted_notes(goals=[...], ...)   # alias used in older code
    and delegates to the tolerant helper that accepts top_k and returns a 4‑tuple.
    """
    # Normalize positional → keyword
    # Expected positional order: (priors_for_cluster, predicted, goal_tags)
    arg_names = ["priors_for_cluster", "predicted", "goal_tags"]
    for i, name in enumerate(arg_names):
        if i < len(args) and name not in kwargs:
            kwargs[name] = args[i]

    # Support alias: some callers pass goals= instead of goal_tags=
    if "goal_tags" not in kwargs and "goals" in kwargs:
        kwargs["goal_tags"] = kwargs.pop("goals")

    # Pass through everything (including top_k, filter_/brewer, etc.)
    return _blend_predicted_notes(**kwargs)

# What it does:
# Map a Brewer geometry to a user-facing method label (keeps UI consistent).
def _method_from_brewer(brewer) -> str:
    if not brewer:
        return "pour-over"
    try:
        gt = brewer.geometry_type.value
    except Exception:
        gt = "conical"
    return {
        "conical": "v60-style",
        "flat": "flatbed",
        "hybrid": "hybrid",
        "immersion": "clever-style",
        "basket": "basket",
    }.get(gt, "pour-over")

# What it does:
# Choose a default pour style (spiral vs segmented) that matches geometry.
def _default_style(brewer) -> PourStyle:
    try:
        return PourStyle.SEGMENTED if brewer and brewer.geometry_type.value == "flat" else PourStyle.SPIRAL
    except Exception:
        return PourStyle.SPIRAL

# What it does:
# Predict a baseline drawdown based on filter permeability (fast/medium/slow).
def _baseline_expected_drawdown(filter_) -> int:
    try:
        p = filter_.permeability.value if filter_ else "medium"
    except Exception:
        p = "medium"
    return 165 if p == "fast" else (240 if p == "slow" else 195)

# What it does:
# Return a short filter blurb to surface "why" in the UI.
def _filter_hint(filter_) -> Optional[str]:
    try:
        p = filter_.permeability.value if filter_ else "medium"
    except Exception:
        p = "medium"
    if p == "fast":
        return "fast filter → clarity, shorter contact"
    if p == "slow":
        return "slow filter → more contact, fuller body"
    return "medium filter"

# What it does:
# Resolve cluster components and all baselines (ratio, temp, drawdown, method, filter_hint, style).
def resolve_cluster_and_baselines(
    req: BrewSuggestRequest,
) -> Tuple[Optional[str], Optional[str], Optional[str], float, int, int, str, Optional[str], PourStyle]:
    ratio_den = parse_ratio_den(getattr(req, "ratio", "1:15") or "1:15")
    # baseline kettle target = request.temp or 92, then add small slurry offset
    temperature_c = int(round((getattr(req, "temperature_c", None) or 92) + (slurry_offset_c() or 0.0)))
    expected_dd = _baseline_expected_drawdown(getattr(req, "filter", None))
    method = _method_from_brewer(getattr(req, "brewer", None))
    filter_hint = _filter_hint(getattr(req, "filter", None))
    style = _default_style(getattr(req, "brewer", None))

    # cluster pieces
    filt_perm = None
    try:
        fp = getattr(getattr(req, "filter", None), "permeability", None)
        filt_perm = fp.value if fp is not None else None
    except Exception:
        pass

    bean = getattr(req, "bean", None)
    process = getattr(req, "bean_process", None) or (getattr(bean, "process", None) if bean else None)
    roast = getattr(req, "roast_level", None) or (getattr(bean, "roast_level", None) if bean else None)

    return process, roast, filt_perm, ratio_den, temperature_c, expected_dd, method, filter_hint, style
