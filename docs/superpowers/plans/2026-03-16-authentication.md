# Authentication System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-user authentication with role-based permissions (admin/purchaser/viewer) to the Art Lounge Stock Intelligence dashboard.

**Architecture:** Stateless JWT auth with Argon2id password hashing. Backend auth dependency injected into FastAPI routes. Frontend uses React Context + ProtectedRoute wrapper with axios interceptor for token attachment. Three initial admin users seeded via migration.

**Tech Stack:** PyJWT, pwdlib[argon2], slowapi (Python). axios interceptors, React Context (TypeScript). Existing PostgreSQL database.

---

## File Structure

### New files to create

```
src/
  api/
    auth.py                          # Password hashing, JWT encode/decode, get_current_user + require_role dependencies
    routes/
      auth_routes.py                 # POST /login, GET /me, PUT /change-password
      users.py                       # GET/POST/PUT users, PUT reset-password (admin-only)
  db/
    migrations/
      010_users_table.sql            # CREATE TABLE users + seed 3 admin users
  dashboard/
    src/
      contexts/
        AuthContext.tsx               # React auth provider: user state, login(), logout(), useAuth()
      components/
        ProtectedRoute.tsx            # Redirects to /login if not authenticated
      pages/
        Login.tsx                     # Login form page
        Users.tsx                     # User management page (admin-only)
```

### Existing files to modify

```
src/
  requirements.txt                   # Add PyJWT, pwdlib[argon2], slowapi
  config/settings.py                 # Add JWT_SECRET, JWT_EXPIRY_HOURS
  api/
    main.py                          # Register auth + users routers, add rate limiting
    routes/
      brands.py                      # Add Depends(get_current_user) to all routes
      skus.py                        # Add Depends(get_current_user) to all routes
      po.py                          # Add Depends(require_role("purchaser"))
      parties.py                     # Add Depends(require_role("purchaser")) on classify
      suppliers.py                   # Add Depends(require_role("admin"))
      settings.py                    # Add Depends(require_role("admin"))
      overrides.py                   # Add Depends(require_role("purchaser"))
      sync_status.py                 # Add Depends(get_current_user)
  dashboard/
    src/
      App.tsx                        # Add AuthProvider, /login route, ProtectedRoute wrapper
      lib/
        api.ts                       # Add axios interceptor for Bearer token + 401 handling
        types.ts                     # Add User, AuthResponse types
      components/
        Layout.tsx                   # Add user menu (top-right), role-based nav visibility
```

---

## Chunk 1: Backend Auth Infrastructure

### Task 1: Install Python dependencies

**Files:**
- Modify: `src/requirements.txt`

- [ ] **Step 1: Add auth dependencies**

Append to `src/requirements.txt`:
```
PyJWT==2.10.1
pwdlib[argon2]==0.3.0
slowapi==0.1.9
```

- [ ] **Step 2: Install**

Run: `cd src && ./venv/Scripts/pip install -r requirements.txt`
Expected: Successfully installed PyJWT, pwdlib, slowapi, argon2-cffi

- [ ] **Step 3: Commit**

```bash
git add src/requirements.txt
git commit -m "chore: add PyJWT, pwdlib, slowapi auth dependencies"
```

---

### Task 2: Add JWT settings

**Files:**
- Modify: `src/config/settings.py`

- [ ] **Step 1: Add JWT config to settings.py**

Add after the SMTP settings block:

```python
# Auth / JWT
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
```

- [ ] **Step 2: Commit**

```bash
git add src/config/settings.py
git commit -m "feat: add JWT_SECRET and JWT_EXPIRY_HOURS to settings"
```

---

### Task 3: Create auth module

**Files:**
- Create: `src/api/auth.py`
- Test: `src/tests/test_auth.py`

- [ ] **Step 1: Write tests for password hashing and JWT**

Create `src/tests/test_auth.py`:

