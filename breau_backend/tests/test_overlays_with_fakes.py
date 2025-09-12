# tests/test_overlays_with_fakes.py
from types import SimpleNamespace

# Purpose:
# Integration-light test: monkeypatch overlays' singletons with fakes
# so we can deterministically verify composition + caps.

class FakeFlags:
    def __init__(self, on):
        self.on = on
    def is_on(self, user_id, key):  # user ignored for simplicity
        return bool(self.on.get(key, False))

class FakePersonalizer:
    def overlays_for_user(self, user_id, goal_tags):
        # clarity-leaning: cooler/gentler
        return {"temp_delta": -0.2, "agitation_delta": -0.1}

class FakePlanner:
    def suggest(self, user_id, goal_tags, context, protocol):
        # planner proposes a small body shift; will be blended by bandit
        return {"temp_delta": +0.15}

class FakeBandit:
    def choose(self, user_id, mode, baseline_overlay, shadow_delta, planner_delta, goal_tags):
        # deterministically choose baseline + personalizer (no shadow/planner)
        # emulate the return shape
        return {"overlay": dict(baseline_overlay), "arm": "baseline", "decision_id": "x", "pi": 1.0}

def test_overlays_composition_with_fakes(reload_overlays, sample_flags, user_id, goal_tags):
    overlays = reload_overlays()

    # monkeypatch singletons
    overlays._flags = FakeFlags({
        "use_learned_edges": False,
        "use_user_personalisation": True,
        "use_practice": False,
        "use_curriculum": False,
        "use_model_planner": False,
        "use_cohort_seed": False,
    })
    overlays._personalizer = FakePersonalizer()
    overlays._planner = FakePlanner()
    overlays._bandit = FakeBandit()

    context = {"process": "pour_over", "roast": "light", "ratio_den": 15}
    ov = overlays.compute_overlays(user_id, goal_tags, context)
    # personalizer should have contributed; final cap protects magnitude
    assert isinstance(ov, dict)
    assert ov.get("temp_delta", 0) <= 0.0
    assert abs(ov.get("temp_delta", 0)) <= 0.3 + 1e-9
