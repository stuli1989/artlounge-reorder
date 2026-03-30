"""SKU detail API endpoints."""
import threading
import time
from datetime import date, timedelta
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from api.auth import get_current_user, require_role
from pydantic import BaseModel
from api.database import get_db
import psycopg2.extras
from api.sql_fragments import OVERRIDE_AGG_SUBQUERY
from engine.velocity import (
    calculate_velocity, find_in_stock_periods,
    resolve_date_range, fetch_batch_velocities, velocities_from_batch_row, opt_float,
)
from engine.reorder import calculate_days_to_stockout, determine_reorder_status, DEFAULT_LEAD_TIME, must_stock_fallback_qty, compute_coverage_days
from engine.effective_values import compute_effective_values, compute_effective_status
from engine.classification import compute_safety_buffer, fetch_buffer_settings, fetch_use_xyz_global
from config.settings import FY_START_DATE, FY_END_DATE

router = APIRouter(tags=["skus"])

# In-memory settings cache (60s TTL, thread-safe)
_settings_lock = threading.Lock()
_settings_cache: dict = {"data": None, "expires": 0.0}
_SETTINGS_TTL = 60.0


def _get_cached_settings(cur) -> dict:
    now = time.monotonic()
    with _settings_lock:
        if _settings_cache["data"] is not None and now < _settings_cache["expires"]:
            return _settings_cache["data"]
    cur.execute("SELECT key, value FROM app_settings WHERE key IN ('dead_stock_threshold_days', 'slow_mover_velocity_threshold')")
    data = {r["key"]: r["value"] for r in cur.fetchall()}
    with _settings_lock:
        _settings_cache["data"] = data
        _settings_cache["expires"] = time.monotonic() + _SETTINGS_TTL
    return data


def _invalidate_settings_cache():
    """Clear settings cache so next request fetches fresh values."""
    global _settings_cache
    with _settings_lock:
        _settings_cache = {"data": None, "expires": 0.0}


