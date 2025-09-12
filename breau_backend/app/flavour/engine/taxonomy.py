# breau_backend/app/flavour/engines/taxonomy.py
from typing import Dict, List, Set, Tuple
from pathlib import Path
import yaml

# Purpose:
# Define and load a **tag taxonomy** used by notes/edges/context rules.
# Tags use the canonical "facet:value" form (e.g., "aroma:floral").
# This module provides (1) a small TagTaxonomy class and (2) a YAML loader.

class TagTaxonomy:
    # Purpose:
    # Construct with facet enumerations + optional alias lists.
    def __init__(self, facets: Dict[str, List[str]], aliases: Dict[str, List[str]]):
        self.facets = facets
        self.aliases = aliases
        # Precompute allowed tags for fast validation.
        self.allowed: Set[str] = {f"{f}:{v}" for f, vs in facets.items() for v in vs}

    def validate_tag(self, tag: str) -> Tuple[bool, str]:
        # Purpose:
        # Validate the string is "facet:value" and present in the allowed set.
        if ":" not in tag:
            return False, "Tag must be 'facet:value'"
        if tag not in self.allowed:
            return False, f"Unknown tag {tag}"
        return True, ""

# Purpose:
# Load a taxonomy YAML of the shape:
# facets:
#   aroma: [floral, citrus, ...]
#   mouthfeel: [silky, syrupy, ...]
# aliases:
#   floral: [flower, blossom]
def load_taxonomy(path: Path) -> TagTaxonomy:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return TagTaxonomy(data["facets"], data.get("aliases", {}))
