from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir
import glob

# Purpose:
# Keep simple, per‑cohort (process × roast × filter_perm) statistics to improve cold‑starts.
# We maintain an EMA (exponentially weighted moving average) of variable deltas that tended
# to help (weighted by sentiment) and the number of sessions observed.

@dataclass
class CohortConfig:
    root_dir: Path
    alpha: float = 0.2        # EMA smoothing factor
    cap: float = 0.20         # absolute cap on any learned delta
    min_count: int = 6        # need at least this many sessions to seed overlays

# Variables we track across cohorts (same units as L2 overlays)
VAR_KEYS = ("temp_delta", "grind_delta", "agitation_delta")

# Purpose:
# Build a stable key for the cohort bucket from context.
def _key(context: Dict) -> str:
    proc = context.get("process") or "_"
    roast = context.get("roast") or "_"
    filt = context.get("filter_perm") or "_"
    return f"{proc}|{roast}|{filt}"

# Purpose:
# Symmetric clip helper for learned values.
def _clip(v: float, c: float) -> float:
    return -c if v < -c else (c if v > c else v)

class Cohort:
    # Purpose:
    # Ensure storage root exists; keep config.
    def __init__(self, cfg: CohortConfig):
        self.cfg = cfg
        ensure_dir(self.cfg.root_dir)

    # Purpose:
    # Convert cohort key to a file path (file-per-cohort).
    def _path(self, key: str) -> Path:
        return self.cfg.root_dir / f"{key.replace('|','__')}.json"

    # Purpose:
    # Update EMA statistics with one session’s applied nudges and sentiment.
    # We nudge toward deltas that correlated with positive sentiment (and away from negative).
    def update(self, context: Dict, var_nudges: Dict[str, float], sentiment: float):
        key = _key(context)
        p = self._path(key)
        js = read_json(p, {"schema_version":"2025-09-03","key":key,"n":0,"ema":{k:0.0 for k in VAR_KEYS}})
        a = float(self.cfg.alpha)
        n0 = int(js.get("n",0))
        ema = js.get("ema", {})
        for k in VAR_KEYS:
            # If sentiment is exactly 0, give a tiny weight so we still learn sign over time.
            delta = float(var_nudges.get(k, 0.0)) * float(sentiment if sentiment != 0 else 0.1)
            ema[k] = _clip((1-a)*float(ema.get(k,0.0)) + a*delta, self.cfg.cap)
        js["ema"] = ema
        js["n"] = n0 + 1
        write_json(p, js)

    # Purpose:
    # For new users (few sessions), return a gentle seed overlay based on this cohort’s EMA.
    # Optionally bias toward clarity/body goals by attenuating opposing signs.
    def seed_overlay(self, context: Dict, goal_tags: List[str]) -> Dict[str, float]:
        key = _key(context)
        js = read_json(self._path(key), None)
        if not js or int(js.get("n",0)) < self.cfg.min_count:
            return {}
        # Gentle seed scaled to half of cohort EMA
        out = {k: _clip(0.5*float(js["ema"].get(k,0.0)), self.cfg.cap) for k in VAR_KEYS}
        # Goal-aware tilt: soften sign-opposed components for clarity/body asks
        g = [g.lower() for g in (goal_tags or [])]
        if any(k in g for k in ["clarity","floral","citrus_acidity","acidity"]):
            # Favor cooler / gentler for clarity
            if out.get("temp_delta",0.0) > 0: out["temp_delta"] *= 0.5
            if out.get("agitation_delta",0.0) > 0: out["agitation_delta"] *= 0.5
        if any(k in g for k in ["body","syrupy_body","round"]):
            # Favor warmer / more agitation for body
            if out.get("temp_delta",0.0) < 0: out["temp_delta"] *= 0.5
            if out.get("agitation_delta",0.0) < 0: out["agitation_delta"] *= 0.5
        return out
