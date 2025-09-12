# breau_backend/app/flavour/engines/grind_math.py
from __future__ import annotations
from typing import List, Dict, Optional, Tuple

# Purpose:
# Map grinder **scale settings ↔ micron size** using either:
# - user calibration points (least‑squares line)
# - known presets per grinder model
# - a fallback heuristic by burr type
# Also provides inverse mapping and scale-clamped rounding.  :contentReference[oaicite:4]{index=4}

# --------- Curves & scale metadata (extensible) ----------
# y (micron) = a + b * x(setting)
PRESET_CURVES: Dict[str, Dict] = {
    # Comandante C40 “clicks from zero”
    "comandante c40": {"a": 200.0, "b": 18.0, "scale": {"type": "clicks", "min": 0, "max": 45, "step": 1}},
    # Timemore Sculptor 064S (flat, number ring)
    "sculptor 064s": {"a": 160.0, "b": 14.0, "scale": {"type": "numbers", "min": 0, "max": 50, "step": 1}},
    # Niche Zero (conical dial)
    "niche zero": {"a": 210.0, "b": 17.0, "scale": {"type": "dial", "min": 0, "max": 50, "step": 1}},
    # EK-style dial ring (flat)
    "ek ring": {"a": 120.0, "b": 12.0, "scale": {"type": "ring", "min": 0, "max": 11, "step": 0.1}},
}

def _norm_model_name(model: Optional[str]) -> str:
    return (model or "").strip().lower()

# --------- Fitting ----------
# Purpose:
# Least-squares fit for y = a + b*x. Needs ≥2 points.
def _fit_linear(points: List[Dict[str, float]]) -> Optional[Dict[str, float]]:
    """
    points: [{"setting": float, "micron": float}, ...]
    """
    n = len(points)
    if n < 2:
        return None
    xs = [float(p["setting"]) for p in points]
    ys = [float(p["micron"]) for p in points]
    sx = sum(xs); sy = sum(ys)
    sxx = sum(x*x for x in xs); sxy = sum(x*y for x, y in zip(xs, ys))
    denom = n*sxx - sx*sx
    if abs(denom) < 1e-9:
        return None
    b = (n*sxy - sx*sy) / denom
    a = (sy - b*sx) / n
    return {"a": a, "b": b}

# Purpose:
# Build curve and scale metadata from a grinder dict with precedence:
# calibration fit → model preset → burr heuristic.
def _curve_from(grinder: Dict) -> Tuple[Dict[str, float], Dict]:
    """
    Returns (curve, scale_meta)
      curve = {"a": float, "b": float}
      scale_meta = {"type": "...", "min": ..., "max": ..., "step": ...}
    """
    points = grinder.get("calibration_points") or []
    fit = _fit_linear(points)
    if fit:
        scale_meta = {
            "type": grinder.get("scale_type", "numbers"),
            "min": grinder.get("user_scale_min", 0),
            "max": grinder.get("user_scale_max", 40),
            "step": 1,
        }
        return fit, scale_meta

    preset = PRESET_CURVES.get(_norm_model_name(grinder.get("model")))
    if preset:
        return {"a": float(preset["a"]), "b": float(preset["b"])}, preset["scale"]

    # Heuristic if no preset: conical vs flat
    bt = (grinder.get("burr_type") or "").lower()
    curve = {"a": 180.0, "b": 16.0} if bt == "conical" else {"a": 140.0, "b": 12.0}
    scale_meta = {
        "type": grinder.get("scale_type", "numbers"),
        "min": grinder.get("user_scale_min", 0),
        "max": grinder.get("user_scale_max", 40),
        "step": 1,
    }
    return curve, scale_meta

# --------- Forward / inverse transforms ----------
# Purpose:
# Estimate microns for a given setting, accepting optional explicit curve/preset.
def microns_for_setting(
    setting: float,
    calibration_points: List[Dict[str, float]] | None = None,
    preset_curve: Dict[str, float] | None = None,
    burr_type: str | None = None,
    model: str | None = None,
    scale_meta: Dict | None = None
) -> float:
    """
    If you already have the grinder dict, call microns_for_setting_grinder(grinder, setting).
    """
    fit = _fit_linear(calibration_points or [])
    if fit:
        return _clip(fit["a"] + fit["b"]*float(setting))

    if preset_curve and "a" in preset_curve and "b" in preset_curve:
        return _clip(float(preset_curve["a"]) + float(preset_curve["b"])*float(setting))

    # fallback by burr/model
    if model:
        preset = PRESET_CURVES.get(_norm_model_name(model))
        if preset:
            return _clip(preset["a"] + preset["b"]*float(setting))

    bt = (burr_type or "").lower()
    a, b = (180.0, 16.0) if bt == "conical" else (140.0, 12.0)
    return _clip(a + b*float(setting))

# Purpose:
# Forward transform using a grinder dict (handles all precedence inside).
def microns_for_setting_grinder(grinder: Dict, setting: float) -> float:
    curve, _scale = _curve_from(grinder)
    return _clip(curve["a"] + curve["b"]*float(setting))

# Purpose:
# Inverse mapping: find recommended setting for a target micron, clamped to scale.
def setting_for_microns_grinder(grinder: Dict, target_micron: float) -> float:
    """
    Inverse mapping: recommended grinder setting for a desired micron.
    """
    curve, scale = _curve_from(grinder)
    b = curve["b"] if abs(curve["b"]) > 1e-9 else 1.0
    raw = (float(target_micron) - curve["a"]) / b
    # clamp to scale min/max, then round to nearest step
    return _round_to_scale(_clamp(raw, scale.get("min", 0), scale.get("max", 50)), scale.get("step", 1))

def _round_to_scale(x: float, step: float) -> float:
    if step <= 0:
        return x
    return round(x / step) * step

def _clip(x: float, lo: float = 150.0, hi: float = 1400.0) -> float:
    return max(lo, min(hi, x))

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
