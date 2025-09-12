from starlette.testclient import TestClient
from breau_backend.app.main import app

client = TestClient(app)

def test_resolve_derives_goals_from_text(monkeypatch):
    # Seed: ensure bean alias exists (skip if you already seed beans in a fixture)
    # We'll create via /beans to exercise the whole flow.
    alias = "guji-2025-lot-12"
    # Try to create; ignore if it already exists.
    client.post("/beans", json={
        "alias": alias,
        "roaster": "Test Roastery",
        "name": "Ethiopia Guji",
        "origin": "Ethiopia",
        "process": "washed",
        "roast_level": "light",
        "tags": ["ethiopia","guji","washed","light"]
    })

    body = {
        "user_id": "testlab",
        "ratio": "1:15",
        "text": "brighter, cleaner, less bitter",
        "bean_id": alias
    }
    r = client.post("/brew/resolve", json=body)
    assert r.status_code == 200, r.text
    payload = r.json()
    goals = payload["resolved"]["goals"]
    assert any(g["trait"]=="clarity" and g["direction"]=="increase" for g in goals)
    assert any(g["trait"]=="acidity" and g["direction"]=="increase" for g in goals)
    assert any(g["trait"]=="bitterness" and g["direction"]=="decrease" for g in goals)
    assert payload["cluster_preview"] == "washed:light:fast"