```python
"""Tests for auth module: password hashing, JWT, dependencies."""
import time
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from api.auth import (
    hash_password,
    verify_password,
    create_token,
    decode_token,
    get_current_user,
    require_role,
)


class TestPasswordHashing:
    def test_hash_produces_argon2_string(self):
        h = hash_password("testpass123")
        assert h.startswith("$argon2id$")

    def test_verify_correct_password(self):
        h = hash_password("hello")
        assert verify_password("hello", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("hello")
        assert verify_password("wrong", h) is False

    def test_different_passwords_different_hashes(self):
        h1 = hash_password("pass1")
        h2 = hash_password("pass2")
        assert h1 != h2

    def test_same_password_different_hashes_due_to_salt(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # Different salt each time


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_token(user_id=1, username="kshitij", role="admin")
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert payload["username"] == "kshitij"
        assert payload["role"] == "admin"

    def test_expired_token_raises(self):
        with patch("api.auth.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-secret"
            mock_settings.JWT_EXPIRY_HOURS = 0  # Expire immediately
            import jwt as pyjwt
            from datetime import datetime, timezone, timedelta
            token = pyjwt.encode(
                {
                    "sub": "1",
                    "username": "test",
                    "role": "viewer",
                    "exp": datetime.now(timezone.utc) - timedelta(seconds=10),
                },
                "test-secret",
                algorithm="HS256",
            )
        # decode_token uses the real settings, so patch it
        with patch("api.auth.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-secret"
            with pytest.raises(HTTPException) as exc:
                decode_token(token)
            assert exc.value.status_code == 401

    def test_tampered_token_raises(self):
        token = create_token(user_id=1, username="test", role="viewer")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(HTTPException):
            decode_token(tampered)


class TestRequireRole:
    def test_admin_can_access_admin_route(self):
        user = {"id": 1, "username": "k", "role": "admin"}
        dep = require_role("admin")
        result = dep(user)
        assert result == user

    def test_purchaser_can_access_purchaser_route(self):
        user = {"id": 2, "username": "p", "role": "purchaser"}
        dep = require_role("purchaser")
        result = dep(user)
        assert result == user

    def test_admin_can_access_purchaser_route(self):
        user = {"id": 1, "username": "k", "role": "admin"}
        dep = require_role("purchaser")
        result = dep(user)
        assert result == user

    def test_viewer_cannot_access_purchaser_route(self):
        user = {"id": 3, "username": "v", "role": "viewer"}
        dep = require_role("purchaser")
        with pytest.raises(HTTPException) as exc:
            dep(user)
        assert exc.value.status_code == 403

    def test_viewer_cannot_access_admin_route(self):
        user = {"id": 3, "username": "v", "role": "viewer"}
        dep = require_role("admin")
        with pytest.raises(HTTPException) as exc:
            dep(user)
        assert exc.value.status_code == 403

    def test_purchaser_cannot_access_admin_route(self):
        user = {"id": 2, "username": "p", "role": "purchaser"}
        dep = require_role("admin")
        with pytest.raises(HTTPException) as exc:
            dep(user)
        assert exc.value.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_auth.py -v`
Expected: FAIL — `api.auth` module does not exist

- [ ] **Step 3: Implement auth module**

Create `src/api/auth.py`:

```python
"""Authentication: password hashing, JWT tokens, FastAPI dependencies."""
from datetime import datetime, timezone, timedelta

import jwt as pyjwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException, Header

from config import settings

_hasher = PasswordHash.recommended()

ROLE_HIERARCHY = {"admin": 3, "purchaser": 2, "viewer": 1}


# ── Password hashing ──

def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


# ── JWT ──

def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS),
    }
    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return pyjwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


# ── FastAPI Dependencies ──

def get_current_user(authorization: str = Header(None)) -> dict:
    """Extract and validate JWT from Authorization header.

    Returns dict with id, username, role.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    token = authorization[7:]  # Strip "Bearer "
    payload = decode_token(token)
    # Check user is still active in database
    from api.database import get_db
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, role, is_active FROM users WHERE id = %s",
                (int(payload["sub"]),),
            )
            user = cur.fetchone()
    if not user or not user["is_active"]:
        raise HTTPException(401, "User not found or deactivated")
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


def require_role(minimum_role: str):
    """Return a dependency that checks the user has at least `minimum_role`."""
    min_level = ROLE_HIERARCHY[minimum_role]

    def checker(user: dict = Depends(get_current_user)) -> dict:
        user_level = ROLE_HIERARCHY.get(user["role"], 0)
        if user_level < min_level:
            raise HTTPException(403, "Insufficient permissions")
        return user

    return checker
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_auth.py -v`
Expected: All tests PASS (the `get_current_user` tests are skipped here — they need a DB; the unit tests for hashing, JWT, and role checking should all pass)

- [ ] **Step 5: Commit**

```bash
git add src/api/auth.py src/tests/test_auth.py
git commit -m "feat: auth module with Argon2id hashing, JWT, role dependencies"
```

---

### Task 4: Database migration — users table + seed users

**Files:**
- Create: `src/db/migrations/010_users_table.sql`

- [ ] **Step 1: Generate password hashes for the three initial users**

Run:
```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -c "from api.auth import hash_password; print(hash_password('Admin@2026'))"
```

Run this 3 times to get 3 distinct hashes (one per user). Save the outputs — each will look like `$argon2id$v=19$m=...`.

- [ ] **Step 2: Create the migration file**

Create `src/db/migrations/010_users_table.sql`:

