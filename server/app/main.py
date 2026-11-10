import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config import Settings
from .db import init_db
from .metrics import HTTP_REQUESTS, HTTP_SECONDS
from .routes import admin, auth, portfolio
from .storage import SiteStorage
from .storage.local import LocalStorage

log = logging.getLogger("portfolive")
CLIENT_DIST = Path(__file__).resolve().parent.parent / "public"  # built React app (Docker copies it here)


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
# The app itself: only same-origin scripts/styles (React bundle). Inline styles are needed by the live preview.
CSP_APP = ("default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; "
           "base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
# Generated portfolio pages (user content): no scripts at all, inline CSS only. Defence in depth on top of escaping.
CSP_SITE = ("default-src 'none'; style-src 'unsafe-inline'; img-src https: data:; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
DOC_PATHS = ("/docs", "/redoc")  # Swagger UI loads assets from a CDN, so it is exempt from the CSP


def build_storage(s: Settings) -> SiteStorage:
    if s.storage == "s3":
        from .storage.s3 import S3Storage
        return S3Storage(s.s3_bucket, s.cloudfront_distribution_id, s.cloudfront_url, s.aws_region)
    return LocalStorage(s.sites_dir, s.public_base_url or f"http://localhost:{s.port}")


def create_app(settings: Settings | None = None, storage: SiteStorage | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    init_db(settings.db_path)

    # Swagger/ReDoc UIs are disabled in production; the OpenAPI spec stays available (used by the ZAP API scan).
    app = FastAPI(
        title="PortfoLive API", version="1.0.0",
        docs_url=None if settings.production else "/docs",
        redoc_url=None if settings.production else "/redoc",
    )
    app.state.settings = settings
    app.state.storage = storage or build_storage(settings)

    @app.middleware("http")
    async def observe_and_harden(request: Request, call_next):
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            route = request.scope.get("route")
            label = getattr(route, "path", "unmatched")  # route template, so label cardinality stays low
            if request.url.path != "/metrics":
                HTTP_REQUESTS.labels(request.method, label, str(status)).inc()
                HTTP_SECONDS.labels(label).observe(time.perf_counter() - started)
        path = request.url.path
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        if path.startswith("/sites/"):
            response.headers["Content-Security-Policy"] = CSP_SITE
        elif not path.startswith(DOC_PATHS):
            response.headers["Content-Security-Policy"] = CSP_APP
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # Keep the same {"error": "..."} shape the React client already reads.
    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0]
        msg = first.get("msg", "Invalid input").removeprefix("Value error, ")
        return JSONResponse({"error": msg}, status_code=400)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error", exc_info=exc)
        return JSONResponse({"error": "Internal server error"}, status_code=500)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    for r in (auth.router, portfolio.router, admin.router):
        app.include_router(r)

    if app.state.storage.name == "local":
        settings.sites_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/sites", StaticFiles(directory=settings.sites_dir, html=True), name="sites")

    if CLIENT_DIST.exists():
        app.mount("/assets", StaticFiles(directory=CLIENT_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):  # React single-page-app fallback
            if path.startswith(("api/", "sites/")):
                raise HTTPException(404, "Not found")
            return FileResponse(CLIENT_DIST / "index.html")

    return app