def _escape_ilike(s: str) -> str:
    """Escape PostgreSQL ILIKE special characters."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

ALLOWED_SORT_COLS = {
    "days_to_stockout", "total_velocity", "current_stock",
    "stock_item_name", "reorder_status", "wholesale_velocity", "online_velocity",
    "wma_total_velocity", "total_revenue", "abc_class", "trend_direction",
}


@router.get("/brands/{category_name}/skus")
def list_skus(
    category_name: str,
    status: str = Query(None, description="Comma-separated: urgent,reorder,healthy,out_of_stock,lost_sales,dead_stock,no_data"),
    min_velocity: float = Query(None),
    sort: str = Query("days_to_stockout"),
    sort_dir: str = Query("asc"),
    search: str = Query(None),
    hazardous: bool = Query(None, description="Filter by hazardous flag"),
    dead_stock: bool = Query(None, description="Filter by dead stock status"),
    reorder_intent: str = Query(None, description="Filter by reorder intent: must_stock, normal, do_not_reorder"),
    slow_mover: bool = Query(None, description="Filter by slow mover status"),
    from_date: str = Query(None, description="Analysis period start (YYYY-MM-DD)"),
    to_date: str = Query(None, description="Analysis period end (YYYY-MM-DD)"),
    abc_class: str = Query(None, description="Filter by ABC class: A, B, C"),
    xyz_class: str = Query(None, description="Filter by XYZ class: X, Y, Z"),
    hide_inactive: bool = Query(True, description="Hide inactive/artifact SKUs"),
    velocity_type: str = Query("flat", description="Velocity type for sorting: flat or wma"),
    paginated: bool = Query(False, description="Return paginated envelope for large tables"),
    limit: int = Query(100, ge=1, le=500, description="Page size when paginated=true"),
    offset: int = Query(0, ge=0, description="Page offset when paginated=true"),
    user: dict = Depends(get_current_user),
):
    """List SKU metrics for a brand with filtering and sorting."""
    custom_range = from_date is not None or to_date is not None

    conditions = ["sm.category_name = %s"]
    params = [category_name]

    # Skip SQL status filter when recalculating (status changes with date range)
    if status and not custom_range:
        statuses = [s.strip() for s in status.split(",")]
        conditions.append("sm.reorder_status = ANY(%s)")
        params.append(statuses)

    if min_velocity is not None and not custom_range:
        conditions.append("sm.total_velocity >= %s")
        params.append(min_velocity)

    if search:
        escaped = _escape_ilike(search)
        conditions.append("(sm.stock_item_name ILIKE %s OR COALESCE(si.part_no, '') ILIKE %s)")
        params.append(f"%{escaped}%")
        params.append(f"%{escaped}%")

    if hazardous is not None:
        conditions.append("COALESCE(si.is_hazardous, FALSE) = %s")
        params.append(hazardous)

    if reorder_intent is not None:
        conditions.append("COALESCE(si.reorder_intent, 'normal') = %s")
        params.append(reorder_intent)

    if abc_class is not None:
        conditions.append("sm.abc_class = %s")
        params.append(abc_class.upper())

    if xyz_class is not None:
        conditions.append("sm.xyz_class = %s")
        params.append(xyz_class.upper())

    if hide_inactive:
        conditions.append("COALESCE(si.is_active, TRUE) = TRUE")

    where = " AND ".join(conditions)

    # Sanitize sort column
    sort_col = sort if sort in ALLOWED_SORT_COLS else "days_to_stockout"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    sql = f"""
        SELECT sm.*,
               si.part_no,
               si.is_hazardous,
               si.reorder_intent,
               si.use_xyz_buffer,
               ovr.stock_override_value,
               ovr.stock_override_note,
               ovr.stock_override_stale,
               ovr.stock_hold_from_po,
               ovr.total_vel_override_value,
               ovr.total_vel_override_stale,
               ovr.wholesale_vel_override_value,
               ovr.online_vel_override_value,
               ovr.store_vel_override_value,
               ovr.override_note,
               ovr.note_override_stale,
               COALESCE(ovr.stock_hold_from_po, ovr.total_vel_hold,
                        ovr.wholesale_vel_hold, ovr.online_vel_hold,
                        ovr.store_vel_hold, FALSE) AS hold_from_po
        FROM sku_metrics sm
        LEFT JOIN stock_items si ON si.name = sm.stock_item_name
        LEFT JOIN {OVERRIDE_AGG_SUBQUERY} ovr ON ovr.stock_item_name = sm.stock_item_name
        WHERE {where}
        ORDER BY sm.{sort_col} {direction} NULLS LAST
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            # Get thresholds (cached in-memory, 60s TTL)
            _settings = _get_cached_settings(cur)
            dead_stock_threshold = int(_settings.get("dead_stock_threshold_days", "90"))
            slow_mover_threshold = float(_settings.get("slow_mover_velocity_threshold", "0.1"))

            # Get supplier lead time for status recalculation
            cur.execute(
                "SELECT supplier_lead_time FROM brand_metrics WHERE category_name = %s",
                (category_name,),
            )
            bm_row = cur.fetchone()
            lead_time = bm_row["supplier_lead_time"] if bm_row and bm_row["supplier_lead_time"] else DEFAULT_LEAD_TIME

            cur.execute(sql, params)
            rows = cur.fetchall()

            # Batch velocity recalculation from daily_stock_positions when custom date range is active
            vel_by_sku = {}
            if custom_range:
                range_start, range_end = resolve_date_range(from_date, to_date)
                sku_names = [r["stock_item_name"] for r in rows]
                vel_by_sku = fetch_batch_velocities(cur, sku_names, range_start, range_end)

            # Get supplier coverage and demand mode for this brand
            coverage_period = 90  # fallback
            supplier_demand_mode = "full"
            with conn.cursor() as cur2:
                cur2.execute("""
                    SELECT s.lead_time_default, s.typical_order_months, s.lead_time_demand_mode
                    FROM suppliers s
                    WHERE UPPER(s.name) = UPPER(%s)
                """, (category_name,))
                srow = cur2.fetchone()
                if srow:
                    coverage_period = compute_coverage_days(
                        srow["lead_time_default"],
                        srow["typical_order_months"],
                    )
                    supplier_demand_mode = srow["lead_time_demand_mode"] or "full"
            include_lead_demand = supplier_demand_mode != "coverage_only"

            # Fetch latest drift for these SKUs
            drift_map = {}
            sku_names_for_drift = [r["stock_item_name"] for r in rows]
            if sku_names_for_drift:
                with conn.cursor() as cur3:
                    cur3.execute("""
                        SELECT DISTINCT ON (stock_item_name)
                            stock_item_name, drift, inventory_blocked, check_date
                        FROM drift_log
                        WHERE stock_item_name = ANY(%s)
                        ORDER BY stock_item_name, check_date DESC
                    """, (sku_names_for_drift,))
                    for row in cur3.fetchall():
                        drift_map[row["stock_item_name"]] = {
                            "drift": float(row["drift"]) if row["drift"] is not None else 0,
                            "inventory_blocked": float(row["inventory_blocked"]) if row["inventory_blocked"] is not None else 0,
                            "drift_date": str(row["check_date"]),
                        }

    today = date.today()
    results = []
    for r in rows:
        d = dict(r)

        # Base velocities: recalculated from positions or stored metrics
        if vel_by_sku:
            base_wholesale, base_online, base_store, base_total = velocities_from_batch_row(
                vel_by_sku.get(d["stock_item_name"])
            )
        else:
            base_wholesale = float(d["wholesale_velocity"] or 0)
            base_online = float(d["online_velocity"] or 0)
            base_store = float(d.get("store_velocity") or 0)
            base_total = float(d["total_velocity"] or 0)

        vals = compute_effective_values(
            float(d["current_stock"] or 0),
            base_wholesale,
            base_online,
            base_total,
            stock_ovr=opt_float(d["stock_override_value"]),
            wholesale_ovr=opt_float(d["wholesale_vel_override_value"]),
            online_ovr=opt_float(d["online_vel_override_value"]),
            store_ovr=opt_float(d["store_vel_override_value"]),
            total_ovr=opt_float(d["total_vel_override_value"]),
        )
        st = compute_effective_status(vals["eff_stock"], vals["eff_total"], lead_time, float(d["safety_buffer"] or 1.3), coverage_period=coverage_period, include_lead_demand=include_lead_demand)

        d["effective_stock"] = vals["eff_stock"]
        d["effective_wholesale_velocity"] = vals["eff_wholesale"]
        d["effective_online_velocity"] = vals["eff_online"]
        d["effective_store_velocity"] = vals["eff_store"]
        d["effective_velocity"] = vals["eff_total"]
        d["effective_days_to_stockout"] = st["eff_days"]
        d["effective_status"] = st["eff_status"]
        d["effective_suggested_qty"] = st["eff_suggested"]
        d["has_stock_override"] = vals["has_stock_override"]
        d["has_velocity_override"] = vals["has_velocity_override"]
        d["has_note"] = d["override_note"] is not None
        d["stock_override_stale"] = bool(d.get("stock_override_stale"))
        d["velocity_override_stale"] = bool(d.get("total_vel_override_stale"))
        d["hold_from_po"] = bool(d.get("hold_from_po"))
        # Derive store velocity (not a stored column — computed as remainder)
        d["store_velocity"] = max(0, base_total - base_wholesale - base_online)

        # Dead stock computed fields
        last_sale_date = d.get("last_sale_date")
        days_since = (today - last_sale_date).days if last_sale_date else None
        eff_stock = d["effective_stock"]
        d["last_sale_date"] = last_sale_date.isoformat() if last_sale_date else None
        d["days_since_last_sale"] = days_since
        d["total_zero_activity_days"] = d.get("total_zero_activity_days", 0)
        d["is_dead_stock"] = eff_stock > 0 and (days_since is None or days_since >= dead_stock_threshold)
        d["reorder_intent"] = d.get("reorder_intent", "normal")
        eff_vel = d["effective_velocity"]
        d["is_slow_mover"] = (eff_stock > 0 and eff_vel > 0
                              and eff_vel < slow_mover_threshold
                              and not d["is_dead_stock"])

        # Drift data
        drift_info = drift_map.get(d["stock_item_name"], {})
        d["drift"] = drift_info.get("drift", 0)
        d["inventory_blocked"] = drift_info.get("inventory_blocked", 0)
        d["has_drift"] = abs(drift_info.get("drift", 0)) > 0

        # Clean up internal join columns
        for key in ("stock_override_value", "stock_override_note", "total_vel_override_value",
                     "total_vel_override_stale", "wholesale_vel_override_value",
                     "online_vel_override_value", "store_vel_override_value",
                     "override_note", "note_override_stale", "stock_hold_from_po"):
            d.pop(key, None)

        results.append(d)

    # Post-recalculation status filter (stored status may differ from recalculated)
    if status and custom_range:
        target_statuses = set(s.strip() for s in status.split(","))
        results = [r for r in results if r["effective_status"] in target_statuses]

    # Post-recalculation min_velocity filter
    if min_velocity is not None and custom_range:
        results = [r for r in results if r["effective_velocity"] >= min_velocity]

    # Dead stock filter
    if dead_stock is not None:
        results = [r for r in results if r["is_dead_stock"] == dead_stock]

    # Slow mover filter
    if slow_mover is not None:
        results = [r for r in results if r["is_slow_mover"] == slow_mover]

    if not paginated:
        return results

    counts = {
        "urgent": 0,
        "reorder": 0,
        "healthy": 0,
        "out_of_stock": 0,
        "no_data": 0,
        "dead_stock": 0,
    }

    for row in results:
        status_key = row.get("effective_status") or row.get("reorder_status")
        if status_key in counts:
            counts[status_key] += 1
        if row.get("is_dead_stock"):
            counts["dead_stock"] += 1

    total = len(results)
    page_items = results[offset: offset + limit]
    return {
        "items": page_items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "counts": counts,
    }


