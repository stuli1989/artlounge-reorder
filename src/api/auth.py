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
