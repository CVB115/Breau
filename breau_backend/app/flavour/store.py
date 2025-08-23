from pathlib import Path
from functools import lru_cache
import os
from .taxonomy import load_taxonomy
from .notes import load_notes, validate_notes
from .edges import load_edges, validate_edges
from .context import load_context_modifiers, validate_context_modifiers

DATA_DIR = Path(os.environ.get("BREAU_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))

class FlavourOntology:
    def __init__(self, taxonomy, notes, edges, context):
        self.taxonomy = taxonomy
        self.notes = notes
        self.edges = edges
        self.context = context

@lru_cache(maxsize=1)
def get_ontology() -> FlavourOntology:
    taxonomy = load_taxonomy(DATA_DIR / "tag_taxonomy.yaml")
    notes = load_notes(DATA_DIR / "note_profiles.json")
    edges = load_edges(DATA_DIR / "note_edges.json")
    context = load_context_modifiers(DATA_DIR / "context_modifiers.json")

    errors = []
    errors += validate_notes(notes, taxonomy)
    errors += validate_edges(edges, taxonomy)
    errors += validate_context_modifiers(context, taxonomy)
    if errors:
        raise ValueError("Flavour ontology validation failed:\n" + "\n".join(errors))
    return FlavourOntology(taxonomy, notes, edges, context)
