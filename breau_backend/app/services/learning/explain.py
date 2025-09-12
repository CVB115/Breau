from __future__ import annotations
from pathlib import Path
from typing import Dict
from breau_backend.app.utils.storage import read_json, write_json, ensure_dir

# Purpose:
# Hold the "why" string (≤ 140 chars) that explains the current overlay in human language,
# plus a light trace of which sources contributed (prior/history/edge).

DATA_DIR = Path("./data")
EXPLAIN_DIR = DATA_DIR / "state" / "explain"
ensure_dir(EXPLAIN_DIR)

# Purpose:
# Compose a compact explanation string. Uses an optional "hint" from context
# (e.g., "clarity" / "body") to pick a friendlier sentence, and appends source tags.
def compose(trace: Dict[str, float], context: Dict) -> str:
    """
    Build a <=140 char why-string with source tags.
    trace keys expected: prior, history, edge
    """
    bits = []
    # Inference: write a quick, goal-aware message users can read at a glance.
    hint = context.get("hint")  # e.g., "clarity", "body"
    if hint == "clarity":
        bits.append("Cooler water & gentler pours for clarity")
    elif hint == "body":
        bits.append("Slightly finer & warmer for fuller body")
    else:
        bits.append("Small tweaks applied for goal")

    tags = []
    if abs(trace.get("prior", 0.0)) > 1e-6:   tags.append("[prior]")
    if abs(trace.get("history", 0.0)) > 1e-6: tags.append("[history]")
    if abs(trace.get("edge", 0.0)) > 1e-6:    tags.append("[edge]")

    s = f"{'; '.join(bits)} {' '.join(tags)}".strip()
    return (s[:137] + "...") if len(s) > 140 else s

# Purpose:
# Persist the last explanation for a user (arm is the bandit choice used).
def save_last(user_id: str, why: str, trace: Dict[str, float], arm: str) -> None:
    write_json(EXPLAIN_DIR / f"{user_id}.json", {"why": why, "trace": trace, "arm": arm})

# Purpose:
# Load the last explanation snapshot for a user; return empty defaults if missing.
def load_last(user_id: str) -> Dict:
    return read_json(EXPLAIN_DIR / f"{user_id}.json", {"why": "", "trace": {}, "arm": ""})
