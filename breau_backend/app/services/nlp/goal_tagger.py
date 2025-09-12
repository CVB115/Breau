# breau_backend/app/services/nlp/goal_tagger.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple
import json

# Centralized path resolver (A1)
from breau_backend.app.config.paths import resolve_rules_file

# Optional semantic enrichment
try:
    from sentence_transformers import SentenceTransformer, util  # type: ignore
except Exception:  # pragma: no cover
    SentenceTransformer = None
    util = None

# Lazy globals
_MODEL = None
_LEX: Dict | None = None
_CAN_USE_EMB: bool | None = None

def _load_lexicon() -> Dict:
    """
    Load tag_lexicon.json from canonical rules/ (with soft legacy fallback).
    """
    global _LEX
    if _LEX is not None:
        return _LEX

    # Prefer rules/
    try:
        p = resolve_rules_file("tag_lexicon.json")
        if p.exists():
            _LEX = json.loads(p.read_text(encoding="utf-8"))
            return _LEX
    except Exception:
        pass

    # Legacy fallback (for transition only)
    legacy = Path("data/tag_lexicon.json")
    if legacy.exists():
        _LEX = json.loads(legacy.read_text(encoding="utf-8"))
        print("[WARN] DEPRECATED PATH USED: data/tag_lexicon.json (please move to rules/tag_lexicon.json)")
        return _LEX

    # Empty default (robust)
    _LEX = {}
    return _LEX

def _model() -> "SentenceTransformer | None":
    global _MODEL, _CAN_USE_EMB
    if _CAN_USE_EMB is False:
        return None
    if SentenceTransformer is None:
        _CAN_USE_EMB = False
        return None
    if _MODEL is None:
        try:
            _MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            _CAN_USE_EMB = True
        except Exception:  # pragma: no cover
            _CAN_USE_EMB = False
            _MODEL = None
    return _MODEL

def infer_tags(text: str, top_k: int = 5) -> List[Tuple[str, float]]:
    """
    Returns [(tag, score 0..1)] using:
      1) keyword/alias matches (fast, deterministic)
      2) optional semantic enrichment if sentence-transformers is available
    """
    if not text or not text.strip():
        return []

    text_norm = text.lower().strip()
    lex = _load_lexicon()

    # 1) quick keyword scores
    scores: Dict[str, float] = {}
    for tag, spec in lex.items():
        alias_hit = 0.0
        for a in [tag] + spec.get("aliases", []):
            a_norm = a.lower()
            if a_norm in text_norm:
                alias_hit = max(alias_hit, 1.0 if len(a_norm) > 4 else 0.7)
        if alias_hit > 0:
            scores[tag] = max(scores.get(tag, 0.0), alias_hit)

    # 2) semantic enrichment (optional)
    model = _model()
    if model is not None and util is not None and lex:
        tag_phrases: List[str] = []
        tag_index: List[str] = []
        for tag, spec in lex.items():
            phrases = [tag] + spec.get("aliases", [])
            for ph in phrases:
                tag_phrases.append(ph)
                tag_index.append(tag)

        try:
            emb_text = model.encode([text_norm], normalize_embeddings=True)
            emb_phr  = model.encode(tag_phrases, normalize_embeddings=True)
            sim = util.cos_sim(emb_text, emb_phr)[0].tolist()
            for s, tag in zip(sim, tag_index):
                # convert cosine (-1..1) → (0..1)
                val = max(0.0, min(1.0, (float(s) + 1.0) / 2.0))
                if val > 0.5:
                    scores[tag] = max(scores.get(tag, 0.0), val)
        except Exception:
            pass

    if not scores:
        return []
    mx = max(scores.values())
    normed = {k: (v / mx) for k, v in scores.items() if mx > 0}
    ranked = sorted(normed.items(), key=lambda x: x[1], reverse=True)[: max(0, int(top_k))]
    return ranked

def tags_to_trait_weights(tag_scores: List[Tuple[str, float]]) -> Dict[str, float]:
    """
    Map tags → trait contributions using lexicon's "traits" mapping.
    """
    if not tag_scores:
        return {}
    lex = _load_lexicon()
    agg: Dict[str, float] = {}
    for tag, s in tag_scores:
        spec = lex.get(tag, {})
        traits = spec.get("traits", {})
        for t, w in traits.items():
            agg[t] = agg.get(t, 0.0) + s * w
    return agg
