# breau_backend/app/services/serve_frontend.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
import os
from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                # SPA fallback: always return index.html for client routes
                return await super().get_response("index.html", scope)
            raise

def _default_dist_dir() -> Path:
    # main.py is at breau_backend/app/main.py → repo root is parents[2]
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    return repo_root / "breau_frontend" / "app" / "dist"

def mount_frontend(app: FastAPI, dist_dir: Optional[Path] = None) -> None:
    dist = Path(dist_dir or os.getenv("FRONTEND_DIST", _default_dist_dir())).resolve()
    if not dist.exists():
        print(f"[frontend] dist not found, skipping mount: {dist}")
        return
    print(f"[frontend] mounting SPA from: {dist}")
    app.mount("/", SPAStaticFiles(directory=str(dist), html=True), name="spa")
