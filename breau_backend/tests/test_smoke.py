import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.mark.smoke
def test_health_and_min_routes():
    from breau_backend.app.main import app
    client = TestClient(app)

    r = client.get("/")
    assert r.status_code == 200 and r.json().get("ok") is True

    # profile
    r = client.post("/profile", json={"user_id":"tester"})
    assert r.status_code == 200

    # brew plan (will fallback if real builder not wired)
    r = client.post("/brew/plan", json={"method":"v60-style","ratio":"1:15","temperature_c":91})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True and "plan" in body

    # feedback x3 → learning flips to ON (LEARNING_THRESHOLD may be set in your conftest)
    def fb(sid, overall):
        return {
            "user_id":"tester","session_id":sid,
            "protocol":{"method":"v60-style","temperature_c":91,"ratio":"1:15","grind_label":"medium","agitation_overall":"moderate"},
            "ratings":{"overall":overall},
            "goals":[{"tags":["increase florality","less body"]}],
        }

    j1 = client.post("/feedback", json=fb("s001", 4.2)).json()
    j2 = client.post("/feedback", json=fb("s002", 3.8)).json()
    j3 = client.post("/feedback", json=fb("s003", 4.9)).json()

    assert "waiting" in j1["learning_state"]["mode"].lower()
    assert "waiting" in j2["learning_state"]["mode"].lower()
    assert j3["learning_state"]["mode"] == "ON"

    # sessions written under DATA_DIR
    data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
    assert (data_dir / "history" / "sessions").exists()
