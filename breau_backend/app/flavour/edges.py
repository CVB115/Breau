from pathlib import Path
from typing import List
import json
from .models import NoteEdge
from .taxonomy import TagTaxonomy

def load_edges(path: Path) -> List[NoteEdge]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [NoteEdge(**e) for e in data]

def validate_edges(edges: List[NoteEdge], taxonomy: TagTaxonomy) -> List[str]:
    errors: List[str] = []
    for e in edges:
        for t in e.effect.add + e.effect.remove:
            ok, msg = taxonomy.validate_tag(t)
            if not ok:
                errors.append(f"[edge {e.source}->{e.target}] invalid tag: {t} ({msg})")
    return errors
