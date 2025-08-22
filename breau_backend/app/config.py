import os

__all__ = ["DB_URL"]

# Default to a local SQLite file at the repo root
DB_URL = os.getenv("BREAU_DB_URL", "sqlite:///./breau.sqlite3")
