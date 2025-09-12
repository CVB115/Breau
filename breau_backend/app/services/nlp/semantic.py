# breau_backend/app/services/nlp/semantic.py
from __future__ import annotations
from functools import lru_cache
from typing import List, Tuple

# Optional heavy dependency; we provide a light fallback if missing
try:
    from sentence_transformers import SentenceTransformer, util  # type: ignore
except Exception:  # pragma: no cover
    SentenceTransformer = None
    util = None

# --------- Heavy model path (optional) ----------
@lru_cache(maxsize=1)
def _model() -> "SentenceTransformer | None":
    if SentenceTransformer is None:
        return None
    try:
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:  # pragma: no cover
        return None

def _embed(texts: List[str]):
    m = _model()
    if m is None:
        return None
    try:
        return m.encode(texts, normalize_embeddings=True)
    except Exception:
        return None

# --------- Lightweight fallback (no deps) ----------
def _tokenize(s: str) -> set[str]:
    import re
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))

def _jaccard(a: str, b: str) -> float:
    A, B = _tokenize(a), _tokenize(b)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    union = len(A | B) or 1
    return inter / union

# --------- Public API ----------
def best_match(query: str, candidates: List[str]) -> Tuple[str, float]:
    """
    Return (best_candidate, score). Uses sentence-transformers if available;
    otherwise falls back to token Jaccard similarity.
    """
    embs = _embed([query] + candidates)
    if embs is not None and util is not None:
        q = embs[0:1]
        C = embs[1:]
        sims = util.cos_sim(q, C)[0].tolist()
        i = int(max(range(len(sims)), key=lambda k: sims[k])) if sims else 0
        return candidates[i], float(sims[i]) if sims else 0.0

    # Fallback: Jaccard
    scores = [(_jaccard(query, c), c) for c in candidates]
    scores.sort(key=lambda x: x[0], reverse=True)
    if not scores:
        return "", 0.0
    s, c = scores[0]
    return c, float(s)

def any_matches(query: str, candidates: List[str], threshold: float = 0.45) -> List[Tuple[str, float]]:
    embs = _embed([query] + candidates)
    if embs is not None and util is not None:
        q = embs[0:1]
        C = embs[1:]
        sims = util.cos_sim(q, C)[0].tolist()
        out = [(c, float(s)) for c, s in zip(candidates, sims) if s >= threshold]
        out.sort(key=lambda x: x[1], reverse=True)
        return out

    # Fallback: Jaccard
    out = [(c, _jaccard(query, c)) for c in candidates if _jaccard(query, c) >= threshold]
    out.sort(key=lambda x: x[1], reverse=True)
    return out
