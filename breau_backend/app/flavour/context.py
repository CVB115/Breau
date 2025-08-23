from pathlib import Path
from typing import List
import json
from .models import ContextModifier
from .taxonomy import TagTaxonomy

def load_context_modifiers(path: Path) -> List[ContextModifier]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ContextModifier(**x) for x in data]

def validate_context_modifiers(mods: List[ContextModifier], taxonomy: TagTaxonomy) -> List[str]:
    errors: List[str] = []
    for m in mods:
        for t in m.tag_weight_deltas.keys():
            ok, msg = taxonomy.validate_tag(t)
            if not ok:
                errors.append(f"[context when={m.when}] invalid tag: {t} ({msg})")
    return errors