```sql
-- 010: Users table for authentication
BEGIN;

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'viewer'
                  CHECK (role IN ('admin', 'purchaser', 'viewer')),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login    TIMESTAMPTZ
);

-- Seed initial admin users (password: Admin@2026 — hashed with Argon2id)
INSERT INTO users (username, password_hash, role) VALUES
    ('kshitij', '<HASH_1>', 'admin'),
    ('yash',    '<HASH_2>', 'admin'),
    ('sonali',  '<HASH_3>', 'admin')
ON CONFLICT (username) DO NOTHING;

COMMIT;
```

Replace `<HASH_1>`, `<HASH_2>`, `<HASH_3>` with the actual hashes from Step 1.

- [ ] **Step 3: Run the migration locally**

Run:
```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -f src/db/migrations/010_users_table.sql
```
Expected: `CREATE TABLE`, `INSERT 0 3`

- [ ] **Step 4: Verify users were created**

Run:
```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "SELECT id, username, role, is_active FROM users"
```
Expected: 3 rows — kshitij, yash, sonali, all admin, all active

- [ ] **Step 5: Commit**

```bash
git add src/db/migrations/010_users_table.sql
git commit -m "feat: users table migration with 3 initial admin users"
```

---

### Task 5: Auth API routes (login, me, change-password)

**Files:**
- Create: `src/api/routes/auth_routes.py`

- [ ] **Step 1: Create auth routes**

Create `src/api/routes/auth_routes.py`:

```python
"""Authentication API routes: login, me, change-password."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import verify_password, hash_password, create_token, get_current_user
from api.database import get_db

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/login")
def login(req: LoginRequest):
    """Authenticate and return JWT token."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, role, is_active FROM users WHERE username = %s",
                (req.username,),
            )
            user = cur.fetchone()

    # Always hash even if user not found (timing attack prevention)
    if not user:
        hash_password("dummy")  # constant-time regardless of user existence
        raise HTTPException(401, "Invalid credentials")

    if not user["is_active"]:
        raise HTTPException(401, "Invalid credentials")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    # Update last_login
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login = %s WHERE id = %s",
                (datetime.now(timezone.utc), user["id"]),
            )
        conn.commit()

    token = create_token(user["id"], user["username"], user["role"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
        },
    }


@router.get("/auth/me")
def get_me(user: dict = Depends(get_current_user)):
    """Return current authenticated user."""
    return user


@router.put("/auth/change-password")
def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Change own password. Requires current password."""
    if len(req.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
            row = cur.fetchone()

        if not verify_password(req.current_password, row["password_hash"]):
            raise HTTPException(401, "Current password is incorrect")

        new_hash = hash_password(req.new_password)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (new_hash, user["id"]),
            )
        conn.commit()

    return {"message": "Password changed successfully"}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/routes/auth_routes.py
git commit -m "feat: auth API routes — login, me, change-password"
```

---

### Task 6: User management API routes (admin-only)

**Files:**
- Create: `src/api/routes/users.py`

- [ ] **Step 1: Create user management routes**

Create `src/api/routes/users.py`:

```python
"""User management API routes (admin only)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import hash_password, require_role
from api.database import get_db

router = APIRouter(tags=["users"])

_admin = require_role("admin")


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class ResetPassword(BaseModel):
    new_password: str


@router.get("/users")
def list_users(user: dict = Depends(_admin)):
    """List all users (admin only)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, role, is_active, created_at, last_login "
                "FROM users ORDER BY created_at"
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/users", status_code=201)
def create_user(req: UserCreate, user: dict = Depends(_admin)):
    """Create a new user (admin only)."""
    if req.role not in ("admin", "purchaser", "viewer"):
        raise HTTPException(400, "Role must be admin, purchaser, or viewer")
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if len(req.username) < 2:
        raise HTTPException(400, "Username must be at least 2 characters")

    pw_hash = hash_password(req.password)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE username = %s", (req.username,)
            )
            if cur.fetchone():
                raise HTTPException(409, "Username already exists")
            cur.execute(
                "INSERT INTO users (username, password_hash, role) "
                "VALUES (%s, %s, %s) RETURNING id, username, role, is_active, created_at",
                (req.username, pw_hash, req.role),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row)


@router.put("/users/{user_id}")
def update_user(user_id: int, req: UserUpdate, user: dict = Depends(_admin)):
    """Update user role or active status (admin only)."""
    if req.role and req.role not in ("admin", "purchaser", "viewer"):
        raise HTTPException(400, "Role must be admin, purchaser, or viewer")

    # Prevent last admin from deactivating themselves
    if user_id == user["id"] and req.is_active is False:
        raise HTTPException(400, "Cannot deactivate your own account")

    updates, params = [], []
    if req.role is not None:
        updates.append("role = %s")
        params.append(req.role)
    if req.is_active is not None:
        updates.append("is_active = %s")
        params.append(req.is_active)

    if not updates:
        raise HTTPException(400, "Nothing to update")

    params.append(user_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = %s "
                "RETURNING id, username, role, is_active",
                params,
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "User not found")
        conn.commit()
    return dict(row)


@router.put("/users/{user_id}/reset-password")
def reset_password(user_id: int, req: ResetPassword, user: dict = Depends(_admin)):
    """Reset a user's password (admin only)."""
    if len(req.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    pw_hash = hash_password(req.new_password)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s RETURNING id",
                (pw_hash, user_id),
            )
            if not cur.fetchone():
                raise HTTPException(404, "User not found")
        conn.commit()
    return {"message": "Password reset successfully"}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/routes/users.py
git commit -m "feat: user management CRUD routes (admin-only)"
```

