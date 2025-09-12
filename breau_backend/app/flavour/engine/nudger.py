# breau_backend/app/flavour/engines/nudger.py
from __future__ import annotations
from typing import Dict, Any, Tuple, List

# Purpose:
# Map **goal traits → small variable deltas** using a policy matrix + constraints.
# Produces deltas over slurry/ratio/agitation, then clips to per-session + method caps.
# Returns (final_vars, clips) and short “reasons” strings for explain UI.  :contentReference[oaicite:8]{index=8}

AGIT_LEVELS = ["low", "medium", "high"]

def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

# Purpose:
# Step agitation level by an integer delta within allowed levels.
def _step_agitation(level: str, delta_steps: int) -> str:
    try:
        idx = AGIT_LEVELS.index(level)
    except ValueError:
        idx = 1
    idx = _clip(idx + delta_steps, 0, len(AGIT_LEVELS)-1)
    return AGIT_LEVELS[int(idx)]

# Purpose:
# Normalize goal vector to L2=1 with a small floor so secondary goals have effect.
def _norm_goal_vec(gv: Dict[str, float]) -> Dict[str, float]:
    import math
    vals = list(gv.values())
    if not vals:
        return {}
    norm = math.sqrt(sum(v*v for v in vals)) or 1.0
    scaled = {k: (v / norm) for k, v in gv.items()}
    # floor to ensure secondaries have a say
    for k, v in scaled.items():
        if abs(v) < 0.2:
            scaled[k] = 0.2 if v > 0 else -0.2 if v < 0 else 0.0
    return scaled

class Nudger:
    # Purpose:
    # policy: {"goal_variable_matrix": {...}, "caps": {...}, "constraints": {...}}
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy

    # Purpose:
    # Convert a goal vector to raw deltas + reasons using linear combo.
    def propose(self, goal_vec: Dict[str, float], base_vars: Dict[str, Any],
                context: Dict[str, Any], profile: Dict[str, Any]) -> Tuple[Dict[str, float], List[str]]:
        gv = _norm_goal_vec(goal_vec)
        M = self.policy["goal_variable_matrix"]
        delta = {"slurry_c": 0.0, "ratio_den": 0.0, "agitation_early": 0.0, "agitation_late": 0.0}
        reasons = []
        for trait, w in gv.items():
            if trait not in M:
                continue
            for var, coeff in M[trait].items():
                if var not in delta:
                    # ignore filter_speed/pour_segmented here; handled by builder heuristics for now
                    continue
                delta[var] += w * coeff * 0.2  # small base scale
                reasons.append(f"{trait}→{var}:{w:+.2f}×{coeff:+.2f}")
        return delta, reasons

    # Purpose:
    # Apply method constraints and per-session caps; return final vars + any clips.
    def apply_and_clip(self, base_vars: Dict[str, Any], delta: Dict[str, float],
                       context: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        caps = self.policy["caps"]
        geom = (context.get("brewer") or {}).get("geometry_type", "conical")
        cons = self.policy["constraints"].get(geom, self.policy["constraints"]["conical"])
        clips: List[str] = []

        # Slurry target C
        slurry = float(base_vars.get("slurry_c", base_vars.get("temperature_c", 92)))
        d_slurry = max(-caps["delta_slurry_c_per_session"], min(caps["delta_slurry_c_per_session"], delta.get("slurry_c", 0.0)))
        slurry_final = _clip(slurry + d_slurry, cons["slurry_c_min"], cons["slurry_c_max"])
        if slurry_final != slurry + d_slurry:
            clips.append("slurry_c clipped to method constraint")

        # Ratio den
        ratio_den = float(base_vars.get("ratio_den", 15))
        d_ratio = max(-caps["delta_ratio_den_per_session"], min(caps["delta_ratio_den_per_session"], delta.get("ratio_den", 0.0)))
        ratio_final = _clip(ratio_den + d_ratio, cons["ratio_den_min"], cons["ratio_den_max"])
        if ratio_final != ratio_den + d_ratio:
            clips.append("ratio_den clipped to method constraint")

        # Agitation early/late (step per session)
        ag_early = base_vars.get("agitation_early", base_vars.get("agitation", "medium"))
        ag_late  = base_vars.get("agitation_late",  base_vars.get("agitation", "medium"))
        step_cap = int(caps["agitation_step_per_session"])
        de = int(max(-step_cap, min(step_cap, round(delta.get("agitation_early", 0.0)))))
        dl = int(max(-step_cap, min(step_cap, round(delta.get("agitation_late", 0.0)))))
        ag_early_final = _step_agitation(ag_early, de)
        ag_late_final  = _step_agitation(ag_late, dl)

        final_vars = dict(base_vars)
        final_vars.update({
            "slurry_c": slurry_final,
            "ratio_den": ratio_final,
            "agitation_early": ag_early_final,
            "agitation_late": ag_late_final
        })
        return final_vars, clips
