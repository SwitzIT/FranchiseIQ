"""
FranchiseIQ — FastAPI Application Entry Point
"""
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import APP_TITLE, APP_VERSION, CORS_ORIGINS
from app.services.session_store import purge_expired
from app.utils import get_logger
from app.routes import all_routers
from app.db.database import init_db

log = get_logger("main")


def _background_cleanup():
    """Purge expired sessions every 10 minutes."""
    while True:
        time.sleep(600)
        purge_expired()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"🚀 {APP_TITLE} v{APP_VERSION} starting up")
    # v6.4 — loud, unmissable warning if the JWT secret was never changed
    # from the insecure development default. Anyone who has this string
    # (it's in the public repo/README) could forge valid login tokens.
    if os.getenv("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me") == "dev-only-insecure-secret-change-me":
        log.warning(
            "⚠️  JWT_SECRET_KEY is still the insecure default from .env.example! "
            "Anyone who has seen this codebase can forge valid login tokens. "
            "Set a real random secret in .env before exposing this beyond localhost: "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    init_db()
    log.info("✅ Database tables ready")
    t = threading.Thread(target=_background_cleanup, daemon=True)
    t.start()
    yield
    log.info(f"👋 {APP_TITLE} shutting down")


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="Production-grade Franchise Location Intelligence API",
    lifespan=lifespan,
)


# ✅ CORS — v6.4: uses the configurable CORS_ORIGINS from config.py (env
# var override via CORS_ORIGINS) instead of a hardcoded list. The old list
# included a "*" wildcard alongside specific origins, which made the
# specific entries pointless (a wildcard matches everything anyway) — too
# permissive for a login-gated app. Add your real deployed frontend URL(s)
# via the CORS_ORIGINS env var, comma-separated.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ✅ REGISTER ROUTES
for router in all_routers:
    app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_TITLE, "version": APP_VERSION}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    log.exception(f"Unhandled: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )
