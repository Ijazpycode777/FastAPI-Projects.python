"""FastAPI application factory and lifespan.

Wires:
  * CORS (configured origins only)
  * CSRF double-submit cookie middleware
  * rate limiting (slowapi)
  * request-id + security headers
  * structured exception handlers
  * /api/v1 router
  * /health endpoint
  * static frontend serving (production single-origin)
  * optional demo data seeding on startup
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Uvicorn installs its own handlers; let app records flow through one formatter.
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access", "smartcampus"):
    _lg = logging.getLogger(_name)
    _lg.handlers = [h for h in _lg.handlers if False]
    _lg.propagate = True

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402

from app.api.v1 import api_router  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.exceptions import add_exception_handlers  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.middleware.csrf import CSRFMiddleware  # noqa: E402
from app.middleware.security import RequestIdMiddleware, SecurityHeadersMiddleware  # noqa: E402

log = logging.getLogger("smartcampus")
# Apply the configured log level (env-driven) after basicConfig.
log.setLevel(getattr(logging, settings.app_log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Always ensure a usable administrator exists — including in production,
    # where demo seeding is disabled. This is the documented first-admin
    # bootstrap: it creates the admin from SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD
    # only if missing, never resets an existing admin's password, and never
    # logs the password. A deployment may not start without a usable admin.
    from app.seed import bootstrap_admin

    try:
        admin_ok = await bootstrap_admin()
    except Exception:  # noqa: BLE001
        log.exception("Administrator bootstrap failed.")
        raise
    if not admin_ok:
        raise RuntimeError("No usable administrator account after bootstrap; refusing to start.")
    log.info("Administrator account verified.")

    # Demo data is development/staging only and never touches production.
    if settings.seed_reset_on_start and settings.app_env != "production":
        try:
            from app.seed import seed_demo_data

            await seed_demo_data()
            log.info("Demo data seeding complete.")
        except Exception:  # noqa: BLE001
            # Full traceback so startup failures are visible. The advisory lock
            # inside seed_demo_data handles the "another worker is seeding" case
            # (logged at INFO); only genuine errors reach here.
            log.exception("Demo data seeding failed.")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Campus",
        description="College management system — students, teachers, attendance, "
                    "examinations, fees, materials and more.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Order matters: outermost first.
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origin_set()),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Rate limiting state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    add_exception_handlers(app)

    # API
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Health
    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok", "app": settings.app_name, "env": settings.app_env}

    # Serve the built frontend (single-origin production deployment).
    # API routes are registered above, so they always take precedence over the
    # SPA fallback below. The catch-all serves index.html for non-API GETs
    # (client-side routing) and a real file when one exists (favicon, assets
    # rooted under /assets). Reserved/API paths — including trailing-slash
    # variants like /api/v1/unknown/ and /health/ — always return a JSON 404
    # rather than the SPA shell, so the client's API layer sees a real miss.
    dist = Path(os.environ.get("FRONTEND_DIST_DIR", settings.frontend_dist_dir)).resolve()
    # Path prefixes that must NEVER be answered with the SPA shell. Checked
    # against the raw path BEFORE any trailing-slash handling, so /api/v1/x/
    # and /health/ are rejected as JSON 404 rather than served index.html.
    _RESERVED_PREFIXES = ("api", "health", "docs", "openapi", "redoc")

    if dist.exists() and (dist / "index.html").exists():
        assets_dir = dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False, tags=["meta"])
        async def spa_fallback(full_path: str):
            # 1. Reserved/API prefixes always JSON 404 — checked FIRST, before
            #    trailing-slash handling, so /api/v1/unknown/ and /health/ never
            #    return the shell. (Bare /api, /health etc. are registered routes
            #    handled above; this catches sub-paths and trailing-slash forms.)
            if any(full_path.startswith(p) for p in _RESERVED_PREFIXES):
                raise HTTPException(status_code=404, detail="Not Found")
            # 2. Root or a directory-style path (trailing slash) -> SPA shell.
            if full_path == "" or full_path.endswith("/"):
                return FileResponse(str(dist / "index.html"))
            # 3. Static file: resolve and VERIFY the resolved path stays inside
            #    the dist directory. This rejects path traversal (including
            #    encoded attempts — Starlette URL-decodes the path before
            #    matching, so %2e%2e%2f arrives as ../). Anything that resolves
            #    outside dist is a 404, never a file from elsewhere on disk.
            candidate = (dist / full_path).resolve()
            try:
                candidate.relative_to(dist)
            except ValueError:
                raise HTTPException(status_code=404, detail="Not Found")
            if candidate.is_file():
                return FileResponse(str(candidate))
            # 4. A missing asset is a real 404 — never advertise the SPA shell
            #    for a file the client expects to exist.
            if full_path.startswith("assets/"):
                raise HTTPException(status_code=404, detail="Not Found")
            # 5. Unknown non-API path -> SPA shell (client router handles it).
            return FileResponse(str(dist / "index.html"))

        log.info("Serving frontend from %s", dist)
    else:
        @app.get("/", tags=["meta"])
        async def root():
            return {
                "name": settings.app_name,
                "docs": "/docs",
                "frontend": "not built — run `npm run build` in frontend/ and restart",
            }

    return app


app = create_app()
