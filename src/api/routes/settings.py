"""App settings API endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.database import get_db

router = APIRouter(tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


@router.get("/settings")
def get_settings():
    """Return all app_settings as a {key: value} dict."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM app_settings ORDER BY key")
            rows = cur.fetchall()
    return {r["key"]: r["value"] for r in rows}


@router.put("/settings/{key}")
def update_setting(key: str, body: SettingUpdate):
    """Update a single setting by key."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app_settings SET value = %s, updated_at = NOW() WHERE key = %s RETURNING key, value",
                (body.value, key),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, f"Setting '{key}' not found")
        conn.commit()
    return dict(row)
