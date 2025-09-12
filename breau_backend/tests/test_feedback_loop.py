# breau_backend/tests/test_feedback_loop.py
import pytest
from starlette.testclient import TestClient
from breau_backend.app.main import app

client = TestClient(app)

def _post(path: str, data: dict):
    r = client.post(path, json=data)
    assert r.status_code == 200, f"{path} failed: {r.status_code} {r.text}"
    return r.json()

def _get(path: str):
    r = client.get(path)
    assert r.status_code == 200, f"{path} failed: {r.status_code} {r.text}"
    return r.json()

def test_feedback_influences_suggestion(tmp_path, monkeypatch):
    # isolate state
    monkeypatch.setenv("BREAU_PROFILE_PATH", str(tmp_path / "profiles.json"))
    monkeypatch.setenv("BREAU_PRIORS_PATH", str(tmp_path / "priors_dynamic.json"))

    # 1) minimal profile
    _post("/profile", {
        "user_id": "local",
        "grinder": {"burr_type": "conical", "model": "C2"},
        "filter":  {"permeability": "fast", "material": "paper_bleached"},
        "water":   {"profile_preset": "sca_target"},
        "brewer":  {"name": "Hario V60", "geometry_type": "conical", "cone_angle_deg": 30,
                    "outlet_profile": "single_large", "size_code": "02",
                    "inner_diameter_mm": 40, "hole_count": 1, "thermal_mass": "medium"}
    })

    # 2) baseline
    baseline = _post("/brew/suggest", {
        "user_id": "local",
        "text": "",
        "goals": [],
        "ratio": "1:15",
        "bean": {"process": "washed", "roast_level": "light"}
    })
    base_temp = baseline["temperature_c"]
    base_ratio = float(baseline["ratio"].split(":")[1])

    # 3) feedback
    for _ in range(3):
        _post("/brew/feedback", {
            "user_id": "local",
            "bean_process": "washed",
            "roast_level": "light",
            "filter_permeability": "fast",
            "variant_used": "primary",
            "rating": 5,
            "notes_positive": ["jasmine"],
            "traits_positive": ["florality", "clarity"]
        })

    # 4) priors reflect feedback
    pri = _get("/brew/priors/washed/light/fast")
    assert "jasmine" in pri["dynamic_notes_top"]
    assert pri["dynamic_traits"].get("florality", 0) > 0
    assert pri["rating"]["count"] >= 1

    # 5) new suggestion should lean clarity
    after = _post("/brew/suggest", {
        "user_id": "local",
        "text": "",
        "goals": [],
        "ratio": "1:15",
        "bean": {"process": "washed", "roast_level": "light"}
    })

    # notes: jasmine should be present
    labels = [n["label"] for n in after.get("predicted_notes", [])]
    assert "jasmine" in labels

    # clarity-leaning signals (cooler or equal temp, ratio same or higher)
    assert after["temperature_c"] <= base_temp
    after_ratio = float(after["ratio"].split(":")[1])
    assert after_ratio >= base_ratio

    # 6) alternative exists: accept either pocket; if none, skip this part
    def _get_alt_pours(resp: dict):
        alt = resp.get("alternative")
        if isinstance(alt, dict) and isinstance(alt.get("pours"), list):
            return alt["pours"]
        alts = resp.get("alternatives")
        if isinstance(alts, list) and len(alts) > 0:
            first = alts[0]
            if isinstance(first, dict) and isinstance(first.get("pours"), list):
                return first["pours"]
        return []

    alt_pours = _get_alt_pours(after)
    if not alt_pours:
        pytest.skip("No alternative variant returned by /brew/suggest in this build.")
    assert len(alt_pours) >= 1
