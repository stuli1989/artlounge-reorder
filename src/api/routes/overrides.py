"""Override CRUD API endpoints."""
import json
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends
from pydantic import BaseModel
from api.database import get_db
from api.auth import get_current_user, require_role
from engine.effective_values import OVERRIDE_FIELD_TO_COLUMN

router = APIRouter(tags=["overrides"])

VALID_FIELDS = {"current_stock", "total_velocity", "wholesale_velocity",
                "online_velocity", "store_velocity", "note"}


class OverrideCreate(BaseModel):
    stock_item_name: str
    field_name: str
    override_value: float | None = None
    note: str
    hold_from_po: bool = False
    created_by: str = "user"
    expires_at: str | None = None


class OverrideDeactivate(BaseModel):
    reason: str
    performed_by: str = "user"


class OverrideReview(BaseModel):
    action: str  # "keep" or "remove"
    reason: str | None = None
    new_value: float | None = None
    performed_by: str = "user"


SAFE_COLUMNS = {"current_stock", "total_velocity", "wholesale_velocity", "online_velocity"}


def _recalc_for_sku(stock_item_name: str):
    """Background task: recompute buffer/reorder status for a single SKU (phases 5+6)."""
    from engine.pipeline import run_computation_pipeline
    with get_db() as conn:
        run_computation_pipeline(conn, phases=[5, 6], scope={"sku": stock_item_name})


def _snapshot_computed_value(cur, stock_item_name: str, field_name: str) -> float | None:
    """Get the current computed value from sku_metrics for snapshotting."""
    if field_name == "note":
        return None
    col = OVERRIDE_FIELD_TO_COLUMN.get(field_name)
    if col:
        if col not in SAFE_COLUMNS:
            raise ValueError(f"Invalid column: {col}")
        cur.execute(f"SELECT {col} FROM sku_metrics WHERE stock_item_name = %s", (stock_item_name,))
        row = cur.fetchone()
        return float(row[col]) if row and row[col] is not None else None
    if field_name == "store_velocity":
        # store_velocity is derived: total - wholesale - online
        cur.execute(
            "SELECT total_velocity, wholesale_velocity, online_velocity FROM sku_metrics WHERE stock_item_name = %s",
            (stock_item_name,),
        )
        row = cur.fetchone()
        if not row:
            return None
        total = float(row["total_velocity"] or 0)
        wholesale = float(row["wholesale_velocity"] or 0)
        online = float(row["online_velocity"] or 0)
        return max(0, total - wholesale - online)
    return None


@router.post("/overrides")
def create_override(req: OverrideCreate, background_tasks: BackgroundTasks, user: dict = Depends(require_role("purchaser"))):
    """Create a new override. Deactivates any prior active override for the same field."""
    if req.field_name not in VALID_FIELDS:
        raise HTTPException(400, f"Invalid field_name. Must be one of: {', '.join(sorted(VALID_FIELDS))}")
    if req.field_name != "note" and req.override_value is None:
        raise HTTPException(400, "override_value is required for non-note overrides")

    with get_db() as conn:
        with conn.cursor() as cur:
            # Verify SKU exists
            cur.execute("SELECT 1 FROM stock_items WHERE name = %s", (req.stock_item_name,))
            if not cur.fetchone():
                raise HTTPException(404, f"Stock item '{req.stock_item_name}' not found")

            # Snapshot computed value
            computed_val = _snapshot_computed_value(cur, req.stock_item_name, req.field_name)

            # Deactivate prior active override for same field
            cur.execute("""
                UPDATE overrides
                SET is_active = FALSE, deactivated_at = NOW(),
                    deactivated_reason = 'Superseded by new override'
                WHERE stock_item_name = %s AND field_name = %s AND is_active = TRUE
                RETURNING id
            """, (req.stock_item_name, req.field_name))
            old_row = cur.fetchone()

            if old_row:
                cur.execute("""
                    INSERT INTO override_audit_log (override_id, action, performed_by, note)
                    VALUES (%s, 'deactivated', %s, 'Superseded by new override')
                """, (old_row["id"], req.created_by))

            # Insert new override
            cur.execute("""
                INSERT INTO overrides (
                    stock_item_name, field_name, override_value, note,
                    hold_from_po, created_by, expires_at,
                    computed_value_at_creation, computed_value_latest
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                req.stock_item_name, req.field_name, req.override_value,
                req.note, req.hold_from_po, req.created_by,
                req.expires_at, computed_val, computed_val,
            ))
            new_row = cur.fetchone()

            # Audit log
            cur.execute("""
                INSERT INTO override_audit_log (override_id, action, new_values, performed_by, note)
                VALUES (%s, 'created', %s, %s, %s)
            """, (
                new_row["id"],
                json.dumps({"override_value": req.override_value, "field_name": req.field_name}),
                req.created_by,
                req.note,
            ))

        conn.commit()

    # Trigger targeted recompute for this SKU (phases 5+6: buffer + reorder)
    background_tasks.add_task(_recalc_for_sku, req.stock_item_name)

    return dict(new_row)


@router.get("/overrides")
def list_overrides(
    is_stale: bool | None = Query(None),
    stock_item_name: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    """List active overrides with current computed values from sku_metrics."""
    conditions = ["o.is_active = TRUE"]
    params: list = []

    if is_stale is not None:
        conditions.append("o.is_stale = %s")
        params.append(is_stale)

    if stock_item_name:
        conditions.append("o.stock_item_name = %s")
        params.append(stock_item_name)

    where = " AND ".join(conditions)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT o.*,
                       sm.current_stock AS computed_current_stock,
                       sm.total_velocity AS computed_total_velocity,
                       sm.wholesale_velocity AS computed_wholesale_velocity,
                       sm.online_velocity AS computed_online_velocity,
                       sm.category_name
                FROM overrides o
                LEFT JOIN sku_metrics sm ON sm.stock_item_name = o.stock_item_name
                WHERE {where}
                ORDER BY o.is_stale DESC, o.created_at DESC
            """, params)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/overrides/{override_id}")