---

### Task 7: Register auth routers + rate limiting in main.py

**Files:**
- Modify: `src/api/main.py`

- [ ] **Step 1: Add rate limiting and auth routers**

In `src/api/main.py`, add imports at top:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
```

After the existing middleware setup, add:
```python
# Rate limiting for login endpoint
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many login attempts. Try again in a minute."})
```

In the router imports section, add:
```python
from api.routes import brands, skus, po, parties, sync_status, suppliers, overrides, settings, auth_routes, users
```

After the existing router registrations, add:
```python
app.include_router(auth_routes.router, prefix="/api")
app.include_router(users.router, prefix="/api")
```

In `auth_routes.py`, add the rate limit decorator to the login endpoint:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login")
@limiter.limit("5/minute")
def login(request: Request, req: LoginRequest):
```

Note: The `request: Request` parameter must be added for slowapi to work. It extracts the client IP.

- [ ] **Step 2: Test login endpoint manually**

Run the API server:
```bash
cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000
```

Test login:
```bash
curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"kshitij","password":"Admin@2026"}'
```
Expected: `{"token":"eyJ...","user":{"id":1,"username":"kshitij","role":"admin"}}`

Test wrong password:
```bash
curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"kshitij","password":"wrong"}'
```
Expected: `{"detail":"Invalid credentials"}`

Test /me with token:
```bash
curl http://localhost:8000/api/auth/me -H "Authorization: Bearer <token-from-above>"
```
Expected: `{"id":1,"username":"kshitij","role":"admin"}`

- [ ] **Step 3: Commit**

```bash
git add src/api/main.py src/api/routes/auth_routes.py
git commit -m "feat: register auth routers with rate limiting on login"
```

---

## Chunk 2: Protect Existing API Routes

### Task 8: Add auth dependencies to all existing routes

**Files:**
- Modify: `src/api/routes/brands.py`
- Modify: `src/api/routes/skus.py`
- Modify: `src/api/routes/po.py`
- Modify: `src/api/routes/parties.py`
- Modify: `src/api/routes/suppliers.py`
- Modify: `src/api/routes/settings.py`
- Modify: `src/api/routes/overrides.py`
- Modify: `src/api/routes/sync_status.py`

- [ ] **Step 1: Add auth to read-only routes (brands, skus, sync_status)**

In each file, add import:
```python
from fastapi import Depends
from api.auth import get_current_user
```

Add `user: dict = Depends(get_current_user)` parameter to every route function. Example for brands.py:

```python
@router.get("/brands")
def list_brands(search: str = Query(None), user: dict = Depends(get_current_user)):
```

Do this for ALL route functions in `brands.py`, `skus.py`, and `sync_status.py`.

- [ ] **Step 2: Add purchaser role to write routes (po, parties, overrides)**

In `po.py`, `parties.py`, `overrides.py`, add import:
```python
from api.auth import get_current_user, require_role
```

For GET routes, use `Depends(get_current_user)`.
For POST/PUT/DELETE routes, use `Depends(require_role("purchaser"))`.

Example for `po.py`:
```python
@router.post("/po/export")
def export_po(..., user: dict = Depends(require_role("purchaser"))):
```

For `parties.py` — classify endpoint needs purchaser, list endpoint needs viewer:
```python
@router.get("/parties")
def list_parties(..., user: dict = Depends(get_current_user)):

@router.put("/parties/{party_name}/classify")
def classify_party(..., user: dict = Depends(require_role("purchaser"))):
```

- [ ] **Step 3: Add admin role to settings and suppliers**

In `settings.py` and `suppliers.py`, add import:
```python
from api.auth import get_current_user, require_role
```

For GET routes, use `Depends(get_current_user)`.
For PUT/POST/DELETE routes, use `Depends(require_role("admin"))`.

- [ ] **Step 4: Test that unauthenticated requests are rejected**

