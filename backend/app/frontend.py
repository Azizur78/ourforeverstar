"""Optional single-service hosting: serve the built React app (frontend/dist) from FastAPI.

Everything outside /api is served from the dist folder; unknown paths fall back to index.html so client-side
routes (/verify, /registry/..., /admin) work on refresh. This keeps site and API on one origin, which the
SameSite session cookies require.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

# Minimal container images ship without a font MIME table; register the web-font types explicitly.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")


def mount_frontend(app: FastAPI, dist: Path, noindex: bool) -> None:
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise RuntimeError(f"FRONTEND_DIST is set but {index} does not exist. Run 'npm run build' first.")
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "Not found.")
        if noindex and full_path == "robots.txt":
            return PlainTextResponse("User-agent: *\nDisallow: /\n")
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
