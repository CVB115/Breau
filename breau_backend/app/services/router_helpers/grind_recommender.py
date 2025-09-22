from __future__ import annotations
from typing import Dict, Any, Optional
from .gear_catalog import find_grinder_by_alias, get_brewer, get_filter, sync_grinders_into_grind_math

# ensure JSON presets are visible to grind_math
sync_grinders_into_grind_math()

from breau_backend.app.flavour.engine.grind_math import setting_for_microns_grinder

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _brewer_factor(brewer: Optional[Dict[str, Any]]) -> float:
    if not brewer: return 1.0
    return float(brewer.get("flow_factor", 1.0))

def _filter_factor(filt: Optional[Dict[str, Any]]) -> float:
    """
    Effective permeability multiplier for grind targeting.
    Combines the existing numeric `permeability_factor` with inferred
    material/thickness multipliers (if present). Conservative defaults.
    """
    if not filt:
        return 1.0

    # base: keep your current numeric knob if provided
    base = float(filt.get("permeability_factor", 1.0))

    # normalize material/thickness from various shapes
    material_raw = (filt.get("material") or "").strip().lower()
    thickness = (filt.get("thickness") or "").strip().lower()  # accepts "thin|std|medium|thick"

    # map common strings to canonical buckets
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
        material = material_raw or "paper_bleached"

    # empirical multipliers (flow ↑ → factor > 1; matches literature & vendor notes)
    MAT_MULT = {
        "paper_bleached":   1.00,
        "paper_unbleached": 1.10,  # often drains a bit faster in tests
        "abaca":            1.06,  # marketed faster flow
        "hemp":             1.05,
        "cloth_cotton":     1.15,  # faster flow, more oils
        "metal_stainless":  1.35,  # much faster, most oils/fines
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

    return base * MAT_MULT.get(material, 1.0) * THICK_MULT.get(thickness, 1.0)


def _base_target_micron(geometry: str) -> float:
    g = (_norm(geometry))
    if g == "flatbed":   return 750.0
    if g == "immersion": return 600.0
    # default (conical / percolation pour-over)
    return 800.0

def _adjust_by_bean(target: float, bean: Optional[Dict[str, Any]]) -> float:
    if not bean: return target
    roast = _norm(bean.get("roast_level"))
    process = _norm(bean.get("process"))
    # roast: lighter -> slightly finer; darker -> slightly coarser
    if roast in ("light", "light-medium", "light+"):
        target *= 0.95
    elif roast in ("dark", "dark+"):
        target *= 1.05
    # process: naturals/anaerobic sometimes extract tail-heavy -> go a bit coarser
    if process in ("natural", "anaerobic", "honeys", "honey"):
        target *= 1.03
    return target

def recommend_grind(bean: Optional[Dict[str, Any]], gear_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
      {
        "target_micron": float,
        "setting": float,
        "label": "C40 ≈ 22 clicks (~820 µm)",
        "scale": {"type": "...", "min": ..., "max": ..., "step": ...}
      }
    """
    brewer_id = (gear_snapshot.get("brewer") or {}).get("id")
    filter_id = (gear_snapshot.get("filter") or {}).get("id")
    grinder   = (gear_snapshot.get("grinder") or {})  # may include user calibration

    # Brewer/filter factors from catalog
    brewer_obj = get_brewer(brewer_id) or {}
    filter_obj = get_filter(filter_id) or {}

    geometry = brewer_obj.get("geometry") or "conical"
    target = _base_target_micron(geometry)
    target *= _brewer_factor(brewer_obj)
    target *= _filter_factor(filter_obj)
    target = _adjust_by_bean(target, bean)

    # Try to enrich grinder dict from catalog (for model presets/scale if user-supplied is sparse)
    brand = grinder.get("brand"); model = grinder.get("model")
    cat   = find_grinder_by_alias(brand, model)
    # Merge non-destructively: user fields (calibration_points, user_scale_*, scale_type) win
    enriched = dict(cat or {})
    enriched.update(grinder or {})

    # Fall back to burr_type from either source
    if "burr_type" not in enriched:
        enriched["burr_type"] = (grinder.get("burr_type") or (cat or {}).get("burr_type") or "conical")

    # Ask grind_math for a setting; it uses: user calibration → model preset → burr-type heuristic
    setting = float(setting_for_microns_grinder(enriched, target))

    scale = (enriched.get("scale") or
             {"type": enriched.get("scale_type", "numbers"), "min": enriched.get("user_scale_min", 0), "max": enriched.get("user_scale_max", 40), "step": 1})

    # Build a readable label
    scale_type = scale.get("type") or "numbers"
    unit = "clicks" if scale_type == "clicks" else ("marks" if scale_type in ("dial", "ring", "numbers") else "units")
    label_model = (enriched.get("model") or model or "").strip() or (cat or {}).get("model") or "Grinder"
    label = f"{label_model} ≈ {setting:g} {unit} (~{round(target)} µm)"

    return {
        "target_micron": target,
        "setting": setting,
        "label": label,
        "scale": scale
    }
