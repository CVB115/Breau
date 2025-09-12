# breau_backend/app/services/protocol_generator/postprocess.py
from __future__ import annotations
from typing import List, Optional
from breau_backend.app.schemas import BrewSuggestion, PredictedNote

# What it does:
# Inject top dynamic prior note if it's missing from predictions.
def merge_dynamic_notes_into_prediction(
    predicted: List[PredictedNote],
    dynamic_priors: List[str],
) -> List[PredictedNote]:
    if not predicted or not dynamic_priors:
        return predicted

    predicted_labels = {p.label.lower() for p in predicted}
    top = next((p for p in dynamic_priors if p.lower() not in predicted_labels), None)

    if top:
        predicted.insert(0, PredictedNote(label=top, confidence=0.66))
        seen = set()
        dedup = []
        for p in predicted:
            if p.label.lower() not in seen:
                dedup.append(p)
                seen.add(p.label.lower())
        return dedup[:3]

    return predicted[:3]


# What it does:
# Ensure the BrewSuggestion has an alternative variant (if missing).
def ensure_alternative(
    suggestion: BrewSuggestion,
    alt: BrewSuggestion | None,
) -> BrewSuggestion:
    if suggestion.alternative is not None:
        return suggestion
    suggestion.alternative = alt
    return suggestion
