"""Tests for auth module: password hashing, JWT, role hierarchy."""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException

from api.auth import (
    hash_password,
    verify_password,
    create_token,
    decode_token,
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
        import jwt as pyjwt
        token = pyjwt.encode(
            {
                "sub": "1",
                "username": "test",
                "role": "viewer",
                "exp": datetime.now(timezone.utc) - timedelta(seconds=10),
            },
            "dev-secret-change-in-production",
            algorithm="HS256",
        )
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
