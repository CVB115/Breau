def test_profile_preferences_api(tmp_path, monkeypatch):
    # Arrange a fake personalizer snapshot
    (tmp_path / "data" / "profiles").mkdir(parents=True, exist_ok=True)
    import json
    (tmp_path / "data" / "profiles" / "u1.json").write_text(json.dumps({
        "trait_response": {"floral": 0.8, "body": -0.4},
        "note_sensitivity": {"jasmine": 0.9},
        "updated_at": "2025-09-11T00:00:00Z",
    }), encoding="utf-8")

    # Point the app at the temp data dir and build a TestClient
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)

    from fastapi.testclient import TestClient
    from breau_backend.app.main import app
    client = TestClient(app)

    # Act
    r = client.get("/profile/preferences/u1")
    assert r.status_code == 200
    data = r.json()

    # Assert
    assert data["enabled"] is True
    assert data["trait_response"]["floral"] == 0.8
