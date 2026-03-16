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

    # Prevent admin from deactivating themselves
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
