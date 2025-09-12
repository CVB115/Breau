# breau_backend/app/services/learning/offline_eval.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from statistics import mean, pstdev
from breau_backend.app.utils.storage import read_json

# Purpose:
# Offline assessment of bandit arms using logged sessions.
# We compute IPS and DR estimates with quick CIs across recent data.
# Requires sessions to have derived.bandit_decision = {arm, pi}.

DATA_DIR = Path("./data")

def _iter_sessions(window_days: Optional[int] = None):
    # Purpose:
    # Yield raw session JSONs within optional time window.
    import time, datetime as dt
    sess_dir = DATA_DIR / "history" / "sessions"
    if not sess_dir.exists():
        return
    cutoff = None
    if window_days and window_days > 0:
        cutoff = time.time() - window_days * 86400
    for p in sess_dir.glob("*.json"):
        js = read_json(p, None)
        if not js:
            continue
        fb = js.get("feedback", {})
        ts = fb.get("created_at")
        if cutoff:
            try:
                t = dt.datetime.fromisoformat(ts).timestamp()
                if t < cutoff:
                    continue
            except Exception:
                pass
        yield js

def _reward(js) -> float:
    # Purpose:
    # Scalar reward from a session (overall rating; default 3.0).
    try:
        return float(js["feedback"]["ratings"]["overall"])
    except Exception:
        return 3.0

def _arm_and_pi(js) -> Tuple[Optional[str], float]:
    # Purpose:
    # Extract (arm, propensity pi) from the saved bandit imprint.
    d = (js.get("derived") or {}).get("bandit_decision")
    if not d:
        return None, 1.0
    return d.get("arm"), float(d.get("pi", 1.0))

def _mu_per_arm(samples: List[Tuple[str, float]]) -> Dict[str, float]:
    # Purpose:
    # Mean reward per arm from observed on-policy samples.
    by = {}
    for arm, r in samples:
        by.setdefault(arm, []).append(r)
    return {k: (mean(v) if v else 0.0) for k, v in by.items()}

def _ci(mean_val: float, terms: List[float]) -> Dict[str, float]:
    # Purpose:
    # 95% CI using normal approximation with population stdev fallback.
    n = max(1, len(terms))
    if n <= 1:
        return {"lo": mean_val, "hi": mean_val}
    sd = pstdev(terms)  # population stdev is OK here
    se = sd / (n ** 0.5)
    z = 1.96
    return {"lo": mean_val - z * se, "hi": mean_val + z * se}

def _eval_one(target: str, S_full: List[Tuple[str, float, float]]) -> Dict:
    """
    Purpose:
    Evaluate a single target arm using:
    - IPS: E[ 1{A=target} * r / pi ]
    - DR:  mu_target + 1{A=target} * (r - mu_A) / pi

    S_full: list of (arm, pi, r)
    """
    if not S_full:
        return {"ok": False, "msg": "no sessions"}

    # IPS
    ips_terms = []
    for arm, pi, r in S_full:
        if arm == target:
            ips_terms.append(r / max(1e-9, pi))
        else:
            ips_terms.append(0.0)
    ips = mean(ips_terms)
    ips_ci = _ci(ips, ips_terms)

    # DR
    mu = _mu_per_arm([(arm, r) for arm, pi, r in S_full])
    mu_target = mu.get(target, mean([r for _, _, r in S_full]))
    dr_terms = []
    for arm, pi, r in S_full:
        base = mu_target
        corr = ((r - mu.get(arm, mu_target)) / max(1e-9, pi)) if arm == target else 0.0
        dr_terms.append(base + corr)
    dr = mean(dr_terms)
    dr_ci = _ci(dr, dr_terms)

    return {
        "ok": True,
        "target": target,
        "samples": len(S_full),
        "ips": ips, "ips_ci": ips_ci,
        "dr": dr,   "dr_ci": dr_ci,
    }

def evaluate(window_days: Optional[int] = 60) -> Dict:
    # Purpose:
    # Compute IPS/DR estimates for each arm found in the window.
    S: List[Tuple[str, float, float]] = []
    arms = set()
    for js in _iter_sessions(window_days=window_days):
        arm, pi = _arm_and_pi(js)
        if not arm:
            continue
        r = _reward(js)
        arms.add(arm)
        S.append((arm, float(pi), float(r)))

    results = {}
    for a in sorted(arms):
        results[a] = _eval_one(a, S)
    return {"ok": True, "arms": results, "N": len(S)}
