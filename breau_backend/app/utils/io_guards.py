# breau_backend/app/utils/io_guards.py
from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable, Optional

from breau_backend.app.config.paths import (
    get_priors_dir,
    get_rules_dir,
)

_FLAVOUR_READONLY_ROOTS = {get_rules_dir().resolve(), get_priors_dir().resolve()}

def _is_under(path: Path, roots: Iterable[Path]) -> bool:
    p = path.resolve()
    for r in roots:
        try:
            p.relative_to(r)
            return True
        except ValueError:
            continue
    return False

def assert_readonly(path: Path) -> None:
    """
    Raise an AssertionError if `path` is under app/flavour/rules or app/flavour/priors.
    Intended for development / CI; call before any write.
    """
    if _is_under(path, _FLAVOUR_READONLY_ROOTS):
        raise AssertionError(
            f"Attempted write under read-only flavour directory: {path} "
            f"(rules={get_rules_dir()}, priors={get_priors_dir()})"
        )

def safe_open_for_write(path: Path, mode: str = "w", encoding: Optional[str] = "utf-8") -> io.TextIOBase:
    """
    Open a file for writing, asserting it is NOT under read-only flavour dirs.
    Creates parent directories if needed.
    """
    if "w" not in mode and "a" not in mode and "x" not in mode and "+" not in mode:
        # Not a write mode; pass-through (still safe).
        return path.open(mode=mode, encoding=encoding)  # type: ignore[arg-type]

    assert_readonly(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open(mode=mode, encoding=encoding)  # type: ignore[arg-type]
