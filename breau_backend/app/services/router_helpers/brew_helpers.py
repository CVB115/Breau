from __future__ import annotations
from typing import Any, List, Dict
import time, random
from fastapi import HTTPException, status

from breau_backend.app.schemas import (
    BrewSuggestRequest, BrewSuggestion,  # BrewFeedbackIn (not required here)
    PourStepIn, Agitation,BrewFeedbackIn
)

from breau_backend.app.services.protocol_generator.builder import build_suggestion
from breau_backend.app.services.protocol_generator.session_plan import build_session_plan
from breau_backend.app.services.protocol_generator.fallback import build_fallback_suggestion

# Priors (static + dynamic)
from breau_backend.app.services.protocol_generator.note_loader import get_prior_notes
from breau_backend.app.services.protocol_generator.priors_dynamic import (
    record_feedback as _record_dynamic_priors,
    get_dynamic_notes_for as _get_dynamic_notes_for,
    get_dynamic_traits_for as _get_dynamic_traits_for,
    rating_summary_for as _rating_summary_for,
)

# Learning feedback flow (tolerant FeedbackIn path)
from breau_backend.app.models.feedback import FeedbackIn, RatingBlock, ProtocolBlock, GoalItem  # permissive model
from breau_backend.app.services.learning.feedback_flow import handle_feedback as _handle_feedback_flow

# Optional: NLP free‑text → goals
try:
    from breau_backend.app.services.nlp.text_to_goals import parse_text_to_goals  # type: ignore
except Exception:  # pragma: no cover
    def parse_text_to_goals(_text: str) -> list[dict]:
        return []


# ----------------------------------------------------------------------
# Suggestion (protocol generator)
# ----------------------------------------------------------------------

def suggest(req: BrewSuggestRequest) -> BrewSuggestion:
    try:
        return build_suggestion(req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"suggest failed: {e}",
        )


# ----------------------------------------------------------------------
# Resolve free-text → goals
# ----------------------------------------------------------------------

def resolve_goals(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = (payload or {}).get("text") or ""
    goals = parse_text_to_goals(text)

    process = (payload.get("bean", {}) or {}).get("process") or payload.get("process") or "washed"
    roast   = (payload.get("bean", {}) or {}).get("roast_level") or payload.get("roast_level") or "light"
    filt    = payload.get("filter_permeability") or "fast"
    cluster_preview = f"{process}:{roast}:{filt}"

    return {
        "resolved": {"goals": goals},
        "cluster_preview": cluster_preview,
        "ok": True,
        "text": text,
    }


# ----------------------------------------------------------------------
# Plan: pours + agitation → session plan
# ----------------------------------------------------------------------

def plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        pours_raw: List[dict] = (payload or {}).get("pours") or []
        ag_early = (payload or {}).get("agitation_early", "moderate")
        ag_late  = (payload or {}).get("agitation_late", "moderate")

        def _to_ag(val) -> Agitation:
            if isinstance(val, Agitation):
                return val
            s = str(val).lower()
            return {
                "gentle": Agitation.GENTLE, "low": Agitation.GENTLE,
                "moderate": Agitation.MODERATE, "medium": Agitation.MODERATE,
                "high": getattr(Agitation, "ROBUST", Agitation.MODERATE),
                "robust": getattr(Agitation, "ROBUST", Agitation.MODERATE),
            }.get(s, Agitation.MODERATE)

        pours = [PourStepIn(**p) for p in pours_raw]
        plan_obj = build_session_plan(pours, _to_ag(ag_early), _to_ag(ag_late))
        return {"ok": True, "plan": plan_obj}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"plan failed: {e}",
        )


# ----------------------------------------------------------------------
# Fallback: minimal safe recipe
# ----------------------------------------------------------------------

def fallback() -> dict[str, Any]:
    return {"ok": True, "suggestion": build_fallback_suggestion()}


# ----------------------------------------------------------------------
# Feedback (tolerant) → learning flow
# ----------------------------------------------------------------------

