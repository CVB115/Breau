from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

@dataclass
class SuggestionTrace:
    base_vars: Dict[str, Any]
    goal_vec: Dict[str, float]
    rule_delta: Dict[str, float]
    model_delta: Dict[str, float]
    alpha: float
    final_delta: Dict[str, float]
    clips: List[str]
    notes_top3: List[str]
    reasons: Optional[List[str]] = None
    warnings: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
