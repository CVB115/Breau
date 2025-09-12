from fastapi.testclient import TestClient

def test_priors_path_equals_cluster(client: TestClient):
    # Record one piece of feedback so both routes return non-empty dynamics
    _ = client.post("/brew/feedback", json={
        "user_id":"eq_tester","bean_process":"washed","roast_level":"light",
        "filter_permeability":"fast","variant_used":"primary","rating":5,
        "notes_positive":["jasmine"],"traits_positive":["florality"]
    })

    a = client.get("/brew/priors/washed/light/fast").json()
    b = client.get("/brew/priors/washed:light:fast").json()

    # Compare on a small stable subset
    assert a["cluster"] == b["cluster"]
    assert set(a["dynamic_notes_top"]) == set(b["dynamic_notes_top"])
    assert a["rating"]["count"] >= 1 and b["rating"]["count"] >= 1
