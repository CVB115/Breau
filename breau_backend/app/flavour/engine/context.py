# breau_backend/app/flavour/engines/context.py
from pathlib import Path
from typing import List
import json
from .models import ContextModifier
from .taxonomy import TagTaxonomy

# Purpose:
# Load and validate “context modifiers”, which tweak tag/edge weights when certain
# brewing context conditions are met (e.g., geometry, roast). These are small, static
# rules that nudge the flavor graph before note ranking.  :contentReference[oaicite:0]{index=0}

# Purpose:
# Read JSON file of context modifiers into typed models.
def load_context_modifiers(path: Path) -> List[ContextModifier]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ContextModifier(**x) for x in data]

# Purpose:
# Validate that every tag referenced by the modifiers exists in the taxonomy.
# Returns a list of error strings (empty if all good).
def validate_context_modifiers(mods: List[ContextModifier], taxonomy: TagTaxonomy) -> List[str]:
    errors: List[str] = []
    for m in mods:
        for t in m.tag_weight_deltas.keys():
            ok, msg = taxonomy.validate_tag(t)
            if not ok:
                errors.append(f"[context when={m.when}] invalid tag: {t} ({msg})")
    return errors
