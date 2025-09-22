# breau_backend/app/utils/strings.py

import re
from unicodedata import normalize

# What it does:
# Strip whitespace or convert falsy/nulls to None
def null_to_none_or_strip(x) -> str | None:
    if not x:
        return None
    return str(x).strip() or None

def safe_filename(name: str, fallback: str = "file") -> str:
    """
    Make a safe, portable filename:
    - strips any path components
    - normalizes unicode
    - keeps only [A-Za-z0-9._-]
    - collapses repeats and trims leading/trailing dots/underscores
    """
    if not name:
        return fallback
    # drop any path portion
    name = name.split("/")[-1].split("\\")[-1]
    # normalize to NFKD and remove disallowed chars
    name = normalize("NFKD", name)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    # collapse underscores and trim junk
    name = re.sub(r"_+", "_", name).strip("._")
    return name or fallback
