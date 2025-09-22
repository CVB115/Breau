from fastapi.testclient import TestClient
from breau_backend.app.main import app
import time

def _parse_sid(js):
    if isinstance(js, str):
        return js
    if isinstance(js, dict):
        return js.get("session_id") or js.get("id") or js.get("sid")
    return None

def test_find_session_read_url():
    c = TestClient(app)

    # 1) Inspect OpenAPI and collect GET paths that look like "session" reads
    spec = c.get("/openapi.json")
    assert spec.status_code == 200, "/openapi.json not reachable"
    paths = spec.json()["paths"]
    cand = [p for p, ops in paths.items() if isinstance(ops, dict) and "get" in ops and "session" in p]

    print("\nGET candidates:", cand)

    # 2) Start a tiny brew (so we have a valid session_id)
    r = c.post("/api/brew/start", json={"user_id": "introspect", "gear": {"brewer": {"name": "Any"}}})
    assert r.status_code == 200, r.text
    sid = _parse_sid(r.json())
    assert sid, f"couldn't parse session_id from {r.json()}"

    t0 = int(time.time() * 1000)
    c.post("/api/brew/step", json={"session_id": sid, "step": {"type": "pour", "target_g": 50, "at_ms": t0}})
    c.post("/api/brew/finish", json={"session_id": sid, "rating": 4})

    # 3) Try each candidate; fill placeholders; print the one that works + its top-level keys
    def fill(p):
        return (p.replace("{session_id}", sid)
                 .replace("{sid}", sid)
                 .replace("{id}", sid)
                 .replace("{user_id}", "introspect")
                 .replace("{userId}", "introspect"))

    worked = []
    for p in cand:
        url = fill(p)
        resp = c.get(url)
        print("TRY", url, "->", resp.status_code)
        if resp.status_code == 200:
            payload = resp.json()
            doc = payload["session"] if isinstance(payload, dict) and "session" in payload else payload
            print("SESSION READ URL:", url)
            print("TOP-LEVEL KEYS:", sorted(list(doc.keys()))[:25])
            worked.append(url)
            break

    assert worked, "No working GET session endpoint found"
