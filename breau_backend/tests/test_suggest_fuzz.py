import random
from fastapi.testclient import TestClient

FUZZ_TEXTS = [
    "increase clarity ✨✨ reduce bitterness pls",
    "更多花香，少一点 body 🙏",
    "floral++ acidity+ sweetness~ umami??",
    "🚀 just brew it — smooth & bright",
]

def test_suggest_handles_weird_text(client: TestClient):
    txt = random.choice(FUZZ_TEXTS)
    r = client.post("/brew/suggest", json={
        "user_id":"fuzz","text":txt,"ratio":"1:16",
        "bean":{"process":"washed","roast_level":"light"},
        "goals":[]
    })
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j.get("pours"), list) and len(j["pours"]) >= 1
    assert isinstance(j.get("notes"), list)
