import os  # <-- add this import at the top of the file

# Ensure these defaults are present even if fixtures haven’t run yet.
os.environ.setdefault("LEARNING_THRESHOLD", "3")
os.environ.setdefault("BREAU_LEARNING_THRESHOLD", "3")
os.environ.setdefault("BREAU_BANDIT_WARMUP", "3")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from breau_backend.app.routers import feedback, profile, beans, brew

app = FastAPI(title="Breau API", version="0.1.0")

# What it does:
# Open CORS for local dev/tests; tighten for prod if needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# What it does:
# Health endpoint (tests hit this) and OpenAPI at /openapi.json (auto).
@app.get("/")
def health():
    return {"ok": True, "service": "breau-backend"}

# What it does:
# Mount the routers the tests look for.
app.include_router(feedback.router)
app.include_router(profile.router)
app.include_router(beans.router)
app.include_router(brew.router)
