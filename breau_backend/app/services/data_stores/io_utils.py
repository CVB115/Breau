# breau_backend/app/services/data_stores/io_utils.py
from __future__ import annotations

import json, os, tempfile, shutil
from pathlib import Path
from typing import Any, Iterable, Optional

from breau_backend.app.utils.io_guards import assert_readonly

def atomic_write(path: Path, text: str) -> None:
    """
    Atomic, guarded text write. Prevents writes under read-only rule/priors dirs.
    """
    assert_readonly(path)  # raises if path is under app/flavour/{rules,priors}
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tf:
        tf.write(text)
        tmp = Path(tf.name)
    try:
        os.replace(tmp, path)   # atomic where supported
    except Exception:
        shutil.move(str(tmp), str(path))

def read_json(path: Path, default: Any):
    """
    Safe JSON reader. Returns `default` if missing or invalid.
    """
    if not path.exists():
        return default
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else default
    except Exception:
        return default

def append_jsonl(path: Path, obj: Any) -> None:
    """
    Append a JSON object as a single line to a .jsonl file (guarded).
    """
    assert_readonly(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False))
        f.write("\n")
