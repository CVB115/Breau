import concurrent.futures as cf
from fastapi.testclient import TestClient

def test_feedback_parallel_is_consistent(client: TestClient):
    payloads = [{
        "user_id":"conc","session_id":f"conc-{i}","variant_used":"primary",
        "bean_process":"washed","roast_level":"light","filter_permeability":"fast",
        "rating":4.2,"notes_positive":["citrus"],"traits_positive":["clarity"]
    } for i in range(8)]

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        resps = list(ex.map(lambda p: client.post("/brew/feedback", json=p), payloads))

    assert all(r.status_code == 200 for r in resps)

    pri = client.get("/brew/priors/washed/light/fast").json()
    assert pri["rating"]["count"] >= 8
