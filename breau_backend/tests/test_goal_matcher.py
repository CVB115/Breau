# tests/test_goal_matcher.py
# Purpose:
# Sanity tests for canonicalization + merge logic in protocol goal matcher.
from breau_backend.app.services.protocol_generator import goal_matcher as gm

def test_canon_map_and_stable_sort():
    assert gm._canon("more body") == "increase body"
    assert gm._canon("LESS CLARITY") == "reduce clarity"
    goals = [("increase body", 0.5), ("increase florality", 1.0)]
    out = gm._stable_sort(goals)
    # Purpose: CANON_ORDER put florality first
    assert out[0][0] == "increase florality"

def test_merge_goals_accumulates_weights_and_dedupes():
    explicit = [("more body", 0.5), ("increase florality", 1.0)]
    parsed   = [("increase body", 0.5), ("increase florality", 0.25)]
    semantic = [("increase body", 0.25)]
    merged = gm.merge_goals(explicit, parsed, semantic)
    # Purpose: "more body" → "increase body" and weights sum to 1.25
    weights = dict(merged)
    assert abs(weights["increase body"] - 1.25) < 1e-6
    assert "increase florality" in weights