def get_override(override_id: int, user: dict = Depends(get_current_user)):
    """Get a single override with its audit log."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM overrides WHERE id = %s", (override_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Override not found")

            cur.execute("""
                SELECT * FROM override_audit_log
                WHERE override_id = %s
                ORDER BY performed_at DESC
            """, (override_id,))
            audit = cur.fetchall()

    result = dict(row)
    result["audit_log"] = [dict(a) for a in audit]
    return result


@router.delete("/overrides/{override_id}")
def deactivate_override(override_id: int, req: OverrideDeactivate, background_tasks: BackgroundTasks, user: dict = Depends(require_role("purchaser"))):
    """Soft-deactivate an override."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE overrides
                SET is_active = FALSE, deactivated_at = NOW(), deactivated_reason = %s
                WHERE id = %s AND is_active = TRUE
                RETURNING *
            """, (req.reason, override_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Active override not found")

            cur.execute("""
                INSERT INTO override_audit_log (override_id, action, performed_by, note)
                VALUES (%s, 'deactivated', %s, %s)
            """, (override_id, req.performed_by, req.reason))

        conn.commit()

    # Trigger targeted recompute so reorder status reflects the removed override
    stock_item_name = row["stock_item_name"]
    background_tasks.add_task(_recalc_for_sku, stock_item_name)

    return dict(row)


@router.post("/overrides/{override_id}/review")
def review_override(override_id: int, req: OverrideReview, background_tasks: BackgroundTasks, user: dict = Depends(require_role("purchaser"))):
    """Handle a stale override — keep (rebase) or remove (deactivate)."""
    if req.action not in ("keep", "remove"):
        raise HTTPException(400, "action must be 'keep' or 'remove'")

    updated = None
    sku_name = None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM overrides WHERE id = %s AND is_active = TRUE", (override_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Active override not found")

            sku_name = row["stock_item_name"]

            if req.action == "keep":
                # Rebase: update snapshot to current, reset stale flag
                new_val = req.new_value if req.new_value is not None else row["override_value"]
                computed_now = _snapshot_computed_value(cur, row["stock_item_name"], row["field_name"])

                cur.execute("""
                    UPDATE overrides
                    SET is_stale = FALSE, stale_since = NULL,
                        last_reviewed_at = NOW(),
                        override_value = %s,
                        computed_value_at_creation = %s,
                        computed_value_latest = %s,
                        drift_pct = 0
                    WHERE id = %s
                    RETURNING *
                """, (new_val, computed_now, computed_now, override_id))
                updated = cur.fetchone()

                cur.execute("""
                    INSERT INTO override_audit_log
                        (override_id, action, old_values, new_values, performed_by, note)
                    VALUES (%s, 'reviewed_keep', %s, %s, %s, %s)
                """, (
                    override_id,
                    json.dumps({"override_value": float(row["override_value"]) if row["override_value"] else None}),
                    json.dumps({"override_value": float(new_val) if new_val else None}),
                    req.performed_by,
                    req.reason or "Reviewed and kept",
                ))

            else:  # remove
                cur.execute("""
                    UPDATE overrides
                    SET is_active = FALSE, deactivated_at = NOW(),
                        deactivated_reason = %s
                    WHERE id = %s
                    RETURNING *
                """, (req.reason or "Removed during review", override_id))
                updated = cur.fetchone()

                cur.execute("""
                    INSERT INTO override_audit_log (override_id, action, performed_by, note)
                    VALUES (%s, 'reviewed_remove', %s, %s)
                """, (override_id, req.performed_by, req.reason or "Removed during review"))

        conn.commit()

    # Trigger targeted recompute so reorder status reflects the updated override
    background_tasks.add_task(_recalc_for_sku, sku_name)

    return dict(updated)
