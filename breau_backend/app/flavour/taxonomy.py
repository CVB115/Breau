from typing import Dict, List, Set, Tuple
from pathlib import Path
import yaml

class TagTaxonomy:
    def __init__(self, facets: Dict[str, List[str]], aliases: Dict[str, List[str]]):
        self.facets = facets
        self.aliases = aliases
        self.allowed: Set[str] = {f"{f}:{v}" for f, vs in facets.items() for v in vs}

    def validate_tag(self, tag: str) -> Tuple[bool, str]:
        if ":" not in tag:
            return False, "Tag must be 'facet:value'"
        if tag not in self.allowed:
            return False, f"Unknown tag {tag}"
        return True, ""

def load_taxonomy(path: Path) -> TagTaxonomy:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return TagTaxonomy(data["facets"], data.get("aliases", {}))
