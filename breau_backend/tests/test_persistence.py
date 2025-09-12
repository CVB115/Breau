import os
from pathlib import Path
from fastapi.testclient import TestClient
from breau_backend.app.main import app

def test_feedback_persists_across_clients(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "persist"))
    c1 = TestClient(app)

    # write some feedback
    for sid in ("s1","s2","s3"):
        r = c1.post("/brew/feedback", json={
            "user_id":"persist","session_id":sid,"variant_used":"primary",
            "bean_process":"washed","roast_level":"light","filter_permeability":"fast",
            "rating": 4.5, "notes_positive":["jasmine"], "traits_positive":["clarity"]
        })
        assert r.status_code == 200

    # "new client" simulates restart
    c2 = TestClient(app)
    pri = c2.get("/brew/priors/washed/light/fast").json()
    assert pri["rating"]["count"] >= 3
    assert "jasmine" in pri["dynamic_notes_top"]
    assert pri["dynamic_traits"].get("clarity", 0) > 0
