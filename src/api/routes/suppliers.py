"""Supplier CRUD API endpoints."""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, field_validator
from api.database import get_db
from api.auth import get_current_user, require_role
from engine.recalculate_buffers import recalculate_all_buffers

router = APIRouter(tags=["suppliers"])


class SupplierCreate(BaseModel):
    name: str
    lead_time_sea: int | None = None
    lead_time_air: int | None = None
    lead_time_default: int = 90
    currency: str = "USD"
    min_order_value: float | None = None
    typical_order_months: int | None = None
    notes: str = ""
    buffer_override: float | None = None
    lead_time_demand_mode: str = "full"

    @field_validator('lead_time_default', 'lead_time_sea', 'lead_time_air')
    @classmethod
    def validate_lead_time(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Lead time must be positive')
        return v

    @field_validator('lead_time_demand_mode')
    @classmethod
    def validate_demand_mode(cls, v):
        if v not in ('full', 'coverage_only'):
            raise ValueError('lead_time_demand_mode must be "full" or "coverage_only"')
        return v


class SupplierUpdate(BaseModel):
    name: str | None = None
    lead_time_sea: int | None = None
    lead_time_air: int | None = None
    lead_time_default: int | None = None
    currency: str | None = None
    min_order_value: float | None = None
    typical_order_months: int | None = None
    notes: str | None = None
    buffer_override: float | None = None
    lead_time_demand_mode: str | None = None

    @field_validator('lead_time_default', 'lead_time_sea', 'lead_time_air')
    @classmethod
    def validate_lead_time(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Lead time must be positive')
        return v


@router.get("/suppliers")
def list_suppliers(user: dict = Depends(get_current_user)):
    """List all suppliers."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM suppliers ORDER BY name")
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def _recalc_buffers():
    """Background task: recalculate all safety buffers and reorder statuses."""
    with get_db() as conn:
        recalculate_all_buffers(conn)


@router.post("/suppliers")
def create_supplier(req: SupplierCreate, background_tasks: BackgroundTasks, user: dict = Depends(require_role("admin"))):
    """Add a new supplier."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO suppliers (name, lead_time_sea, lead_time_air,
                    lead_time_default, currency, min_order_value, typical_order_months,
                    notes, buffer_override, lead_time_demand_mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (req.name, req.lead_time_sea, req.lead_time_air,
                  req.lead_time_default, req.currency, req.min_order_value,
                  req.typical_order_months, req.notes, req.buffer_override,
                  req.lead_time_demand_mode))
            row = cur.fetchone()
        conn.commit()

    if req.buffer_override is not None:
        background_tasks.add_task(_recalc_buffers)

    return dict(row)


@router.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, req: SupplierUpdate, background_tasks: BackgroundTasks, user: dict = Depends(require_role("admin"))):
    """Update an existing supplier."""
    ALLOWED_SUPPLIER_COLUMNS = {
        "name", "lead_time_sea", "lead_time_air",
        "lead_time_default", "currency", "min_order_value",
        "typical_order_months", "notes", "buffer_override",
        "lead_time_demand_mode",
    }

    # Use exclude_unset to distinguish "field not sent" from "field sent as null".
    # All sent fields (including null) are included if they're in ALLOWED_SUPPLIER_COLUMNS.
    sent_fields = req.model_dump(exclude_unset=True)
    updates = {k: v for k, v in sent_fields.items() if k in ALLOWED_SUPPLIER_COLUMNS}
    if not updates:
        raise HTTPException(400, "No valid fields to update")

    set_parts = [f"{k} = %s" for k in updates]
    values = list(updates.values())
    values.append(supplier_id)

    recalc_fields = {"buffer_override", "lead_time_default", "lead_time_sea", "lead_time_air", "typical_order_months", "lead_time_demand_mode"}
    needs_recalc = bool(recalc_fields & set(sent_fields.keys()))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE suppliers SET {', '.join(set_parts)}
                WHERE id = %s RETURNING *
            """, values)
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Supplier not found")
        conn.commit()

    if needs_recalc:
        background_tasks.add_task(_recalc_buffers)

    return dict(row)


@router.delete("/suppliers/{supplier_id}")
def delete_supplier(supplier_id: int, user: dict = Depends(require_role("admin"))):
    """Delete a supplier (only if not referenced)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # Check if supplier is referenced
            cur.execute("""
                SELECT COUNT(*) AS cnt FROM brand_metrics
                WHERE primary_supplier = (SELECT name FROM suppliers WHERE id = %s)
            """, (supplier_id,))
            if cur.fetchone()["cnt"] > 0:
                raise HTTPException(400, "Cannot delete supplier that is referenced by brand metrics")

            cur.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
            if cur.rowcount == 0:
                raise HTTPException(404, "Supplier not found")
        conn.commit()
    return {"success": True}
