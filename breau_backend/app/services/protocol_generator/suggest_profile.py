# breau_backend/app/services/protocol_generator/suggest_profile.py
from __future__ import annotations
from typing import Optional, Tuple
from breau_backend.app.schemas import BrewSuggestRequest, PourStyle, Agitation
from .parser import parse_ratio_den
from .note_loader import slurry_offset_c


from .note_loader import blend_predicted_notes as _blend_predicted_notes
# --- Filter material/thickness helper ----------------------------------------
def _material_thickness_multiplier(material_raw: str = "", thickness: str = "") -> float:
    """
    Convert material+thickness into a permeability multiplier.
    > 1.0 = faster flow (shorter drawdown), < 1.0 = slower flow.
    """
    material_raw = (material_raw or "").strip().lower()
    thickness = (thickness or "").strip().lower()  # "thin|std|medium|thick" or ""

    if material_raw in ("paper", "paper_bleached", "bleached"):
        material = "paper_bleached"
    elif material_raw in ("paper_unbleached", "unbleached", "brown"):
        material = "paper_unbleached"
    elif "abaca" in material_raw:
        material = "abaca"
    elif "hemp" in material_raw:
        material = "hemp"
    elif "cloth" in material_raw or "cotton" in material_raw:
        material = "cloth_cotton"
    elif "titanium" in material_raw:
        material = "metal_titanium"
    elif "metal" in material_raw or "stainless" in material_raw or "mesh" in material_raw:
        material = "metal_stainless"
    elif "poly" in material_raw or "synthetic" in material_raw:
        material = "synthetic_poly"
    else:
        material = "paper_bleached"

    MAT_MULT = {
        "paper_bleached":   1.00,
        "paper_unbleached": 1.10,  # often drains a bit faster
        "abaca":            1.06,  # marketed faster
        "hemp":             1.05,
        "cloth_cotton":     1.15,  # faster & more oils
        "metal_stainless":  1.35,  # much faster & most oils/fines
        "metal_titanium":   1.35,
        "synthetic_poly":   1.20,
    }
    THICK_MULT = {
        "thin":   1.05,
        "std":    1.00,
        "medium": 1.00,
        "thick":  0.93,
        "":       1.00,
    }
    return MAT_MULT.get(material, 1.0) * THICK_MULT.get(thickness, 1.0)

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
    """
    Base expected drawdown seconds.
    Step 1: use permeability tier ('fast'/'medium'/'slow').
    Step 2: modulate by material+thickness (faster material → shorter time).
    """
    # Step 1 — permeability tier
    try:
        p = filter_.permeability.value if filter_ else "medium"
    except Exception:
        p = "medium"

    # sensible defaults (tweak if your project’s targets differ)
    base = 165 if p == "fast" else (240 if p == "slow" else 195)

    # Step 2 — material/thickness modulation (inverse: faster → shorter)
    try:
        mat = getattr(filter_, "material", None) or ""
        thick = getattr(filter_, "thickness", None) or ""
        eff_mult = _material_thickness_multiplier(mat, thick)
        base = int(round(base / max(0.5, min(2.0, eff_mult))))  # clamp to avoid extremes
    except Exception:
        pass

    return max(90, base)  # keep a sane floor


# What it does:
# Return a short filter blurb to surface "why" in the UI.
def _filter_hint(filter_) -> Optional[str]:
    try:
        p = getattr(filter_.permeability, "value", None) or "medium"
    except Exception:
        p = "medium"

    mat = (getattr(filter_, "material", None) or "").replace("_", " ").strip()
    pieces = []
    if p == "fast":
        pieces.append("fast filter → more clarity, shorter contact")
    elif p == "slow":
        pieces.append("slow filter → fuller body, longer contact")
    else:
        pieces.append("medium flow filter")

    if mat:
        pieces.append(f"material: {mat}")

    thick = (getattr(filter_, "thickness", None) or "").strip().lower()
    if thick in ("thin", "thick"):
        pieces.append(f"thickness: {thick}")

    return " · ".join(pieces) if pieces else None


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
