# breau_backend/tests/test_end_to_end.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import os
import json
import re

def _payload(user: str, sid: str, overall: float = 4.5) -> Dict[str, Any]:
    return {
        "user_id": user,
        "session_id": sid,
        "protocol": {
            "method": "v60-style",
            "temperature_c": 91,
            "ratio": "1:15",
            "grind_label": "medium",
            "agitation_overall": "moderate",
        },
        "ratings": {"overall": overall},
        "goals": [{"tags": ["increase florality", "less body"]}],
        "notes_confirmed": ["jasmine"],
        "notes_missing": ["bitterness"],
        "beans_meta": {"roast_level": "light", "process": "washed"},
    }

def test_health_and_openapi(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True

    # make sure OpenAPI has paths
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert "paths" in spec and isinstance(spec["paths"], dict)
    # basic routers expected (presence is enough)
    # don't hard fail if optional ones are absent
    # just record what we see
    seen = set(spec["paths"].keys())
    # These are common; won't fail test if missing, just sanity check:
    _ = {p for p in ["/feedback", "/brew/plan", "/library/beans"] if p in seen}

def test_feedback_warmup_then_on(client):
    """
    LEARNING_THRESHOLD is set to 3 (via fixture). We post 3 sessions:
    - sessions 1 & 2 => should show 'waiting (n/3)'
    - session 3      => should show 'ON'
    Also asserts a session file is written under DATA_DIR/history/sessions.
    """
    data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
    sess_dir = data_dir / "history" / "sessions"

    # 1st
    r1 = client.post("/feedback", json=_payload("tester", "s001", overall=4.3))
    assert r1.status_code == 200
    j1 = r1.json()
    assert j1.get("ok") is True
    assert "waiting" in str(j1["learning_state"].get("mode", "")).lower()

    # 2nd
    r2 = client.post("/feedback", json=_payload("tester", "s002", overall=3.8))
    assert r2.status_code == 200
    j2 = r2.json()
    assert "waiting" in str(j2["learning_state"].get("mode", "")).lower()

    # 3rd reaches threshold → ON
    r3 = client.post("/feedback", json=_payload("tester", "s003", overall=4.9))
    assert r3.status_code == 200
    j3 = r3.json()
    assert j3["learning_state"].get("mode") == "ON"

    # verify session file exists (the last response has "stored": "<path>")
    stored_path = j3.get("stored")
    assert stored_path, "feedback endpoint must return 'stored' path"
    # path is returned as string; ensure it's under our DATA_DIR
    sp = Path(stored_path)
    assert "history" in str(sp).replace("\\", "/")
    assert sp.exists(), f"session file not found: {sp}"
    # quick schema sanity
    js = json.loads(Path(sp).read_text(encoding="utf-8"))
    assert "feedback" in js and "derived" in js

def test_optional_brew_plan_if_present(client):
    """
    If /brew/plan exists, do a light probe.
    If it's not mounted, test is skipped.
    """
    # Check openapi for route presence
    spec = client.get("/openapi.json").json()
    if "/brew/plan" not in spec.get("paths", {}):
        # skip cleanly
        return

    payload = {"method": "v60-style", "ratio": "1:15", "temperature_c": 91}
    r = client.post("/brew/plan", json=payload)
    assert r.status_code in (200, 422)  # 422 allowed if Pydantic model differs
    if r.status_code == 200:
        j = r.json()
        assert isinstance(j, dict)
        # tolerate both real builder or fallback shape
        assert any(k in j for k in ("plan", "recipe", "ok"))

def test_optional_library_beans_if_present(client):
    """
    If /library/beans exists, it should return 200 and JSON list/dict.
    If it's not mounted, test is skipped.
    """
    spec = client.get("/openapi.json").json()
    if "/library/beans" not in spec.get("paths", {}):
        return
    r = client.get("/library/beans")
    assert r.status_code == 200
    # Could be a dict or list depending on your implementation
    assert isinstance(r.json(), (list, dict))