```bash
curl http://localhost:8000/api/brands
```
Expected: `{"detail":"Missing or invalid Authorization header"}` (401)

```bash
curl http://localhost:8000/api/brands -H "Authorization: Bearer <valid-token>"
```
Expected: 200 with brands data

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/
git commit -m "feat: protect all API routes with auth dependencies"
```

---

## Chunk 3: Frontend — Login, Auth Context, Protected Routes

### Task 9: Add TypeScript types for auth

**Files:**
- Modify: `src/dashboard/src/lib/types.ts`

- [ ] **Step 1: Add auth types**

Append to `src/dashboard/src/lib/types.ts`:

```typescript
export type UserRole = 'admin' | 'purchaser' | 'viewer'

export interface AuthUser {
  id: number
  username: string
  role: UserRole
}

export interface LoginResponse {
  token: string
  user: AuthUser
}
```

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/src/lib/types.ts
git commit -m "feat: add auth TypeScript types"
```

---

### Task 10: Add auth API functions + axios interceptor

**Files:**
- Modify: `src/dashboard/src/lib/api.ts`

- [ ] **Step 1: Add token interceptor and auth API functions**

At the top of `api.ts`, after the `axios.create()` call, add:

```typescript
// ── Auth token interceptor ──
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      // Redirect to login unless already there
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)
```

At the bottom of the file, add auth API functions:

```typescript
// ── Auth ──
import type { AuthUser, LoginResponse } from './types'

export const login = (username: string, password: string): Promise<LoginResponse> =>
  api.post('/api/auth/login', { username, password }).then(r => r.data)

export const fetchMe = (): Promise<AuthUser> =>
  api.get('/api/auth/me').then(r => r.data)

export const changePassword = (currentPassword: string, newPassword: string) =>
  api.put('/api/auth/change-password', { current_password: currentPassword, new_password: newPassword }).then(r => r.data)

// ── Users (admin) ──
export const fetchUsers = () =>
  api.get('/api/users').then(r => r.data)

export const createUser = (data: { username: string; password: string; role: string }) =>
  api.post('/api/users', data).then(r => r.data)

export const updateUser = (id: number, data: { role?: string; is_active?: boolean }) =>
  api.put(`/api/users/${id}`, data).then(r => r.data)

export const resetUserPassword = (id: number, newPassword: string) =>
  api.put(`/api/users/${id}/reset-password`, { new_password: newPassword }).then(r => r.data)
```

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/src/lib/api.ts
git commit -m "feat: axios auth interceptor + auth API functions"
```

---

### Task 11: Create AuthContext

**Files:**
- Create: `src/dashboard/src/contexts/AuthContext.tsx`

- [ ] **Step 1: Create auth context provider**

Create directory and file `src/dashboard/src/contexts/AuthContext.tsx`:

```tsx
import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'
import type { AuthUser } from '@/lib/types'
import { login as apiLogin, fetchMe } from '@/lib/api'

interface AuthContextType {
  user: AuthUser | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  // On mount: check for existing token
  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }
    fetchMe()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem('token')
      })
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiLogin(username, password)
    localStorage.setItem('token', res.token)
    setUser(res.user)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
```

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/src/contexts/AuthContext.tsx
git commit -m "feat: AuthContext provider with login/logout/token persistence"
```

---

### Task 12: Create ProtectedRoute + Login page

**Files:**
- Create: `src/dashboard/src/components/ProtectedRoute.tsx`
- Create: `src/dashboard/src/pages/Login.tsx`

- [ ] **Step 1: Create ProtectedRoute component**

Create `src/dashboard/src/components/ProtectedRoute.tsx`:

```tsx
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
```

- [ ] **Step 2: Create Login page**

Create `src/dashboard/src/pages/Login.tsx`:

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

