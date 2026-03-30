"""App settings API endpoints."""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from api.database import get_db
from api.auth import get_current_user, require_role
from engine.recalculate_buffers import recalculate_all_buffers

router = APIRouter(tags=["settings"])

BUFFER_KEYS = {"use_xyz_buffer"} | {
    f"buffer_{abc}{xyz}" for abc in "abc" for xyz in "xyz"
} | {f"buffer_{abc}" for abc in "abc"}

# Keys that affect brand rollup counts (dead stock / slow mover classification)
RECALC_KEYS = BUFFER_KEYS | {"dead_stock_threshold_days", "slow_mover_velocity_threshold"}

VALID_SETTINGS_KEYS = {
    "dead_stock_threshold_days",
    "slow_mover_velocity_threshold",
    "use_xyz_buffer",
    "buffer_a", "buffer_b", "buffer_c",
    "buffer_ax", "buffer_ay", "buffer_az",
    "buffer_bx", "buffer_by", "buffer_bz",
    "buffer_cx", "buffer_cy", "buffer_cz",
    "min_velocity_sample_days",
}

PIPELINE_RECALC_KEYS = set()  # No settings currently trigger full pipeline recalc


class SettingUpdate(BaseModel):
    value: str


def _recalc_buffers():
    """Background task: recalculate all safety buffers and reorder statuses."""
    with get_db() as conn:
        recalculate_all_buffers(conn)


def _recalc_pipeline():
    """Background task: full pipeline recompute (positions + velocity + buffers)."""
    from engine.pipeline import run_computation_pipeline
    with get_db() as conn:
        run_computation_pipeline(conn)


@router.get("/settings")
def get_settings(user: dict = Depends(get_current_user)):
    """Return all app_settings as a {key: value} dict."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM app_settings ORDER BY key")
            rows = cur.fetchall()
    return {r["key"]: r["value"] for r in rows}


@router.put("/settings/{key}")
def update_setting(key: str, body: SettingUpdate, background_tasks: BackgroundTasks, user: dict = Depends(require_role("admin"))):
    """Update a single setting by key. Buffer changes trigger automatic recalculation."""
    if key not in VALID_SETTINGS_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown setting key: {key}")

    # Validate numeric settings
    NUMERIC_INT_KEYS = {"dead_stock_threshold_days", "min_velocity_sample_days"}
    NUMERIC_FLOAT_KEYS = {"slow_mover_velocity_threshold"} | BUFFER_KEYS - {"use_xyz_buffer"}
    if key in NUMERIC_INT_KEYS:
        try:
            v = int(body.value)
            if v < 0:
                raise ValueError("must be non-negative")
        except ValueError:
            raise HTTPException(400, f"Setting '{key}' must be a non-negative integer")
    elif key in NUMERIC_FLOAT_KEYS:
        try:
            v = float(body.value)
            if v < 0:
                raise ValueError("must be non-negative")
        except ValueError:
            raise HTTPException(400, f"Setting '{key}' must be a non-negative number")

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

    # Invalidate settings cache so SKU endpoints pick up new values immediately
    from api.routes.skus import _invalidate_settings_cache
    _invalidate_settings_cache()

    # Trigger recalculation in the background when buffer/threshold settings change
    if key in RECALC_KEYS:
        background_tasks.add_task(_recalc_buffers)

    if key in PIPELINE_RECALC_KEYS:
        background_tasks.add_task(_recalc_pipeline)

    return dict(row)
