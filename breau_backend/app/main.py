# main.py — backend entrypoint (copy-paste)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Breau API")

# --- CORS for Vite dev -------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include routers under /api ----------------------------------------------
def _include(module_name: str, prefix: str = "/api"):
    """
    Try a few import paths and include the router if present.
    This keeps things working regardless of your package name.
    """
    import importlib
    for mod in (
        f"breau_backend.app.routers.{module_name}",
        f"app.routers.{module_name}",
        f"routers.{module_name}",
    ):
        try:
            m = importlib.import_module(mod)
            router = getattr(m, "router", None)
            if router is not None:
                app.include_router(router, prefix=prefix)
                print(f"✓ Mounted {module_name} at {prefix}")
                return True
        except Exception as e:
            # Comment the next line if you prefer silence
            print(f"… skip {mod} ({e})")
    return False

# mount the ones the frontend needs
_include("library")            # /api/library/...
_include("profile")            # /api/profile/...
_include("beans_frontend")     # /api/beans/...
_include("gear_frontend")      # /api/gear/...
_include("sessions_frontend")  # /api/sessions/...
_include("feedback")           # /api/feedback/...
_include("ocr_frontend")       # /api/ocr/...
_include("voice")
_include("nlp")
_include("brew")



try:
    from app.routers import brew as _brew
except Exception:
    try:
        from breau_backend.app.routers import brew as _brew
    except Exception:
        _brew = None

if _brew is not None:
    app.include_router(_brew.router, prefix="/api")
    print(" Explicitly mounted brew at /api")

# --- Small fallbacks / health ------------------------------------------------
@app.get("/api/ocr/warmup")
async def ocr_warmup():
    # harmless if your ocr router also defines this; the first included wins
    return {"ok": True}

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/api/history/local")
async def history_local(limit: int = 5):
    """
    Optional stub so the frontend 'local history peek' doesn't 404.
    Return an empty list for now.
    """
    return {"data": []}

# Print final routes for sanity check
@app.on_event("startup")
async def _print_routes():
    try:
        from fastapi.routing import APIRoute
        print("\n-- Routes mounted --")
        for r in app.router.routes:
            if isinstance(r, APIRoute):
                methods = ",".join(sorted(r.methods))
                print(f"{methods:10s} {r.path}")
        print("-- End routes --\n")
    except Exception:
        pass

# --- Small fallbacks / health ------------------------------------------------
@app.get("/api/health")
async def api_health():
    # mirror the non-prefixed /health so the FE's /api/health succeeds
    return {"ok": True}

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/api/profile/local")
async def profile_local():
    """
    Minimal stub used by the /profile page in dev.
    Shape is kept as { data: { ... } } to match the FE hook expectations.
    """
    return {
        "data": {
            "userId": "local-dev",
            "display_name": "Local Dev",
            "email": "local@example.com",
            # add more fields if your UI shows them:
            "preferences": {},
        }
    }

@app.get("/api/history/local")
async def history_local(limit: int = 5):
    """
    Optional stub so the frontend 'local history peek' doesn't 404.
    Return an empty list for now.
    """
    return {"data": []}
