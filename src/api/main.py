"""FastAPI application for Art Lounge Stock Intelligence."""
import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api.database import get_db

logger = logging.getLogger(__name__)

app = FastAPI(title="Art Lounge Stock Intelligence", version="1.0.0")


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# CORS for local React dev server and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://artlounge-reorder-production.up.railway.app",
        os.environ.get("CORS_ORIGIN", ""),
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression — SKU list responses compress ~85% (150KB → 15KB)
app.add_middleware(GZipMiddleware, minimum_size=500)

# Rate limiting for login endpoint
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many login attempts. Try again in a minute."})


# Import and register route modules
from api.routes import brands, skus, po, parties, sync_status, suppliers, overrides, settings, auth_routes, users, search
from api.routes.channel_rules import router as channel_rules_router

app.include_router(brands.router, prefix="/api")
app.include_router(skus.router, prefix="/api")
app.include_router(po.router, prefix="/api")
app.include_router(parties.router, prefix="/api")
app.include_router(sync_status.router, prefix="/api")
app.include_router(suppliers.router, prefix="/api")
app.include_router(overrides.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(auth_routes.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(channel_rules_router, prefix="/api")


# Global exception handler — hide tracebacks from clients
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
def health():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"status": "ok"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "detail": "Database unreachable"})


# Serve React static build (production)
build_dir = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")
if os.path.exists(build_dir):
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(build_dir, "assets")), name="assets")

    # SPA catch-all: serve index.html for all non-API routes
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file_path = os.path.join(build_dir, full_path)
        # Prevent path traversal
        resolved = os.path.realpath(file_path)
        if not resolved.startswith(os.path.realpath(build_dir)):
            return FileResponse(os.path.join(build_dir, "index.html"))
        # Try to serve the exact file first (e.g. favicon.ico, vite.svg)
        if full_path and os.path.isfile(resolved):
            return FileResponse(resolved)
        # Otherwise serve index.html for SPA routing
        return FileResponse(os.path.join(build_dir, "index.html"))
