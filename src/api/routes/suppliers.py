"""Supplier CRUD API endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.database import get_db

router = APIRouter(tags=["suppliers"])


class SupplierCreate(BaseModel):
    name: str
    tally_party: str = ""
    lead_time_sea: int | None = None
    lead_time_air: int | None = None
    lead_time_default: int = 90
    currency: str = "USD"
    min_order_value: float | None = None
    typical_order_months: int | None = None
    notes: str = ""


class SupplierUpdate(BaseModel):
    name: str | None = None
    tally_party: str | None = None
    lead_time_sea: int | None = None
    lead_time_air: int | None = None
    lead_time_default: int | None = None
    currency: str | None = None
    min_order_value: float | None = None
    typical_order_months: int | None = None
    notes: str | None = None


@router.get("/suppliers")
def list_suppliers():
    """List all suppliers."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM suppliers ORDER BY name")
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/suppliers")
def create_supplier(req: SupplierCreate):
    """Add a new supplier."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO suppliers (name, tally_party, lead_time_sea, lead_time_air,
                    lead_time_default, currency, min_order_value, typical_order_months, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (req.name, req.tally_party, req.lead_time_sea, req.lead_time_air,
                  req.lead_time_default, req.currency, req.min_order_value,
                  req.typical_order_months, req.notes))
            row = cur.fetchone()
        conn.commit()
    return dict(row)


@router.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, req: SupplierUpdate):
    """Update an existing supplier."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    set_parts = [f"{k} = %s" for k in updates]
    values = list(updates.values())
    values.append(supplier_id)

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
    return dict(row)


@router.delete("/suppliers/{supplier_id}")
def delete_supplier(supplier_id: int):
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
