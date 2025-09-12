# breau_backend/app/utils/strings.py

# What it does:
# Strip whitespace or convert falsy/nulls to None
def null_to_none_or_strip(x) -> str | None:
    if not x:
        return None
    return str(x).strip() or None