export default function Login() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // If already logged in, redirect
  if (user) {
    navigate('/', { replace: true })
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold">Art Lounge</h1>
          <p className="text-sm text-muted-foreground">Stock Intelligence Dashboard</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="username" className="text-sm font-medium">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              required
              autoFocus
              autoComplete="username"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              required
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="flex w-full justify-center rounded-md bg-primary px-3 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/ProtectedRoute.tsx src/dashboard/src/pages/Login.tsx
git commit -m "feat: ProtectedRoute component and Login page"
```

---

### Task 13: Wire auth into App.tsx

**Files:**
- Modify: `src/dashboard/src/App.tsx`

- [ ] **Step 1: Update App.tsx**

Wrap the existing Router in `<AuthProvider>`. Add the `/login` route outside the `<ProtectedRoute>` wrapper. Wrap the `<Layout>` route inside `<ProtectedRoute>`.

Add imports:
```tsx
import { AuthProvider } from '@/contexts/AuthContext'
import ProtectedRoute from '@/components/ProtectedRoute'
const Login = lazy(() => import('./pages/Login'))
```

Change the Routes structure from:
```tsx
<Routes>
  <Route element={<Layout />}>
    ...all routes...
  </Route>
</Routes>
```

To:
```tsx
<AuthProvider>
  <Routes>
    <Route path="/login" element={<SuspenseWrapper><Login /></SuspenseWrapper>} />
    <Route element={<ProtectedRoute />}>
      <Route element={<Layout />}>
        ...all existing routes unchanged...
      </Route>
    </Route>
  </Routes>
</AuthProvider>
```

Move `<AuthProvider>` to wrap `<BrowserRouter>` if `QueryClientProvider` is outside. The key point: `<AuthProvider>` must be inside `<BrowserRouter>` (because `useNavigate` is used in Login) but wrap all routes.

- [ ] **Step 2: Test the login flow in browser**

1. Run the API: `cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000`
2. Run the frontend: `cd src/dashboard && npm run dev`
3. Open `http://localhost:5173` — should redirect to `/login`
4. Login as `kshitij` / `Admin@2026` — should redirect to dashboard
5. Refresh page — should stay logged in (token persisted)

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/App.tsx
git commit -m "feat: wire AuthProvider + ProtectedRoute into App"
```

---

## Chunk 4: User Menu + Role-Based UI + Users Page

### Task 14: Add user menu to Layout header

**Files:**
- Modify: `src/dashboard/src/components/Layout.tsx`

- [ ] **Step 1: Add user menu to header**

In `Layout.tsx`, import `useAuth`:
```tsx
import { useAuth } from '@/contexts/AuthContext'
```

Add `LogOut` and `UserCircle` to the lucide import.

Inside the component, get user and logout:
```tsx
const { user, logout } = useAuth()
```

In the header right side (next to HelpMenu), add a user menu:
```tsx
{user && (
  <div className="flex items-center gap-2 text-sm">
    <UserCircle className="h-4 w-4 text-muted-foreground" />
    <span className="font-medium">{user.username}</span>
    <span className="text-xs text-muted-foreground capitalize">({user.role})</span>
    <button
      onClick={logout}
      className="ml-1 p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      title="Sign out"
    >
      <LogOut className="h-4 w-4" />
    </button>
  </div>
)}
```

- [ ] **Step 2: Add role-based nav visibility**

Filter `navGroups` based on user role. Settings should only show for admin. Add a Users nav item for admin:

```tsx
const navGroups = [
  [
    { path: '/', label: 'Home', icon: LayoutDashboard, exact: true },
    { path: '/brands', label: 'Brands', icon: Package, exact: true },
    { path: '/critical', label: 'Critical', icon: ShieldAlert },
    ...(user?.role !== 'viewer' ? [{ path: '/po', label: 'Build PO', icon: ClipboardList }] : []),
  ],
  ...(user?.role !== 'viewer' ? [[
    { path: '/parties', label: 'Parties', icon: Users },
    { path: '/suppliers', label: 'Suppliers', icon: Truck },
    { path: '/overrides', label: 'Overrides', icon: Pencil },
  ]] : []),
  ...(user?.role === 'admin' ? [[
    { path: '/settings', label: 'Settings', icon: Settings },
    { path: '/users', label: 'Users', icon: UserCircle },
  ]] : []),
]
```

Note: Use a different icon for Users nav if `UserCircle` conflicts with `Users` from lucide. Import `UserCog` for the Users page nav item.

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/Layout.tsx
git commit -m "feat: user menu in header with logout, role-based nav"
```

---

### Task 15: Create Users management page

**Files:**
- Create: `src/dashboard/src/pages/Users.tsx`
- Modify: `src/dashboard/src/App.tsx` (add route)

- [ ] **Step 1: Create Users page**

Create `src/dashboard/src/pages/Users.tsx`:

```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchUsers, createUser, updateUser, resetUserPassword } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useAuth } from '@/contexts/AuthContext'
import { UserCog } from 'lucide-react'

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-red-100 text-red-700',
  purchaser: 'bg-blue-100 text-blue-700',
  viewer: 'bg-gray-100 text-gray-600',
}

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const queryClient = useQueryClient()
  const { data: users = [], isLoading } = useQuery({ queryKey: ['users'], queryFn: fetchUsers })

  const [showCreate, setShowCreate] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState('viewer')
  const [createError, setCreateError] = useState('')

  const [resetId, setResetId] = useState<number | null>(null)
  const [resetPw, setResetPw] = useState('')

  const createMut = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowCreate(false)
      setNewUsername('')
      setNewPassword('')
      setNewRole('viewer')
      setCreateError('')
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCreateError(msg || 'Failed to create user')
    },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { role?: string; is_active?: boolean } }) => updateUser(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })

  const resetMut = useMutation({
    mutationFn: ({ id, pw }: { id: number; pw: string }) => resetUserPassword(id, pw),
    onSuccess: () => { setResetId(null); setResetPw('') },
  })

  if (currentUser?.role !== 'admin') return <p className="text-muted-foreground">Admin access required.</p>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <UserCog className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Users</h2>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          {showCreate ? 'Cancel' : '+ Add User'}
        </button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Create New User</CardTitle></CardHeader>
          <CardContent>
            <form
              onSubmit={e => { e.preventDefault(); createMut.mutate({ username: newUsername, password: newPassword, role: newRole }) }}
              className="flex flex-wrap items-end gap-3"
            >
              <div className="space-y-1">
                <label className="text-xs font-medium">Username</label>
                <input
                  value={newUsername} onChange={e => setNewUsername(e.target.value)}
                  className="flex h-9 w-40 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  required minLength={2}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Password</label>
                <input
                  type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)}
                  className="flex h-9 w-40 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  required minLength={8}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Role</label>
                <select
                  value={newRole} onChange={e => setNewRole(e.target.value)}
                  className="flex h-9 w-32 rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="viewer">Viewer</option>
                  <option value="purchaser">Purchaser</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <button
                type="submit" disabled={createMut.isPending}
                className="h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                {createMut.isPending ? 'Creating...' : 'Create'}
              </button>
            </form>
            {createError && <p className="text-sm text-red-600 mt-2">{createError}</p>}
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <p className="text-muted-foreground text-sm">Loading users...</p>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Username</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Role</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Status</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Last Login</th>
                  <th className="text-right px-4 py-2.5 font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u: Record<string, unknown>) => (
                  <tr key={u.id as number} className="border-b last:border-0">
                    <td className="px-4 py-2.5 font-medium">{u.username as string}</td>
                    <td className="px-4 py-2.5">
                      <select
                        value={u.role as string}
                        onChange={e => updateMut.mutate({ id: u.id as number, data: { role: e.target.value } })}
                        className="text-xs rounded border px-2 py-1 bg-background"
                        disabled={u.id === currentUser?.id}
                      >
                        <option value="viewer">Viewer</option>
                        <option value="purchaser">Purchaser</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge className={u.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {u.last_login
                        ? new Date(u.last_login as string).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                        : 'Never'}
                    </td>
                    <td className="px-4 py-2.5 text-right space-x-2">
                      <button
                        onClick={() => setResetId(u.id as number)}
                        className="text-xs text-primary hover:underline"
                      >
                        Reset Password
                      </button>
                      {u.id !== currentUser?.id && (
                        <button
                          onClick={() => updateMut.mutate({ id: u.id as number, data: { is_active: !(u.is_active as boolean) } })}
                          className={`text-xs ${u.is_active ? 'text-red-600' : 'text-green-600'} hover:underline`}
                        >
                          {u.is_active ? 'Deactivate' : 'Reactivate'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Reset password modal */}
      {resetId !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg p-6 w-full max-w-sm space-y-4 shadow-lg">
            <h3 className="font-semibold">Reset Password</h3>
            <input
              type="password" value={resetPw} onChange={e => setResetPw(e.target.value)}
              placeholder="New password (min 8 chars)"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              minLength={8}
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => { setResetId(null); setResetPw('') }} className="px-3 py-1.5 text-sm rounded border hover:bg-muted">Cancel</button>
              <button
                onClick={() => resetMut.mutate({ id: resetId, pw: resetPw })}
                disabled={resetPw.length < 8 || resetMut.isPending}
                className="px-3 py-1.5 text-sm rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {resetMut.isPending ? 'Resetting...' : 'Reset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add /users route to App.tsx**

Add lazy import:
```tsx
const Users = lazy(() => import('./pages/Users'))
```

Add route inside the protected Layout group:
```tsx
<Route path="/users" element={<SuspenseWrapper><Users /></SuspenseWrapper>} />
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/Users.tsx src/dashboard/src/App.tsx
git commit -m "feat: Users management page with create, role change, reset password, deactivate"
```

---

### Task 14b: Add user info + logout to MobileLayout

**Files:**
- Modify: `src/dashboard/src/components/mobile/MobileLayout.tsx`

The mobile layout uses a hamburger drawer (Sheet) for navigation. The user info and logout button go inside this drawer.

- [ ] **Step 1: Add user info section to the drawer**

In `MobileLayout.tsx`, import `useAuth` and `LogOut`:
```tsx
import { useAuth } from '@/contexts/AuthContext'
import { LogOut } from 'lucide-react'
```

Inside the `<Sheet>` drawer, after the `DRAWER_GROUPS` map, add a user section at the bottom:

```tsx
{/* User section at bottom of drawer */}
<div className="absolute bottom-0 left-0 right-0 border-t bg-card px-4 py-3">
  <div className="flex items-center justify-between">
    <div>
      <p className="text-sm font-medium">{user?.username}</p>
      <p className="text-[10px] text-muted-foreground capitalize">{user?.role}</p>
    </div>
    <button
      onClick={() => { logout(); setDrawerOpen(false) }}
      className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2 py-1.5 rounded-md hover:bg-muted transition-colors"
    >
      <LogOut className="h-3.5 w-3.5" />
      Sign out
    </button>
  </div>
</div>
```

Get `user` and `logout` from `useAuth()` at the top of the component:
```tsx
const { user, logout } = useAuth()
```

- [ ] **Step 2: Apply role-based filtering to mobile nav**

Filter `DRAWER_GROUPS` based on role — hide Data Management items for viewers, hide Settings for non-admins. Move the groups into the component body (not module-level) so they can reference `user.role`:

```tsx
const drawerGroups = [
  ...(user?.role !== 'viewer' ? [{
    title: 'Data Management',
    items: [
      { path: '/parties', label: 'Parties', icon: Users },
      { path: '/suppliers', label: 'Suppliers', icon: Truck },
      { path: '/overrides', label: 'Overrides', icon: Pencil },
      { path: '/brands?filter=dead-stock', label: 'Dead Stock', icon: Skull },
    ],
  }] : []),
  {
    title: 'System',
    items: [
      ...(user?.role === 'admin' ? [
        { path: '/settings', label: 'Settings', icon: Settings },
        { path: '/users', label: 'Users', icon: UserCog },
      ] : []),
      { path: '/help', label: 'Help Guide', icon: BookOpen },
    ],
  },
]
```

Also filter `BOTTOM_TABS` — hide Build PO tab for viewers:
```tsx
const bottomTabs = BOTTOM_TABS.filter(t => !(t.path === '/po' && user?.role === 'viewer'))
```

- [ ] **Step 3: Add /users to PAGE_TITLES**

```tsx
const PAGE_TITLES: Record<string, string> = {
  ...existing entries,
  '/users': 'Users',
}
```

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/components/mobile/MobileLayout.tsx
git commit -m "feat: user info + logout in mobile drawer, role-based mobile nav"
```

---

## Chunk 5: Deploy + Sync

### Task 16: Set JWT_SECRET on Railway and sync DB

- [ ] **Step 1: Generate a production JWT secret**

Run: `openssl rand -hex 32`

Copy the output.

- [ ] **Step 2: Set JWT_SECRET environment variable on Railway**

```bash
railway variables set JWT_SECRET=<the-hex-string-from-step-1>
```

Or use Railway dashboard: project settings > variables > add `JWT_SECRET`.

- [ ] **Step 3: Run the users migration on Railway**

Option A — via Railway CLI:
```bash
railway run -- psql "$DATABASE_URL" -f src/db/migrations/010_users_table.sql
```

Option B — run locally against Railway DB using `sync-to-railway.sh` (which recreates schema).

- [ ] **Step 4: Build frontend and push**

```bash
cd src/dashboard && npm run build
git add -A
git commit -m "feat: complete auth system — login, roles, user management"
git push
```

Railway auto-deploys from main.

- [ ] **Step 5: Verify on production**

1. Open `https://artlounge-reorder-production.up.railway.app` — should redirect to login
2. Login as `kshitij` / `Admin@2026` — should see dashboard
3. Navigate to `/users` — should see all 3 users
4. Verify Settings nav only visible to admin
5. Log out and verify redirect to login

---

## Summary

| Task | What | Estimated Steps |
|------|------|-----------------|
| 1 | Install Python deps | 3 |
| 2 | JWT settings | 2 |
| 3 | Auth module (hash, JWT, deps) | 5 |
| 4 | Users table migration + seed | 5 |
| 5 | Auth API routes (login/me/change-pw) | 2 |
| 6 | User management routes (admin CRUD) | 2 |
| 7 | Register routers + rate limiting | 3 |
| 8 | Protect existing API routes | 5 |
| 9 | TypeScript auth types | 2 |
| 10 | Axios interceptor + auth API funcs | 2 |
| 11 | AuthContext provider | 2 |
| 12 | ProtectedRoute + Login page | 3 |
| 13 | Wire into App.tsx | 3 |
| 14 | User menu + role-based nav (desktop) | 3 |
| 14b | User info + logout in mobile drawer, role-based mobile nav | 4 |
| 15 | Users management page | 3 |
| 16 | Deploy to Railway | 5 |
| **Total** | | **54 steps** |
