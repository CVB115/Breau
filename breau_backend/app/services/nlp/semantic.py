from functools import lru_cache
from typing import List, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer, util

@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    # Small, fast, robust for semantic intent
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def _embed(texts: List[str]) -> np.ndarray:
    return _model().encode(texts, normalize_embeddings=True)

def best_match(query: str, candidates: List[str]) -> Tuple[str, float]:
    q = _embed([query])[0]
    C = _embed(candidates)
    sims = util.cos_sim(q, C).cpu().numpy().flatten()
    i = int(np.argmax(sims))
    return candidates[i], float(sims[i])

def any_matches(query: str, candidates: List[str], threshold: float = 0.45) -> List[Tuple[str, float]]:
    q = _embed([query])[0]
    C = _embed(candidates)
    sims = util.cos_sim(q, C).cpu().numpy().flatten()
    out = [(c, float(s)) for c, s in zip(candidates, sims) if s >= threshold]
    out.sort(key=lambda x: x[1], reverse=True)
    return out