@router.get("/critical-skus")
def list_critical_skus(
    status: str = Query("urgent,reorder", description="Comma-separated statuses"),
    abc_class: str = Query(None, description="Filter by ABC class: A, B, C"),
    velocity_type: str = Query("flat", description="flat or wma"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Cross-brand critical/warning SKU list, ordered by days_to_stockout ASC."""
    conditions = ["COALESCE(si.is_active, TRUE) = TRUE"]
    params = []

    statuses = [s.strip() for s in status.split(",")]
    conditions.append("sm.reorder_status = ANY(%s)")
    params.append(statuses)

    if abc_class:
        conditions.append("sm.abc_class = %s")
        params.append(abc_class.upper())

    where = " AND ".join(conditions)

    vel_col = "sm.wma_total_velocity" if velocity_type == "wma" else "sm.total_velocity"

    sql = f"""
        SELECT sm.stock_item_name, sm.category_name, sm.current_stock,
               sm.wholesale_velocity, sm.online_velocity, sm.total_velocity,
               sm.wma_wholesale_velocity, sm.wma_online_velocity, sm.wma_total_velocity,
               sm.days_to_stockout, sm.reorder_status, sm.reorder_qty_suggested,
               sm.abc_class, sm.xyz_class, sm.trend_direction, sm.trend_ratio,
               sm.safety_buffer, sm.total_revenue, sm.demand_cv,
               sm.estimated_stockout_date, sm.last_import_date,
               si.part_no, si.is_hazardous
        FROM sku_metrics sm
        LEFT JOIN stock_items si ON si.name = sm.stock_item_name
        WHERE {where}
        ORDER BY sm.days_to_stockout ASC NULLS LAST
        LIMIT %s OFFSET %s
    """
    count_params = list(params)
    params.extend([limit, offset])

    with get_db() as conn:
        with conn.cursor() as cur:
            # Get total count
            count_sql = f"SELECT COUNT(*) AS cnt FROM sku_metrics sm LEFT JOIN stock_items si ON si.name = sm.stock_item_name WHERE {where}"
            cur.execute(count_sql, count_params)
            total = cur.fetchone()["cnt"]

            cur.execute(sql, params)
            rows = cur.fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


class HazardousUpdate(BaseModel):
    is_hazardous: bool


@router.patch("/skus/{stock_item_name}/hazardous")
def toggle_hazardous(stock_item_name: str, req: HazardousUpdate, user: dict = Depends(require_role("purchaser"))):
    """Toggle hazardous flag on a stock item."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE stock_items SET is_hazardous = %s, updated_at = NOW() WHERE name = %s RETURNING name, is_hazardous",
                (req.is_hazardous, stock_item_name),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Stock item not found")
        conn.commit()
    return dict(row)


class ReorderIntentUpdate(BaseModel):
    reorder_intent: Literal['must_stock', 'normal', 'do_not_reorder']


def _recompute_for_sku(sku_name: str):
    """Background task: run targeted recompute for the SKU's brand."""
    from engine.targeted_recompute import run_targeted_recompute
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT category_name FROM stock_items WHERE name = %s", (sku_name,))
            row = cur.fetchone()
        if row:
            run_targeted_recompute(conn, [row["category_name"]])


@router.patch("/skus/{stock_item_name}/reorder-intent")
def update_reorder_intent(stock_item_name: str, req: ReorderIntentUpdate, background_tasks: BackgroundTasks, user: dict = Depends(require_role("purchaser"))):
    """Update reorder intent classification on a stock item."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE stock_items SET reorder_intent = %s, updated_at = NOW() "
                "WHERE name = %s RETURNING name, reorder_intent",
                (req.reorder_intent, stock_item_name),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Stock item not found")
        conn.commit()
    background_tasks.add_task(_recompute_for_sku, stock_item_name)
    return dict(row)


class XyzBufferUpdate(BaseModel):
    use_xyz_buffer: bool | None = None


@router.patch("/skus/{stock_item_name}/xyz-buffer")
def update_xyz_buffer(stock_item_name: str, req: XyzBufferUpdate, user: dict = Depends(require_role("purchaser"))):
    """Toggle per-item XYZ buffer preference and recompute metrics instantly."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # Update the stock_items toggle and fetch intent in one query
            cur.execute(
                "UPDATE stock_items SET use_xyz_buffer = %s, updated_at = NOW() "
                "WHERE name = %s RETURNING name, reorder_intent",
                (req.use_xyz_buffer, stock_item_name),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Stock item not found")
            item_intent = row["reorder_intent"] or "normal"

            # Recompute buffer + status for this single SKU
            cur.execute(
                "SELECT abc_class, xyz_class, current_stock, total_velocity, category_name, "
                "reorder_status, reorder_qty_suggested, safety_buffer "
                "FROM sku_metrics WHERE stock_item_name = %s",
                (stock_item_name,),
            )
            sm = cur.fetchone()
            if not sm:
                conn.commit()
                return {"name": stock_item_name, "use_xyz_buffer": req.use_xyz_buffer}

            # Determine effective use_xyz
            use_xyz_global = fetch_use_xyz_global(conn)
            use_xyz = req.use_xyz_buffer if req.use_xyz_buffer is not None else use_xyz_global
            buffer_settings = fetch_buffer_settings(conn)
            new_buffer = compute_safety_buffer(
                sm["abc_class"], sm["xyz_class"], buffer_settings, use_xyz=use_xyz
            )

            # Recompute reorder status
            current_stock = float(sm["current_stock"] or 0)
            total_vel = float(sm["total_velocity"] or 0)

            cur.execute(
                "SELECT supplier_lead_time FROM brand_metrics WHERE category_name = %s",
                (sm["category_name"],),
            )
            bm = cur.fetchone()
            lead_time = bm["supplier_lead_time"] if bm and bm["supplier_lead_time"] else DEFAULT_LEAD_TIME

            # Look up coverage period for this brand's supplier
            cur.execute(
                "SELECT typical_order_months FROM suppliers WHERE UPPER(name) = UPPER(%s)",
                (sm["category_name"],),
            )
            srow = cur.fetchone()
            coverage = compute_coverage_days(
                lead_time, srow["typical_order_months"] if srow else None
            )

            days_to_so = calculate_days_to_stockout(current_stock, total_vel)
            status, suggested_qty = determine_reorder_status(
                current_stock, days_to_so, lead_time, total_vel,
                safety_buffer=new_buffer, coverage_period=coverage,
            )

            # Apply intent override
            if item_intent == "must_stock" and status in ("no_data", "out_of_stock"):
                status = "urgent"
                if suggested_qty is None:
                    suggested_qty = must_stock_fallback_qty(lead_time + coverage)
            elif item_intent == "do_not_reorder":
                status = "no_data"
                suggested_qty = None

            stockout_date = None
            if days_to_so is not None and days_to_so > 0:
                stockout_date = date.today() + timedelta(days=int(days_to_so))

            # Update sku_metrics
            cur.execute(
                "UPDATE sku_metrics SET safety_buffer = %s, reorder_status = %s, "
                "reorder_qty_suggested = %s, days_to_stockout = %s, "
                "estimated_stockout_date = %s, computed_at = NOW() "
                "WHERE stock_item_name = %s",
                (new_buffer, status, suggested_qty, days_to_so,
                 stockout_date, stock_item_name),
            )
        conn.commit()

    return {
        "name": stock_item_name,
        "use_xyz_buffer": req.use_xyz_buffer,
        "safety_buffer": new_buffer,
        "reorder_status": status,
        "reorder_qty_suggested": suggested_qty,
    }


@router.get("/brands/{category_name}/skus/{stock_item_name}/positions")
def get_positions(
    category_name: str,
    stock_item_name: str,
    from_date: str = Query(None),
    to_date: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """Daily stock position data for charting."""
    if from_date:
        try:
            date.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(400, f"Invalid from_date format: {from_date}. Use YYYY-MM-DD.")
    if to_date:
        try:
            date.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(400, f"Invalid to_date format: {to_date}. Use YYYY-MM-DD.")

    conditions = ["stock_item_name = %s"]
    params = [stock_item_name]

    if from_date:
        conditions.append("position_date >= %s")
        params.append(from_date)
    if to_date:
        conditions.append("position_date <= %s")
        params.append(to_date)

    where = " AND ".join(conditions)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT position_date, opening_qty, closing_qty, inward_qty, outward_qty,
                       wholesale_out, online_out, store_out, is_in_stock
                FROM daily_stock_positions
                WHERE {where}
                ORDER BY position_date
            """, params)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/brands/{category_name}/skus/{stock_item_name}/transactions")
def get_transactions(
    category_name: str,
    stock_item_name: str,
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    """Transaction history for a specific SKU."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT txn_date,
                       ABS(stock_change) AS quantity,
                       (txn_type = 'IN') AS is_inward,
                       channel,
                       entity AS voucher_type,
                       sale_order_code,
                       entity_code AS voucher_number,
                       facility,
                       entity_type
                FROM transactions
                WHERE stock_item_name = %s
                ORDER BY txn_date DESC, id DESC
                LIMIT %s
            """, (stock_item_name, limit))
            rows = cur.fetchall()

    # Also include KG shipping package demand
    kg_rows = []
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT txn_date, quantity, FALSE AS is_inward, channel,
                       'SHIPPING_PACKAGE' AS voucher_type,
                       NULL AS sale_order_code,
                       shipping_package_code AS voucher_number,
                       'PPETPLKALAGHODA' AS facility,
                       'KG_DISPATCH' AS entity_type
                FROM kg_demand
                WHERE stock_item_name = %s
                ORDER BY txn_date DESC
                LIMIT %s
            """, (stock_item_name, limit))
            kg_rows = cur.fetchall()

    # Merge and sort
    all_txns = [dict(r) for r in rows] + [dict(r) for r in kg_rows]
    all_txns.sort(key=lambda x: x['txn_date'], reverse=True)
    return all_txns[:limit]


# Channel explanation mapping
_CHANNEL_EXPLANATIONS = {
    ("wholesale", False): "Wholesale sales — counted as demand",
    ("wholesale", True): "Wholesale return/credit — not demand",
    ("online", False): "Online sales — counted as demand",
    ("online", True): "Online return/credit — not demand",
    ("store", False): "Store sales — counted as demand",
    ("store", True): "Store return/credit — not demand",
    ("supplier", True): "Purchase replenishment — not demand",
    ("supplier", False): "Supplier return — not demand",
    ("ignore", True): "Physical stock adjustment — affects balance only",
    ("ignore", False): "Physical stock adjustment — affects balance only",
    ("internal", True): "Internal transfer — excluded from balance and demand",
    ("internal", False): "Internal transfer — excluded from balance and demand",
}

# Channels where outward sales count as demand
_DEMAND_CHANNELS = {"wholesale", "online", "store"}



@router.get("/brands/{category_name}/skus/{stock_item_name}/breakdown")
def get_breakdown(
    category_name: str,
    stock_item_name: str,
    from_date: str = Query(None),
    to_date: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """Full calculation breakdown for a single SKU — ground-up transparency."""
    # Resolve date range
    range_start, range_end = resolve_date_range(from_date, to_date)

    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. Closing balance + XYZ pref from stock_items
            cur.execute(
                "SELECT closing_balance, use_xyz_buffer FROM stock_items WHERE name = %s",
                (stock_item_name,),
            )
            si_row = cur.fetchone()
            closing_balance = float(si_row["closing_balance"]) if si_row else None
            item_xyz_pref = si_row["use_xyz_buffer"] if si_row else None

            # 2. Computed_at, current_stock, and safety_buffer from sku_metrics
            cur.execute(
                "SELECT current_stock, computed_at, safety_buffer FROM sku_metrics WHERE stock_item_name = %s",
                (stock_item_name,),
            )
            sm_row = cur.fetchone()
            current_stock = float(sm_row["current_stock"]) if sm_row else 0.0
            computed_at = sm_row["computed_at"].isoformat() if sm_row and sm_row["computed_at"] else None
            buffer_multiplier = float(sm_row["safety_buffer"]) if sm_row and sm_row["safety_buffer"] else 1.3

            # 3. Global XYZ buffer setting
            cur.execute("SELECT value FROM app_settings WHERE key = 'use_xyz_buffer'")
            global_row = cur.fetchone()
            global_xyz = global_row["value"].lower() == 'true' if global_row else False
            effective_use_xyz = item_xyz_pref if item_xyz_pref is not None else global_xyz
            buffer_mode = "abc_xyz" if effective_use_xyz else "abc_only"

            # 3. Daily positions in range
            cur.execute("""
                SELECT position_date, opening_qty, closing_qty, inward_qty, outward_qty,
                       wholesale_out, online_out, store_out, is_in_stock
                FROM daily_stock_positions
                WHERE stock_item_name = %s AND position_date >= %s AND position_date <= %s
                ORDER BY position_date
            """, (stock_item_name, range_start, range_end))
            positions = [dict(r) for r in cur.fetchall()]
            # Convert Decimals to float
            for p in positions:
                for k in ("opening_qty", "closing_qty", "inward_qty", "outward_qty",
                          "wholesale_out", "online_out", "store_out"):
                    p[k] = float(p[k])

            # Determine effective analysis end from actual position data
            if positions:
                data_as_of = positions[-1]["position_date"]
                range_end_effective = min(range_end, data_as_of)
            else:
                data_as_of = None
                range_end_effective = range_end
            total_days = (range_end_effective - range_start).days + 1

            # 4. Transaction summary grouped by channel + direction
            cur.execute("""
                SELECT channel, (txn_type = 'IN') AS is_inward,
                       COUNT(*) AS cnt,
                       SUM(ABS(stock_change)) AS total_qty
                FROM transactions
                WHERE stock_item_name = %s
                  AND txn_date >= %s AND txn_date <= %s
                GROUP BY channel, (txn_type = 'IN')
                ORDER BY channel, (txn_type = 'IN')
            """, (stock_item_name, range_start, range_end))
            txn_groups = [dict(r) for r in cur.fetchall()]

            # 5. Supplier lookup
            cur.execute("""
                SELECT name, lead_time_default, lead_time_sea, lead_time_air,
                       buffer_override, typical_order_months, lead_time_demand_mode
                FROM suppliers
                WHERE UPPER(name) = UPPER(%s)
                LIMIT 1
            """, (category_name,))
            supplier_row = cur.fetchone()

            # 6. Active overrides for this SKU
            cur.execute("""
                SELECT id, field_name, override_value, note, hold_from_po,
                       is_stale, stale_since, computed_value_at_creation,
                       computed_value_latest, drift_pct, created_at, created_by
                FROM overrides
                WHERE stock_item_name = %s AND is_active = TRUE
            """, (stock_item_name,))
            active_overrides_rows = [dict(r) for r in cur.fetchall()]

    # Index overrides by field_name
    overrides_by_field = {}
    for ovr in active_overrides_rows:
        overrides_by_field[ovr["field_name"]] = {
            "id": ovr["id"],
            "value": float(ovr["override_value"]) if ovr["override_value"] is not None else None,
            "note": ovr["note"],
            "hold_from_po": ovr["hold_from_po"],
            "is_stale": ovr["is_stale"],
            "stale_since": ovr["stale_since"].isoformat() if ovr["stale_since"] else None,
            "computed_at_creation": float(ovr["computed_value_at_creation"]) if ovr["computed_value_at_creation"] is not None else None,
            "computed_latest": float(ovr["computed_value_latest"]) if ovr["computed_value_latest"] is not None else None,
            "drift_pct": float(ovr["drift_pct"]) if ovr["drift_pct"] is not None else None,
            "created_at": ovr["created_at"].isoformat() if ovr["created_at"] else None,
            "created_by": ovr["created_by"],
        }

    # --- Build response sections ---

    # Data Source
    data_source = {
        "closing_balance_from_ledger": closing_balance,
        "last_computed": computed_at,
        "data_as_of": data_as_of.isoformat() if data_as_of else None,
        "fy_period": f"Apr 1, {FY_START_DATE.year} — Mar 31, {FY_END_DATE.year}",
        "overrides": overrides_by_field,
    }

    # Position Reconstruction
    total_inward = sum(p["inward_qty"] for p in positions)
    total_outward = sum(p["outward_qty"] for p in positions)
    implied_opening = (closing_balance or 0) - total_inward + total_outward
    position_reconstruction = {
        "implied_opening": round(implied_opening, 2),
        "total_inward": round(total_inward, 2),
        "total_outward": round(total_outward, 2),
        "closing_balance": closing_balance,
        "formula": f"{round(implied_opening, 2)} (implied opening) + {round(total_inward, 2)} (total in) - {round(total_outward, 2)} (total out) = {closing_balance} (closing balance)",
    }

    # Transaction Summary — one row per channel+direction (no merging)
    txn_summary = []
    for g in txn_groups:
        ch = g["channel"] or "unclassified"
        is_in = g["is_inward"]
        qty = round(float(g["total_qty"]), 2)
        included = ch in _DEMAND_CHANNELS and not is_in
        explanation = _CHANNEL_EXPLANATIONS.get((ch, is_in), f"{ch} transactions")

        txn_summary.append({
            "channel": ch,
            "direction": "inward" if is_in else "outward",
            "count": g["cnt"],
            "total_qty": qty,
            "included_in_demand": included,
            "explanation": explanation,
        })

    # Date Range
    date_range = {
        "from_date": range_start.isoformat(),
        "to_date": range_end_effective.isoformat(),
        "total_days_in_range": total_days,
    }

    # Velocity
    vel = calculate_velocity(stock_item_name, positions)
    in_stock_periods = find_in_stock_periods(positions)
    in_stock_count = vel["total_in_stock_days"]
    oos_count = total_days - in_stock_count

    # Per-channel totals from in-stock days only
    in_stock_positions = [p for p in positions if p["is_in_stock"]]
    wholesale_total = sum(p["wholesale_out"] for p in in_stock_positions)
    online_total = sum(p["online_out"] for p in in_stock_positions)
    store_total = sum(p["store_out"] for p in in_stock_positions)
    demand_total = wholesale_total + online_total + store_total

    total_vel = float(vel["total_velocity"])
    wholesale_vel = float(vel["wholesale_velocity"])
    online_vel = float(vel["online_velocity"])
    store_vel = round(store_total / in_stock_count, 4) if in_stock_count > 0 else 0

    # Confidence
    if in_stock_count >= 90:
        confidence = "high"
        confidence_reason = f"Based on {in_stock_count} active days of data (high = >90 days)"
    elif in_stock_count >= 30:
        confidence = "medium"
        confidence_reason = f"Based on {in_stock_count} active days of data (medium = 30-90 days)"
    else:
        confidence = "low"
        confidence_reason = f"Based on {in_stock_count} active days of data (low = <30 days)"

    periods_json = [
        {"from": p["from"].isoformat(), "to": p["to"].isoformat(), "days": p["days"]}
        for p in in_stock_periods
    ]

    velocity_section = {
        "in_stock_days": in_stock_count,
        "out_of_stock_days": oos_count,
        "in_stock_pct": round(in_stock_count / total_days * 100, 1) if total_days > 0 else 0,
        "in_stock_periods": periods_json,
        "out_of_stock_exclusion_reason": "Days with no stock and no sales are excluded — if a sale happened, the item was on the shelf regardless of book balance. Only truly inactive days (no stock, no demand) are excluded to avoid undercounting the demand rate.",
        "wholesale": {
            "total_units": round(wholesale_total, 2),
            "daily_velocity": wholesale_vel,
            "monthly_velocity": round(wholesale_vel * 30, 2),
        },
        "online": {
            "total_units": round(online_total, 2),
            "daily_velocity": online_vel,
            "monthly_velocity": round(online_vel * 30, 2),
        },
        "store": {
            "total_units": round(store_total, 2),
            "daily_velocity": store_vel,
            "monthly_velocity": round(store_vel * 30, 2),
        },
        "total": {
            "total_units": round(demand_total, 2),
            "daily_velocity": total_vel,
            "monthly_velocity": round(total_vel * 30, 2),
        },
        "formula": f"{round(demand_total, 2)} units sold during {in_stock_count} active days = {total_vel} units/day = {round(total_vel * 30, 2)} units/month" if in_stock_count > 0 else "No active days — velocity cannot be calculated",
        "confidence": confidence,
        "confidence_reason": confidence_reason,
    }

    # Compute effective values (override layer)
    def _ovr_val(field):
        o = overrides_by_field.get(field)
        return o["value"] if o else None

    eff = compute_effective_values(
        current_stock, wholesale_vel, online_vel, total_vel,
        stock_ovr=_ovr_val("current_stock"),
        wholesale_ovr=_ovr_val("wholesale_velocity"),
        online_ovr=_ovr_val("online_velocity"),
        store_ovr=_ovr_val("store_velocity"),
        total_ovr=_ovr_val("total_velocity"),
    )
    eff_stock = eff["eff_stock"]
    eff_total_vel = eff["eff_total"]

    effective_values = {
        "current_stock": eff_stock,
        "stock_source": "override" if eff["has_stock_override"] else "computed",
        "total_velocity": eff_total_vel,
        "velocity_source": "override" if eff["has_velocity_override"] else "computed",
        "wholesale_velocity": eff["eff_wholesale"],
        "online_velocity": eff["eff_online"],
        "store_velocity": eff["eff_store"],
    }

    # Stockout — uses effective values
    days_to_so = calculate_days_to_stockout(eff_stock, eff_total_vel)
    stockout_date = None
    if days_to_so is not None and days_to_so > 0:
        stockout_date = (date.today() + timedelta(days=int(days_to_so))).isoformat()

    stockout_section = {
        "current_stock": eff_stock,
        "daily_burn_rate": eff_total_vel,
        "days_to_stockout": days_to_so,
        "estimated_stockout_date": stockout_date,
        "formula": f"{eff_stock} units / {eff_total_vel} units per day = {days_to_so} days" if days_to_so and eff_total_vel > 0 else ("Already out of stock" if eff_stock <= 0 else "No demand data — stockout cannot be estimated"),
    }

    # Reorder — uses effective values
    supplier_name = supplier_row["name"] if supplier_row else None
    lead_time = supplier_row["lead_time_default"] if supplier_row else DEFAULT_LEAD_TIME
    typical_months = supplier_row["typical_order_months"] if supplier_row else None
    supplier_demand_mode_bd = (supplier_row["lead_time_demand_mode"] or "full") if supplier_row else "full"
    include_lead_demand_bd = supplier_demand_mode_bd != "coverage_only"
    coverage_days = compute_coverage_days(lead_time, typical_months)
    total_coverage = lead_time + coverage_days

    status, suggested_qty = determine_reorder_status(
        eff_stock, days_to_so, lead_time, eff_total_vel,
        safety_buffer=buffer_multiplier, coverage_period=coverage_days,
        include_lead_demand=include_lead_demand_bd,
    )
    warning_buffer = max(30, int(lead_time * 0.5))
    threshold_warning = lead_time + warning_buffer

    if eff_total_vel > 0:
        order_for_coverage = round(eff_total_vel * coverage_days * buffer_multiplier, 1)
        if include_lead_demand_bd:
            demand_during_lead = round(eff_total_vel * lead_time, 1)  # NO buffer on lead
            target = round(demand_during_lead + order_for_coverage, 1)
            total_days = lead_time + coverage_days
            reorder_formula = (
                f"Target stock       = {target} units  (enough for {total_days} days: {lead_time}d wait + {coverage_days}d coverage)\n"
                f"  ├─ Wait period   = {demand_during_lead} units  ({lead_time} days × {eff_total_vel}/day)\n"
                f"  └─ Post-arrival  = {order_for_coverage} units  ({coverage_days} days × {eff_total_vel}/day × {buffer_multiplier}x buffer)\n"
                f"Already have       = {eff_stock} units\n"
                f"─────────────────\n"
                f"Order qty          = {target} − {eff_stock} = {suggested_qty} units"
            )
        else:
            reorder_formula = (
                f"Target stock       = {order_for_coverage} units  (enough for {coverage_days}d coverage, wait period excluded)\n"
                f"  └─ Post-arrival  = {order_for_coverage} units  ({coverage_days} days × {eff_total_vel}/day × {buffer_multiplier}x buffer)\n"
                f"Already have       = {eff_stock} units\n"
                f"─────────────────\n"
                f"Order qty          = {order_for_coverage} − {eff_stock} = {suggested_qty} units"
            )
    else:
        reorder_formula = "No demand data — suggested quantity cannot be calculated"

    if days_to_so is not None:
        days_str = str(days_to_so)
        if status == "healthy":
            status_reason = f"{days_str} days remaining > lead time ({lead_time}d) + 30d buffer = {threshold_warning}d threshold"
        elif status == "reorder":
            status_reason = f"{days_str} days remaining <= {threshold_warning}d threshold (lead time + 30d buffer)"
        elif status == "urgent":
            status_reason = f"{days_str} days remaining <= {lead_time}d lead time"
        elif status == "out_of_stock":
            status_reason = "Current stock is zero or negative"
        else:
            status_reason = "Insufficient data to determine status"
    else:
        if status == "out_of_stock":
            status_reason = "Current stock is zero or negative"
        else:
            status_reason = "No demand data available"

    reorder_section = {
        "supplier_name": supplier_name,
        "supplier_lead_time": lead_time,
        "buffer_multiplier": buffer_multiplier,
        "buffer_mode": buffer_mode,
        "use_xyz_buffer": item_xyz_pref,
        "suggested_qty": suggested_qty,
        "formula": reorder_formula,
        "status": status,
        "status_reason": status_reason,
        "status_thresholds": f"urgent: <={lead_time}d | reorder: <={threshold_warning}d | healthy: >{threshold_warning}d | coverage: {coverage_days}d",
        "coverage_days": coverage_days,
        "total_coverage": total_coverage,
        "coverage_source": f"{typical_months} months" if typical_months else "auto",
    }

    return {
        "stock_item_name": stock_item_name,
        "data_source": data_source,
        "effective_values": effective_values,
        "position_reconstruction": position_reconstruction,
        "transaction_summary": txn_summary,
        "date_range": date_range,
        "velocity": velocity_section,
        "stockout": stockout_section,
        "reorder": reorder_section,
    }
