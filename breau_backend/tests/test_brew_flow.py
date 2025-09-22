# breau_backend/tests/test_brew_flow.py
# End-to-end: start -> steps -> finish -> (optional feedback) -> read session (auto-discovers paths)

def _parse_sid(resp_json):
    """Server may return {'session_id': '...'} or a raw string."""
    if isinstance(resp_json, str):
        return resp_json
    if isinstance(resp_json, dict):
        for k in ("session_id", "id", "sid"):
            v = resp_json.get(k)
            if isinstance(v, str) and v:
                return v
    raise AssertionError(f"Could not find session_id in response: {resp_json!r}")

def _openapi(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200, "/openapi.json not reachable"
    data = r.json()
    assert isinstance(data, dict) and "paths" in data
    return data["paths"]

def _find_session_read_url(client, sid, user_id):
    """
    Try common read paths first, then fall back to OpenAPI discovery.
    Returns a ready-to-call URL string.
    """
    candidates = [
        f"/api/sessions/{sid}",
        f"/api/session/{sid}",
        f"/api/brew/session/{sid}",
        f"/api/history/session/{sid}",
        f"/api/sessions/{user_id}/{sid}",   # two-param style
        f"/api/session/{user_id}/{sid}",
    ]
    # Probe the quick candidates
    for url in candidates:
        r = client.get(url)
        if r.status_code == 200:
            return url
    # Discover via OpenAPI
    paths = _openapi(client)
    discovered = []
    for p, ops in paths.items():
        if not isinstance(ops, dict) or "get" not in ops:
            continue
        if "session" in p:
            discovered.append(p)

    def _fill(p):
        return (p.replace("{session_id}", sid)
                 .replace("{sid}", sid)
                 .replace("{id}", sid)
                 .replace("{user_id}", user_id)
                 .replace("{userId}", user_id))

    for p in discovered:
        url = _fill(p)
        r = client.get(url)
        if r.status_code == 200:
            return url

    raise AssertionError(
        f"Could not find a working session read path. Tried: {candidates} and discovered: {discovered}"
    )

def _find_feedback_paths(client):
    """Return (rate_path_template, suggest_path_template) via OpenAPI, or (None, None)."""
    paths = _openapi(client)
    rate = None
    suggest = None
    for p, ops in paths.items():
        if not isinstance(ops, dict) or "post" not in ops:
            continue
        if "/feedback" in p:
            if p.rstrip("/").endswith("suggest"):
                suggest = p
            else:
                rate = p
    return (rate, suggest)

def _post_feedback_if_available(client, sid):
    rate_tmpl, suggest_tmpl = _find_feedback_paths(client)

    def fill(path):
        if not path:
            return None
        return (path.replace("{session_id}", sid)
                    .replace("{sid}", sid)
                    .replace("{id}", sid)
                    .replace("{sessionId}", sid))

    rate_url = fill(rate_tmpl)
    suggest_url = fill(suggest_tmpl)

    if rate_url:
        payload = {
            "rating": 4,  # int (this backend validates ints)
            "perceived_notes": [{"note": "sweet", "score": 2.5}],
            "intensities": {
                "acidity": 2.5,
                "sweetness": 2.5,
                "bitterness": 0.0,
                "body": 3.4,
                "clarity": 2.5,
            },
            "comments": "well balanced",
        }
        r = client.post(rate_url, json=payload)
        # If payload/route mismatch, don’t fail the flow — continue
        if r.status_code not in (200, 201, 204):
            print(f"[warn] feedback POST {rate_url} -> {r.status_code}: {r.text}")

    if suggest_url:
        r = client.post(suggest_url, json={"rating": 5, "comment": "brew again"})
        if r.status_code not in (200, 201, 204):
            print(f"[warn] feedback suggest POST {suggest_url} -> {r.status_code}: {r.text}")

def _pluck_session(payload):
    """
    Normalize to the inner session dict. Some backends return {"session": {...}},
    others return the document directly.
    """
    if isinstance(payload, dict):
        if "session" in payload and isinstance(payload["session"], dict):
            return payload["session"]
        return payload
    raise AssertionError(f"Unexpected GET /session response: {payload!r}")

def test_full_brew_happy_path(client):
    """
    Start -> step(s) -> finish -> (optional feedback) -> read session.
    Accepts either raw storage shape (pours/events) or enriched (timeline).
    """

    # 1) Start — gear.brewer must be an object with a name
    start_payload = {
        "user_id": "pytest-user",
        "bean": {"name": "Test Bean", "roaster": "Py Roasters"},
        "gear": {
            "brewer": {"name": "V60 02"},
            "grinder": {"model": "C40"},
        },
        "recipe": {
            "dose_g": 15,
            "total_water_g": 240,
            "ratio_pretty": "1:16",
            "bloom": {"water_g": 40},
        },
    }
    r = client.post("/api/brew/start", json=start_payload)
    assert r.status_code == 200, r.text
    sid = _parse_sid(r.json())
    assert isinstance(sid, str) and sid

    # 2) Steps — USE water_g for bloom, target_g for pours
    import time as _time
    t0 = int(_time.time() * 1000)
    steps = [
        {"type": "bloom", "water_g": 40,  "at_ms": t0,            "style": "center", "note": "wet grounds"},
        {"type": "pour",  "target_g": 150, "at_ms": t0 + 25_000,  "style": "spiral"},
        {"event": "swirl",                 "at_ms": t0 + 30_000,  "meta": {"note": "gentle"}},
        {"type": "pour",  "target_g": 240, "at_ms": t0 + 45_000,  "style": "center"},
    ]
    for s in steps:
        rr = client.post("/api/brew/step", json={"session_id": sid, "step": s})
        assert rr.status_code == 200, rr.text

    # 3) Finish — rating must be INT for this backend
    r = client.post("/api/brew/finish", json={"session_id": sid, "rating": 4, "notes": "tasty!"})
    assert r.status_code == 200, r.text

    # 4) Feedback (optional; try if a route exists). Do not fail if missing/ignored.
    _post_feedback_if_available(client, sid)

    # 5) Read session (auto-discover the correct path)
    read_url = _find_session_read_url(client, sid=sid, user_id="pytest-user")
    r = client.get(read_url)
    assert r.status_code == 200, f"GET {read_url} failed: {r.text}"
    sess = _pluck_session(r.json())

    # --- Identity / timestamps (accept ISO or epoch) ---
    assert (sess.get("session_id") == sid) or (sess.get("id") == sid)
    has_started = ("started_at" in sess) or ("created_utc" in sess)
    assert has_started, f"Missing started_at/created_utc in {sess.keys()}"
    assert ("finished_at" in sess) or ("finished_utc" in sess)

    # --- Recipe totals present or derivable from pours ---
    recipe = sess.get("recipe") or {}
    has_total = (recipe.get("total_water_g") in (240, 240.0))
    pours = sess.get("pours") or []
    if not has_total and isinstance(pours, list) and pours:
        try:
            max_to = max([p.get("to_g") or 0 for p in pours if isinstance(p, dict)])
            assert max_to in (240, 240.0)
        except Exception:
            assert False, f"Neither recipe.total_water_g nor pours max(to_g) equals 240; recipe={recipe}, pours={pours}"

    # --- Bloom present or inferable from first bloom pour ---
    bloom = recipe.get("bloom") or {}
    if not bloom.get("water_g"):
        try:
            first_bloom = next((p for p in pours if (p.get("type") or "").lower() == "bloom"), None)
            assert first_bloom and (first_bloom.get("to_g") in (40, 40.0))
        except Exception:
            assert False, f"Bloom not present and cannot be inferred; recipe={recipe}, pours={pours}"

    # --- Timeline or Pours available ---
    timeline = sess.get("timeline") or []
    assert (len(timeline) >= 1) or (len(pours) >= 1), "No timeline/pours found"

    # At least one pour delta (if timeline present) OR a cumulative pour in pours
    if timeline:
        assert any((row.get("water_g") or 0) > 0 for row in timeline if isinstance(row, dict)), f"Timeline lacks water_g deltas: {timeline}"
    else:
        assert any((p.get("to_g") or 0) > 0 for p in pours if isinstance(p, dict)), f"Pours lacks to_g: {pours}"

    # Swirl event either mapped into timeline.agitation or present in events[]
    events = sess.get("events") or []
    has_swirl = any((row.get("agitation") in ("swirl", "stir")) for row in timeline if isinstance(row, dict)) \
                or any(((e.get("event") or "").lower() == "swirl") for e in events if isinstance(e, dict))
    assert has_swirl, f"Expected a swirl event either in timeline.agitation or events[]; timeline={timeline}, events={events}"

    # --- Feedback is optional: just assert type if present ---
    fb = sess.get("feedback")
    assert (fb is None) or isinstance(fb, dict)
