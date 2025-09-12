# breau_backend/app/services/nlp/note_ranker.py
# [Improvement A] Semantic-ish ranking with a deterministic, dependency-free embed.
from __future__ import annotations
from typing import List, Dict, Tuple
import math

# [Improvement A] Pure-python cosine
def _cos(u: List[float], v: List[float]) -> float:
    num = sum(a*b for a, b in zip(u, v))
    du  = math.sqrt(sum(a*a for a in u)) or 1e-9
    dv  = math.sqrt(sum(b*b for b in v)) or 1e-9
    return num / (du * dv)

# [Improvement A] Tiny fake embedding – stable, deterministic
def _bag_embed(text: str, tags: List[str]) -> List[float]:
    t = (text or "").lower()
    vowels = sum(t.count(c) for c in "aeiou")
    letters = [ch for ch in t if ch.isalpha()]
    cons   = max(len(letters) - vowels, 0)
    toks   = [w for w in t.replace("/", " ").replace("_", " ").split() if w]
    return [
        len(t) / 256.0,
        vowels / 64.0,
        cons / 64.0,
        len(tags) / 16.0,
        (sum(len(w) for w in toks) / (len(toks) or 1)) / 16.0,
    ]

def embed_goal(goal_text: str, goal_tags: List[str]) -> List[float]:
    txt = (goal_text or "") + " " + " ".join(goal_tags or [])
    return _bag_embed(txt, goal_tags or [])

def embed_note(name: str, desc: str, tags: List[str]) -> List[float]:
    txt = f"{name or ''}. {desc or ''} " + " ".join(tags or [])
    return _bag_embed(txt, tags or [])

def rank_notes(
    goals: List[Dict],            # [{trait, direction, weight}]
    goal_tags: List[str],         # ["sweetness_type:honeyed", ...]
    note_profiles: Dict[str, Dict],   # name -> profile (needs description, tags)
    top_k: int = 8
) -> List[Tuple[str, float]]:
    if not note_profiles:
        return []

    goal_str = " ".join(
        f"{g.get('direction','')} {g.get('trait','')}".strip()
        for g in (goals or [])
    )
    g_vec = embed_goal(goal_str, goal_tags or [])

    scored: List[Tuple[str, float]] = []
    for name, prof in note_profiles.items():
        desc = prof.get("description", name)
        tags = prof.get("tags", [])
        n_vec = embed_note(name, desc, tags)
        sim = _cos(g_vec, n_vec)
        # Light tag overlap bonus to respect your rules
        tag_overlap = len(set(goal_tags or []) & set(tags))
        bonus = 0.03 * tag_overlap
        scored.append((name, sim + bonus))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:max(0, int(top_k))]
