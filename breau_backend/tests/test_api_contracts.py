import os
from pathlib import Path
from fastapi.testclient import TestClient

def test_minimal_suggest_contract(client: TestClient):
    r = client.post("/brew/suggest", json={
        "user_id": "contract_user",
        "text": "✨ increase florality & clarity 🌸",
        "goals": [],
        "ratio": "1:15",
        "bean": {"process": "washed", "roast_level": "light"},
        # intentionally omit filter to exercise defaults down-pipeline
    })
    assert r.status_code == 200
    body = r.json()
    # Bare contract checks; do NOT overfit values
    assert set(["temperature_c", "ratio", "pours", "notes"]).issubset(body.keys())
    # Pours should be valid objects with required keys
    assert isinstance(body["pours"], list)
    for p in body["pours"]:
        for k in ("pour_style", "water_g", "kettle_temp_c", "agitation"):
            assert k in p

def test_feedback_validation_errors_return_4xx(client: TestClient):
    r = client.post("/brew/feedback", json={
        "user_id": "",  # invalid
        "variant_used": "primary"
    })
    assert r.status_code in (400, 422)

def test_priors_empty_state_is_safe(tmp_path, monkeypatch, client: TestClient):
    # Force empty data dir
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    # Fresh app call: no feedback recorded yet
    r = client.get("/brew/priors/washed/light/fast")
    assert r.status_code == 200
    j = r.json()
    # Expected keys exist; lists/dicts may be empty but must be present
    assert "dynamic_notes_top" in j
    assert "dynamic_traits" in j
    assert "static_notes" in j
    assert "rating" in j and "count" in j["rating"]
