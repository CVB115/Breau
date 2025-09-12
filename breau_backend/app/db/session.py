# breau_backend/app/db/session.py

# [DB Session] Engine + helpers
from sqlmodel import SQLModel, create_engine, Session
from breau_backend.app.config import DB_URL  # absolute import (exported by app/config/__init__.py)
from breau_backend.app.config.paths import DATA_DIR

# Ensure /data exists (needed for sqlite file URLs)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# SQLite needs check_same_thread=False for typical FastAPI usage; keep your original behavior
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

# Create the engine
engine = create_engine(DB_URL, echo=False, connect_args=connect_args)

def init_db() -> None:
    # Ensure table definitions are registered before create_all
    from . import models  # noqa: F401
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
