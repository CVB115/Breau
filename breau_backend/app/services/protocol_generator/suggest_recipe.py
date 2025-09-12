# breau_backend/app/services/protocol_generator/suggest_recipe.py
from __future__ import annotations
from typing import Tuple
from breau_backend.app.schemas import BrewSuggestRequest, Agitation

# Optional overlays; if missing, we return defaults safely.
try:
    from breau_backend.app.services.learning.overlays import compute_overlays  # type: ignore
except Exception:  # pragma: no cover
    compute_overlays = None

# What it does:
# Clamp brew temperature to safe bounds (°C).
def _clamp_temp(t_c: int, lo: int = 85, hi: int = 96) -> int:
    return max(lo, min(hi, int(t_c)))

# What it does:
# Apply optional personalization overlays and return updated temp/drawdown/agitations.
def personalize_overlays_and_tweaks(
    *,
    req: BrewSuggestRequest,
    temperature_c: int,
    expected_dd: int,
    goal_tags: list[str],
    ratio_den: float,
    filt_perm: str | None,
    dyn_priors: bool,
) -> Tuple[int, int, Agitation, Agitation]:
    early, late = Agitation.MODERATE, Agitation.MODERATE
    try:
        user_id = getattr(req, "user_id", None) or getattr(req, "profile_id", None)

        geometry = None
        try:
            g = getattr(getattr(req, "brewer", None), "geometry_type", None)
            geometry = g.value if g else None
        except Exception:
            pass

        if compute_overlays and user_id and goal_tags:
            ctx = {
                "process": getattr(req, "bean_process", None) or getattr(getattr(req, "bean", None), "process", None),
                "roast": getattr(req, "roast_level", None) or getattr(getattr(req, "bean", None), "roast_level", None),
                "ratio_den": float(ratio_den),
                "temp_bucket": int(temperature_c),
                "filter_perm": filt_perm,
                "geometry": geometry,
                "priors_used": bool(dyn_priors),
            }
            ov = compute_overlays(user_id=user_id, goal_tags=goal_tags, context=ctx)

            # Apply deltas (temp / grind→drawdown / late-agitation)
            if "temp_delta" in ov:
                temperature_c = _clamp_temp(int(round(temperature_c + ov["temp_delta"])))

            if "grind_delta" in ov and isinstance(expected_dd, (int, float)):
                # negative grind_delta => finer => longer drawdown
                expected_dd = int(round(float(expected_dd) * (1.0 - 0.05 * float(ov["grind_delta"]))))

            if "agitation_delta" in ov:
                if late == Agitation.MODERATE and ov["agitation_delta"] < 0:
                    late = Agitation.GENTLE
                elif late == Agitation.MODERATE and ov["agitation_delta"] > 0:
                    late = getattr(Agitation, "ROBUST", Agitation.MODERATE)

            # --- NEW: add a tiny breadcrumb for UI if anything actually changed ---
            try:
                crumb_bits = []
                if isinstance(ov, dict):
                    td = ov.get("temp_delta")
                    gd = ov.get("grind_delta")
                    ad = ov.get("agitation_delta")
                    if isinstance(td, (int, float)) and abs(float(td)) > 1e-9:
                        crumb_bits.append(f"Δtemp {float(td):+0.1f}°C")
                    if isinstance(gd, (int, float)) and abs(float(gd)) > 1e-9:
                        crumb_bits.append(f"grind {float(gd):+0.1f}")
                    if isinstance(ad, (int, float)) and abs(float(ad)) > 1e-9:
                        crumb_bits.append("agitation gentler" if float(ad) < 0 else "agitation stronger")
                if crumb_bits:
                    setattr(req, "_explain_breadcrumb", "Personalized: " + ", ".join(crumb_bits))
            except Exception:
                # Never block suggestion if request object is immutable or odd
                pass

    except Exception:
        # overlays are optional; never block suggestion
        pass

    return temperature_c, expected_dd, early, late
