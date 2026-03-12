# T14: FastAPI App Skeleton + DB Connection

## Prerequisites
- T04 (database schema exists)
- T01 (config/settings.py exists)

## Objective
Set up the FastAPI application skeleton with database connection pooling, CORS, and static file serving for the React build.

## Files to Create

### 1. `api/main.py`

```python
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
from api.routes import brands, skus, po, parties, sync_status, suppliers
app.include_router(brands.router, prefix="/api")
app.include_router(skus.router, prefix="/api")
app.include_router(po.router, prefix="/api")
app.include_router(parties.router, prefix="/api")
app.include_router(sync_status.router, prefix="/api")
app.include_router(suppliers.router, prefix="/api")

# Serve React static build (production)
build_dir = os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'dist')
if os.path.exists(build_dir):
    app.mount("/", StaticFiles(directory=build_dir, html=True), name="static")
```

### 2. `api/database.py`

Database connection management:
```python
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config.settings import DATABASE_URL

@contextmanager
def get_db():
    """Get a database connection with RealDictCursor (returns dicts not tuples)."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()
```

### 3. `api/routes/__init__.py`
Empty file.

### 4. Stub route files (one per module):

Create these as stubs with empty routers — they'll be implemented in T15 and T16:

- `api/routes/brands.py` — `router = APIRouter()`
- `api/routes/skus.py` — `router = APIRouter()`
- `api/routes/po.py` — `router = APIRouter()`
- `api/routes/parties.py` — `router = APIRouter()`
- `api/routes/sync_status.py` — `router = APIRouter()`
- `api/routes/suppliers.py` — `router = APIRouter()`

Each stub:
```python
from fastapi import APIRouter
router = APIRouter()
```

### 5. `Procfile` (project root)
```
web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

## Running locally
```bash
uvicorn api.main:app --reload --port 8000
```

## Acceptance Criteria
- [ ] `uvicorn api.main:app --reload` starts without errors
- [ ] CORS configured for localhost:3000 and localhost:5173 (Vite)
- [ ] All route stubs imported without error
- [ ] `get_db()` context manager returns dict-cursor connections
- [ ] Static file serving configured for production React build
- [ ] Procfile uses $PORT env var for Railway
