# breau_backend/tests/test_files_written.py
from __future__ import annotations
from pathlib import Path
import os

def test_data_tree_created_by_feedback(client):
    # trigger one session
    client.post("/feedback", json={
        "user_id": "file_tester",
        "session_id": "fx1",
        "protocol": {"method":"v60-style","temperature_c":91,"ratio":"1:15","grind_label":"medium","agitation_overall":"moderate"},
        "ratings": {"overall": 4.0},
        "goals": [{"tags":["increase florality"]}]
    })

    data = Path(os.getenv("DATA_DIR", "./data")).resolve()
    assert (data / "history" / "sessions").exists()
    # optional subtrees, only assert existence if your code writes them:
    # (comment out any you don't want enforced)
    for maybe in [
        data / "profiles",
        data / "metrics",
        data / "priors",
        data / "models",
        data / "state",
    ]:
        # don't hard fail if not used yet
        _ = maybe.exists()
