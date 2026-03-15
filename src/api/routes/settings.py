"""App settings API endpoints."""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from api.database import get_db
from engine.recalculate_buffers import recalculate_all_buffers

router = APIRouter(tags=["settings"])

BUFFER_KEYS = {"use_xyz_buffer"} | {
    f"buffer_{abc}{xyz}" for abc in "abc" for xyz in "xyz"
} | {f"buffer_{abc}" for abc in "abc"}


class SettingUpdate(BaseModel):
    value: str


def _recalc_buffers():
    """Background task: recalculate all safety buffers and reorder statuses."""
    with get_db() as conn:
        recalculate_all_buffers(conn)


@router.get("/settings")
def get_settings():
    """Return all app_settings as a {key: value} dict."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM app_settings ORDER BY key")
            rows = cur.fetchall()
    return {r["key"]: r["value"] for r in rows}


@router.put("/settings/{key}")
def update_setting(key: str, body: SettingUpdate, background_tasks: BackgroundTasks):
    """Update a single setting by key. Buffer changes trigger automatic recalculation."""
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

    # Trigger buffer recalculation in the background when buffer settings change
    if key in BUFFER_KEYS:
        background_tasks.add_task(_recalc_buffers)

    return dict(row)
