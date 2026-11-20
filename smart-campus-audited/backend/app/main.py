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
from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.util import get_remote_address  # noqa: E402

from app.api.v1 import api_router  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.exceptions import add_exception_handlers  # noqa: E402
from app.middleware.csrf import CSRFMiddleware  # noqa: E402
from app.middleware.security import RequestIdMiddleware, SecurityHeadersMiddleware  # noqa: E402

log = logging.getLogger("smartcampus")
# Apply the configured log level (env-driven) after basicConfig.
log.setLevel(getattr(logging, settings.app_log_level.upper(), logging.INFO))

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.default_rate_limit])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Optional demo seeding (only when explicitly enabled).
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
    # rooted under /assets). Any /api, /health, /docs, /openapi.json, /redoc
    # path that is NOT a registered route falls through to FastAPI's JSON 404
    # envelope instead of being masked as index.html — which is essential for
    # the frontend to distinguish a genuine API miss from the SPA shell.
    dist = Path(os.environ.get("FRONTEND_DIST_DIR", settings.frontend_dist_dir))
    _API_RESERVED = ("api/", "health", "docs", "openapi.json", "redoc", "assets/")

    if dist.exists() and (dist / "index.html").exists():
        assets_dir = dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False, tags=["meta"])
        async def spa_fallback(full_path: str):
            # Never let the SPA shell answer reserved/API paths — those must
            # produce a real JSON error so the client's API layer sees it.
            if full_path == "" or full_path.endswith("/"):
                return FileResponse(str(dist / "index.html"))
            if full_path.startswith(_API_RESERVED):
                raise HTTPException(status_code=404, detail="Not Found")
            candidate = dist / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            # Unknown non-API path -> SPA shell (client router handles it).
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
