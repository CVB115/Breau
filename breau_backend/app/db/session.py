# [DB Session] Engine + helpers
from sqlmodel import SQLModel, create_engine, Session
from breau_backend.app.config import DB_URL  # absolute import

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, echo=False, connect_args=connect_args)

def init_db() -> None:
    from . import models  # ensure table definitions are registered
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
