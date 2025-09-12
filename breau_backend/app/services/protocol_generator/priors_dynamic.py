# breau_backend/app/services/protocol_generator/priors_dynamic.py
from __future__ import annotations

from collections import defaultdict, Counter
from threading import Lock
from typing import Dict, List, Tuple, Any
import json
import os

from breau_backend.app.schemas import BrewFeedbackIn
from .note_loader import cluster_key

from breau_backend.app.config.paths import path_under_data, ensure_data_dir_exists

_LOCK = Lock()

# What it stores in memory (by cluster: "process:roast:filter"):
# - _NOTES  : Counter(note -> count) from confirmed/missing notes
# - _TRAITS : dict(trait -> accumulated delta)
# - _RATING : (count, sum) so we can compute average rating on read
_NOTES: Dict[str, Counter] = defaultdict(Counter)
_TRAITS: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
_RATING: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))

# Purpose:
# Always store priors under DATA_DIR/priors/priors_dynamic.json (mutable runtime).
def _store_path() -> str:
    ensure_data_dir_exists("priors")
    return str(path_under_data("priors", "priors_dynamic.json"))

# Purpose:
# Best-effort load from disk into the in-memory structures (quiet on failure).
def _safe_load() -> None:
    try:
        with _LOCK:
            p = _store_path()
            if not os.path.exists(p):
                return
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            notes_raw = data.get("notes", {})
            traits_raw = data.get("traits", {})
            rating_raw = data.get("rating", {})

            _NOTES.clear(); _TRAITS.clear(); _RATING.clear()

            for k, d in notes_raw.items():
                _NOTES[k] = Counter(d or {})

            for k, d in traits_raw.items():
                _TRAITS[k] = defaultdict(float, d or {})

            for k, pair in rating_raw.items():
                try:
                    c, s = pair
                    _RATING[k] = (int(c), int(s))
                except Exception:
                    pass
    except Exception:
        # keep quiet, tests will still pass without persisted state
        pass

# Purpose:
# Atomically dump current state to disk (quiet on failure).
def _safe_dump() -> None:
    try:
        final_path = _store_path()
        tmp_path = final_path + ".tmp"
        data = {
            "notes": {k: dict(v) for k, v in _NOTES.items()},
            "traits": {k: dict(v) for k, v in _TRAITS.items()},
            "rating": {k: list(v) for k, v in _RATING.items()},
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, final_path)  # atomic on same filesystem
    except Exception:
        # keep quiet in tests
        pass

# Load any existing state at import time (safe if file absent)
_safe_load()

# Purpose:
# Update dynamic priors given a BrewFeedbackIn-like object.
# Steps:
#  - derive cluster from bean process/roast/filter
#  - increment/decrement note counts
#  - add trait deltas
#  - update rating (count/sum)
# Returns: small debug snapshot for the caller.
def record_feedback(fb: BrewFeedbackIn | Any) -> dict:
    # extract fields generously
    bean_process = getattr(fb, "bean_process", None) or (fb.get("bean_process") if isinstance(fb, dict) else None)
    roast_level = getattr(fb, "roast_level", None) or (fb.get("roast_level") if isinstance(fb, dict) else None)
    filter_perm = getattr(fb, "filter_permeability", None) or (fb.get("filter_permeability") if isinstance(fb, dict) else None)

    key = cluster_key(
        (bean_process or "").strip().lower() or None,
        (roast_level or "").strip().lower() or None,
        (filter_perm or "").strip().lower() or None,
    )

    notes_pos = getattr(fb, "notes_positive", None) or (fb.get("notes_positive") if isinstance(fb, dict) else []) or []
    notes_neg = getattr(fb, "notes_negative", None) or (fb.get("notes_negative") if isinstance(fb, dict) else []) or []
    traits_delta = getattr(fb, "traits_delta", None) or (fb.get("traits_delta") if isinstance(fb, dict) else {}) or {}
    rating = getattr(fb, "rating", None) or (fb.get("rating") if isinstance(fb, dict) else None)

    with _LOCK:
        for n in notes_pos:
            n2 = str(n).strip().lower()
            if n2:
                _NOTES[key][n2] += 1
        for n in notes_neg:
            n2 = str(n).strip().lower()
            if n2:
                _NOTES[key][n2] -= 1

        for t, delta in (traits_delta or {}).items():
            try:
                _TRAITS[key][str(t).strip().lower()] += float(delta)
            except Exception:
                pass

        if rating is not None:
            c, s = _RATING.get(key, (0, 0))
            try:
                r = int(rating)
                _RATING[key] = (c + 1, s + r)
            except Exception:
                _RATING[key] = (c, s)

    _safe_dump()
    return {
        "cluster": key,
        "top_notes": _NOTES[key].most_common(5),
        "traits": dict(_TRAITS[key]),
        "rating": _RATING.get(key, (0, 0)),
    }

# Purpose:
# Read helpers (used by builder/router) to surface current dynamic priors.
def get_dynamic_notes_for(key: str, top_k: int = 5) -> List[tuple[str, int]]:
    with _LOCK:
        ctr = _NOTES.get(key, Counter())
        return ctr.most_common(max(1, int(top_k)))

def get_dynamic_traits_for(key: str) -> Dict[str, float]:
    with _LOCK:
        return dict(_TRAITS.get(key, {}))

def rating_summary_for(key: str) -> tuple[int, float]:
    with _LOCK:
        c, s = _RATING.get(key, (0, 0))
        return c, (s / c if c else 0.0)
    
def get_prior_notes(cluster: str | None = None, top_k: int = 5, *_, **__):
    if not cluster: return []
    return [label for (label, _cnt) in get_dynamic_notes_for(cluster, top_k=max(1, int(top_k)))]

def get_prior_traits(cluster: str | None = None, *_, **__):
    return get_dynamic_traits_for(cluster) if cluster else {}

def get_prior_rating(cluster: str | None = None, *_, **__):
    if not cluster: return {"count": 0, "avg": 0.0}
    c, avg = rating_summary_for(cluster)
    return {"count": int(c), "avg": float(avg)}