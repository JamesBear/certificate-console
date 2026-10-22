"""Application factory."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import router as auth_router
from .certs.router import router as cert_router
from .db import Databases
from .errors import install_error_handlers, not_found

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data"
FRONTEND_DIST = ROOT / "frontend" / "dist"


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Certificate Console", docs_url="/api/docs", redoc_url=None)
    app.state.databases = Databases(data_dir or os.environ.get("CERT_CONSOLE_DATA", DEFAULT_DATA))

    install_error_handlers(app)

    @app.get("/api/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(cert_router)

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            root = FRONTEND_DIST.resolve()
            candidate = (root / path).resolve()
            if not candidate.is_relative_to(root):
                raise not_found("Page")
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
