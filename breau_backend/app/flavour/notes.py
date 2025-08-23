from pathlib import Path
from typing import Dict, List
import json
from .models import NoteProfile
from .taxonomy import TagTaxonomy

def load_notes(path: Path) -> Dict[str, NoteProfile]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    notes: Dict[str, NoteProfile] = {}
    for key, val in raw.items():
        if key == "schema_version":
            continue
        notes[key] = NoteProfile(**val)
    return notes

def validate_notes(notes: Dict[str, NoteProfile], taxonomy: TagTaxonomy) -> List[str]:
    errors: List[str] = []
    for k, n in notes.items():
        for t in n.tags:
            ok, msg = taxonomy.validate_tag(t)
            if not ok:
                errors.append(f"[{k}] invalid tag: {t} ({msg})")
        for spk, sp in n.sub_profiles.items():
            for t in sp.tags:
                ok, msg = taxonomy.validate_tag(t)
                if not ok:
                    errors.append(f"[{k}.{spk}] invalid tag: {t} ({msg})")
    return errors
