"""Authentication API routes: login, me, change-password."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.requests import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth import verify_password, hash_password, create_token, get_current_user
from api.database import get_db

router = APIRouter(tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/login")
@limiter.limit("5/minute")
def login(request: Request, req: LoginRequest):
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
        hash_password("dummy")
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
