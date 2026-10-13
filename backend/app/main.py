"""Forever Star API entry point.  Run:  uvicorn app.main:app --reload"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, load_settings
from .database.connection import init_db
from .frontend import mount_frontend
from .routes import admin, public, recovery
from .services.storage import build_storage
from .services.crypto import CodeVault
from .services.email import build_email_sender
from .services.rate_limit import RateLimiter
from .services.staging_seed import apply_staging_seed

log = logging.getLogger("forever_star")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    docs = None if settings.is_production else "/api/docs"
    app = FastAPI(title="Forever Star API", docs_url=docs, redoc_url=None, openapi_url=None if docs is None else "/api/openapi.json")

    init_db(settings.database_path)
    app.state.settings = settings
    app.state.vault = CodeVault(settings.secret_key)
    app.state.storage = build_storage(settings)
    app.state.email_sender = build_email_sender(settings)                       # None until SMTP is configured
    app.state.recovery_limiter = RateLimiter(max_attempts=5, window_seconds=60 * 60)  # form submissions / IP
    app.state.contact_email_limiter = RateLimiter(max_attempts=10, window_seconds=60 * 60)  # recovery-email saves / IP
    app.state.download_limiter = RateLimiter(max_attempts=30, window_seconds=5 * 60)  # document requests / IP
    app.state.verify_limiter = RateLimiter(max_attempts=10, window_seconds=15 * 60)  # failed attempts / IP
    app.state.password_limiter = RateLimiter(max_attempts=5, window_seconds=15 * 60)  # wrong current password
    app.state.login_limiter = RateLimiter(max_attempts=5, window_seconds=15 * 60)

    apply_staging_seed(settings, app.state.vault, app.state.storage)  # no-op unless a staging seed is configured

    if not settings.admin_password_hash:
        log.warning("ADMIN_PASSWORD_HASH is not set: admin login is disabled.")

    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        elif request.url.path.startswith("/assets/"):
            response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")  # content-hashed files
        if settings.noindex:
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        detail = exc.detail
        body = detail if isinstance(detail, dict) else {"message": detail}
        return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][-1]),
                "message": str(e["msg"]).removeprefix("Value error, "),
            }
            for e in exc.errors()
        ]
        return JSONResponse({"message": "Please correct the highlighted fields.", "errors": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"message": "Something went wrong. Please try again."}, status_code=500)

    @app.get("/api/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    app.include_router(public.router)
    app.include_router(recovery.public_router)
    app.include_router(recovery.router)
    app.include_router(admin.public_router)
    app.include_router(admin.router)
    if settings.frontend_dist:
        mount_frontend(app, settings.frontend_dist, settings.noindex)  # must stay last: it owns the catch-all route
    return app


app = create_app()
