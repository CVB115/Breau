# [App] Updated: init DB on startup + /debug/db
from fastapi import FastAPI
from sqlalchemy import inspect
from .routers import brew,feedback,library
from .db.session import init_db, engine
from .db.seed import seed_defaults

app = FastAPI(title="Breau API", version="0.1.0")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

# Simple smoke test to confirm DB/tables exist
@app.get("/debug/db")
def debug_db():
    return {"tables": inspect(engine).get_table_names()}

@app.post("/debug/seed")
def debug_seed():
    return {"status": seed_defaults()}

app.include_router(brew.router, prefix="/brew", tags=["brew"])
app.include_router(feedback.router)
app.include_router(library.router)