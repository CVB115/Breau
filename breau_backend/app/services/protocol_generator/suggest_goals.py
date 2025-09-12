# breau_backend/app/services/protocol_generator/suggest_goals.py
from __future__ import annotations
from typing import List, Tuple, Dict
from breau_backend.app.schemas import BrewSuggestRequest
from .goal_matcher import merge_goals, goals_as_phrases_and_weighted
from .note_loader import goals_to_tags

# Optional NLP; safe fallbacks if model not available.
try:
    from breau_backend.app.services.nlp.goal_tagger import infer_tags, tags_to_trait_weights  # type: ignore
except Exception:
    infer_tags = lambda *_a, **_k: []
    tags_to_trait_weights = lambda *_a, **_k: {}

# What it does:
# Normalize explicit/parsed/semantic goals and derive goal_tags + trait weights.
def resolve_goals_and_traits(
    req: BrewSuggestRequest,
) -> tuple[list[tuple[str, float]], list[str], dict]:
    mg = merge_goals(
        explicit=getattr(req, "goals", None) or [],
        parsed=getattr(req, "parsed_goals", None) or [],
        semantic=getattr(req, "semantic_goals", None) or [],
    )
    phrases, weighted = goals_as_phrases_and_weighted(mg)
    goal_tags = goals_to_tags(phrases)

    # optional free-text → tag scores → trait weights
    tag_scores = infer_tags(getattr(req, "goals_text", "") or "", top_k=6)
    trait_weights = tags_to_trait_weights(tag_scores) if tag_scores else {}

    return weighted, goal_tags, trait_weights
