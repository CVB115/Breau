from __future__ import annotations
import json, os, shutil
from pathlib import Path
from typing import Any, Union, Optional

Pathish = Union[str, Path]

def _as_path(p: Pathish) -> Path:
    return p if isinstance(p, Path) else Path(p)

def ensure_dir(p: Pathish) -> Path:
    path = _as_path(p)
    target = (path.parent if path.suffix else path)
    target.mkdir(parents=True, exist_ok=True)
    return target

def data_dir(*parts: str) -> Path:
    base = Path(os.getenv("DATA_DIR", "./data")).resolve()
    return base.joinpath(*parts)

def read_json(path: Pathish, default: Any = None, *, encoding: str = "utf-8") -> Any:
    p = _as_path(path)
    try:
        if p.exists() and p.is_file():
            return json.loads(p.read_text(encoding=encoding))
    except Exception:
        pass
    return default

def write_json(path: Pathish, obj: Any, *, encoding: str = "utf-8", indent: int = 2) -> None:
    p = _as_path(path)
    ensure_dir(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=indent), encoding=encoding)
    tmp.replace(p)

# Optional convenience
def read_text(path: Pathish, default: Optional[str] = None, *, encoding: str = "utf-8") -> Optional[str]:
    p = _as_path(path)
    try:
        if p.exists() and p.is_file():
            return p.read_text(encoding=encoding)
    except Exception:
        pass
    return default

def write_text(path: Pathish, text: str, *, encoding: str = "utf-8") -> None:
    p = _as_path(path)
    ensure_dir(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    tmp.replace(p)

def copy_file(src: Pathish, dst: Pathish) -> None:
    src_p, dst_p = _as_path(src), _as_path(dst)
    ensure_dir(dst_p)
    tmp = dst_p.with_suffix(dst_p.suffix + ".tmp")
    shutil.copy2(src_p, tmp)
    tmp.replace(dst_p)