def _as_feedback_in_from_flat(payload: Dict[str, Any]) -> FeedbackIn:
    """
    Build a permissive FeedbackIn from the flat test shape:
      user_id, session_id, bean_process, roast_level, filter_permeability,
      rating, notes_positive, notes_negative, traits_positive, traits_negative
    """
    beans_meta = {
        "process": payload.get("bean_process"),
        "roast_level": payload.get("roast_level"),
        "filter_permeability": payload.get("filter_permeability"),
    }
    protocol = ProtocolBlock(
        method=payload.get("method"),
        ratio=payload.get("ratio"),
        temperature_c=payload.get("temperature_c"),
        grind_label=payload.get("grind_label"),
        agitation_overall=payload.get("agitation_overall"),
    )
    ratings = RatingBlock(overall=payload.get("rating"))

    goals: List[GoalItem] = []
    tp = payload.get("traits_positive") or []
    if isinstance(tp, list) and tp:
        goals.append(GoalItem(tags=[str(t) for t in tp if t]))

    # ↓↓↓ instantiate FeedbackIn (NOT ModelFeedbackIn)
    return FeedbackIn(
        user_id=str(payload.get("user_id") or ""),
        session_id=str(payload.get("session_id") or ""),
        beans_meta=beans_meta,
        protocol=protocol,
        ratings=ratings,
        goals=(goals or None),
        notes_confirmed=[str(n) for n in (payload.get("notes_positive") or []) if n],
        notes_missing=[str(n) for n in (payload.get("notes_negative") or []) if n],
        payload=payload,
    )

def feedback_any(payload: Dict[str, Any]) -> Dict[str, Any]:
    # --- minimal contract: require user_id; session_id is optional ---
    uid = str(payload.get("user_id") or "").strip()
    if not uid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="user_id is required")

    sid = str(payload.get("session_id") or "").strip()
    if not sid:
        sid = f"auto-{int(time.time()*1000)}-{random.randint(1000,9999)}"
        payload["session_id"] = sid  # so it flows into the model/persistence

    # Try flat adapter; if it fails, bubble a 400
    try:
        fb = _as_feedback_in_from_flat(payload)  # returns FeedbackIn
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"invalid feedback payload: {e}")

    # Hand off to unified feedback flow (persists + updates learners)
    try:
        return _handle_feedback_flow(fb)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"feedback failed: {e}")


# ----------------------------------------------------------------------
# Priors: read dynamic + static priors for a cluster
# ----------------------------------------------------------------------

def _normalize_rating(rating_raw: Any) -> Dict[str, Any]:
    if isinstance(rating_raw, dict):
        return {"count": int(rating_raw.get("count", 0)), **{k: v for k, v in rating_raw.items() if k != "count"}}
    if isinstance(rating_raw, (list, tuple)):
        if len(rating_raw) == 0:
            return {"count": 0}
        if len(rating_raw) == 1:
            return {"count": int(rating_raw[0] or 0)}
        d = {"count": int(rating_raw[0] or 0), "avg": float(rating_raw[1] or 0)}
        if len(rating_raw) >= 3:
            try:
                d["sum"] = float(rating_raw[2])
            except Exception:
                pass
        return d
    try:
        return {"count": int(rating_raw)}
    except Exception:
        return {"count": 0}

def priors_by_cluster(cluster: str, top_k: int = 5) -> dict[str, Any]:
    k = max(1, int(top_k))
    dyn_pairs = _get_dynamic_notes_for(cluster, top_k=k) or []
    dynamic_notes_top = [str(name) for (name, _cnt) in dyn_pairs if name]
    static_notes = get_prior_notes(cluster) or []
    dynamic_traits = _get_dynamic_traits_for(cluster) or {}
    rating_raw = _rating_summary_for(cluster)
    rating = _normalize_rating(rating_raw)
    return {
        "cluster": cluster,
        "top_k": k,
        "dynamic_notes_top": dynamic_notes_top,
        "static_notes": static_notes,
        "dynamic_traits": dynamic_traits,
        "rating": rating,
    }

def priors_by_path(process: str, roast: str, permeability: str, top_k: int = 5) -> dict[str, Any]:
    cluster = f"{process.strip().lower()}:{roast.strip().lower()}:{permeability.strip().lower()}"
    return priors_by_cluster(cluster, top_k=top_k)

def read_dynamic_priors(cluster: str, top_k: int = 5) -> dict[str, Any]:
    pairs = _get_dynamic_notes_for(cluster, top_k=max(1, int(top_k))) or []
    return {"cluster": cluster, "top_notes": pairs}

def feedback(fb: BrewFeedbackIn) -> dict[str, Any]:
    """
    Record post‑brew feedback into dynamic priors (notes + traits).
    Also validate minimal contract so clearly invalid payloads return 4xx.
    """
    # Minimal contract checks expected by tests
    if not getattr(fb, "user_id", None) or not str(fb.user_id).strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="user_id is required")
    if not getattr(fb, "session_id", None) or not str(fb.session_id).strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="session_id is required")

    snapshot = _record_dynamic_priors(fb)
    return {"ok": True, "snapshot": snapshot}