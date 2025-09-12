def test_personalizer_index_sync(tmp_path, monkeypatch):
    # Arrange: a fake per-user personalizer snapshot
    base = tmp_path / "data" / "profiles"
    base.mkdir(parents=True, exist_ok=True)
    snap = {
        "trait_response": {"floral": 0.6, "body": -0.3},
        "note_sensitivity": {"jasmine": 0.9},
        "updated_at": "2025-09-11T00:00:00Z",
        "history_count": 5
    }

    import json
    (base / "u1.json").write_text(json.dumps(snap), encoding="utf-8")

    # Point the app at the temp DATA_DIR
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)

    # Act: sync index
    from breau_backend.app.services.learning.personalizer_index import sync_personalizer_index
    entry = sync_personalizer_index("u1")

    # Assert: returned entry is compact and correct
    assert entry["trait_response"]["floral"] == 0.6
    assert entry["history_count"] == 5

    # And the index file exists and contains the entry
    idx = tmp_path / "data" / "profiles" / "profiles.json"
    assert idx.exists()
    blob = json.loads(idx.read_text(encoding="utf-8"))
    assert blob["u1"]["trait_response"]["floral"] == 0.6
