def test_personalizer_index_backfill_and_api(tmp_path, monkeypatch):
    # Arrange snapshots
    d = tmp_path / "data" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    import json
    (d / "u1.json").write_text(json.dumps({
        "trait_response": {"floral": 0.4},
        "note_sensitivity": {"jasmine": 0.7},
        "updated_at": "2025-09-11T00:00:00Z",
        "history_count": 2
    }), encoding="utf-8")
    (d / "u2.json").write_text(json.dumps({
        "trait_response": {"body": -0.2},
        "note_sensitivity": {"cocoa": 0.5},
        "updated_at": "2025-09-10T00:00:00Z",
        "history_count": 5
    }), encoding="utf-8")

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)

    # Backfill
    from breau_backend.app.services.learning.personalizer_index import backfill_all
    n = backfill_all()
    assert n == 2

    # API read (optional route)
    from fastapi.testclient import TestClient
    from breau_backend.app.main import app
    client = TestClient(app)

    r = client.get("/profile/preferences_index?limit=10&offset=0")
    assert r.status_code == 200
    data = r.json()
    # u1 and u2 present with compact fields
    assert "u1" in data and "u2" in data
    assert data["u1"]["trait_response"]["floral"] == 0.4
    assert data["u2"]["history_count"] == 5
