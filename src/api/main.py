"""FastAPI application for Art Lounge Stock Intelligence."""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="Art Lounge Stock Intelligence", version="1.0.0")

# CORS for local React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register route modules
from api.routes import brands, skus, po, parties, sync_status, suppliers, overrides, settings

app.include_router(brands.router, prefix="/api")
app.include_router(skus.router, prefix="/api")
app.include_router(po.router, prefix="/api")
app.include_router(parties.router, prefix="/api")
app.include_router(sync_status.router, prefix="/api")
app.include_router(suppliers.router, prefix="/api")
app.include_router(overrides.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve React static build (production)
build_dir = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")
if os.path.exists(build_dir):
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(build_dir, "assets")), name="assets")

    # SPA catch-all: serve index.html for all non-API routes
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        # Try to serve the exact file first (e.g. favicon.ico, vite.svg)
        file_path = os.path.join(build_dir, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        return FileResponse(os.path.join(build_dir, "index.html"))
