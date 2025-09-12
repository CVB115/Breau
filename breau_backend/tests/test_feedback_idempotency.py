from fastapi.testclient import TestClient

def test_duplicate_feedback_is_tolerated(client: TestClient):
    payload = {
        "user_id":"dupe","session_id":"repeat-001","variant_used":"primary",
        "bean_process":"washed","roast_level":"light","filter_permeability":"fast",
        "rating": 5, "notes_positive":["jasmine"], "traits_positive":["florality"]
    }
    r1 = client.post("/brew/feedback", json=payload)
    r2 = client.post("/brew/feedback", json=payload)  # duplicate
    assert r1.status_code == 200 and r2.status_code in (200, 409, 202)

    pri = client.get("/brew/priors/washed/light/fast").json()
    assert pri["rating"]["count"] >= 1
