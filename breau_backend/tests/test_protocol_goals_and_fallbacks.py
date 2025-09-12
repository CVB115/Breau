# tests/test_protocol_goals_and_fallbacks.py
# Purpose:
# Protocol generator pieces: goals canonicalization/merge and default goal tags.

from breau_backend.app.services.protocol_generator import goal_matcher as gm
from breau_backend.app.services.protocol_generator import fallback_goals as fbg

def test_goal_canonicalization_and_merge():
    explicit = [("more body", 0.5), ("increase florality", 1.0)]
    parsed   = [("increase body", 0.5), ("increase florality", 0.25)]
    semantic = [("increase body", 0.25)]
    merged = gm.merge_goals(explicit, parsed, semantic)
    d = dict(merged)
    # Purpose: synonyms mapped and weights summed
    assert abs(d["increase body"] - 1.25) < 1e-6
    # Purpose: canonical order keeps florality ahead
    assert [k for k,_ in merged][0] == "increase florality"
    # Purpose: views helper preserves both forms
    phrases, weighted = gm.goals_as_phrases_and_weighted(merged)
    assert phrases[0] == "increase florality"
    assert weighted == merged

def test_fallback_goal_tags_for_cluster():
    # Washed + light → clarity leaning defaults
    out = fbg.fallback_goal_tags_for_cluster(process="washed", roast="light")
    assert any("clarity" in t or "temp_affinity:lower" in t for t in out)
    # Natural + medium-dark → body leaning defaults
    out2 = fbg.fallback_goal_tags_for_cluster(process="natural", roast="medium-dark")
    assert any("syrupy" in t or "density:rich" in t for t in out2)
