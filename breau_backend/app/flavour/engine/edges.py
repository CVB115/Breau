# breau_backend/app/flavour/engines/edges.py
from pathlib import Path
from typing import List
import json
from .models import NoteEdge
from .taxonomy import TagTaxonomy

# Purpose:
# Load static **note edges** (synergy/suppression/etc.) and validate that
# all tag references are legal under the taxonomy.  :contentReference[oaicite:2]{index=2}

# Purpose:
# Read JSON list of edges into typed models.
def load_edges(path: Path) -> List[NoteEdge]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [NoteEdge(**e) for e in data]

# Purpose:
# Validate tags in edge effects (both add/remove lists). Returns error strings.
def validate_edges(edges: List[NoteEdge], taxonomy: TagTaxonomy) -> List[str]:
    errors: List[str] = []
    for e in edges:
        for t in e.effect.add + e.effect.remove:
            ok, msg = taxonomy.validate_tag(t)
            if not ok:
                errors.append(f"[edge {e.source}->{e.target}] invalid tag: {t} ({msg})")
    return errors
