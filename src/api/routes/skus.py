"""SKU detail API endpoints."""
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from api.database import get_db
from engine.velocity import (
    calculate_velocity, find_in_stock_periods,
    resolve_date_range, fetch_batch_velocities, velocities_from_batch_row, opt_float,
)
from engine.reorder import calculate_days_to_stockout, determine_reorder_status, DEFAULT_LEAD_TIME
from engine.effective_values import compute_effective_values, compute_effective_status
from config.settings import FY_START_DATE, FY_END_DATE

router = APIRouter(tags=["skus"])

ALLOWED_SORT_COLS = {
    "days_to_stockout", "total_velocity", "current_stock",
    "stock_item_name", "reorder_status", "wholesale_velocity", "online_velocity",
}


@router.get("/brands/{category_name}/skus")
def list_skus(
    category_name: str,
    status: str = Query(None, description="Comma-separated: critical,warning,ok,out_of_stock,no_data"),
    min_velocity: float = Query(None),
    sort: str = Query("days_to_stockout"),
    sort_dir: str = Query("asc"),
    search: str = Query(None),
    hazardous: bool = Query(None, description="Filter by hazardous flag"),
    from_date: str = Query(None, description="Analysis period start (YYYY-MM-DD)"),
    to_date: str = Query(None, description="Analysis period end (YYYY-MM-DD)"),
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
        conditions.append("sm.stock_item_name ILIKE %s")
        params.append(f"%{search}%")

    if hazardous is not None:
        conditions.append("COALESCE(si.is_hazardous, FALSE) = %s")
        params.append(hazardous)

    where = " AND ".join(conditions)

    # Sanitize sort column
    sort_col = sort if sort in ALLOWED_SORT_COLS else "days_to_stockout"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    sql = f"""
        SELECT sm.*,
               si.part_no,
               si.is_hazardous,
               os.override_value AS stock_override_value,
               os.note AS stock_override_note,
               os.is_stale AS stock_override_stale,
               os.hold_from_po AS stock_hold_from_po,
               ov.override_value AS total_vel_override_value,
               ov.is_stale AS total_vel_override_stale,
               owv.override_value AS wholesale_vel_override_value,
               oov.override_value AS online_vel_override_value,
               osv.override_value AS store_vel_override_value,
               on2.note AS override_note,
               on2.is_stale AS note_override_stale,
               COALESCE(os.hold_from_po, ov.hold_from_po,
                        owv.hold_from_po, oov.hold_from_po,
                        osv.hold_from_po, FALSE) AS hold_from_po
        FROM sku_metrics sm
        LEFT JOIN stock_items si ON si.tally_name = sm.stock_item_name
        LEFT JOIN overrides os  ON os.stock_item_name = sm.stock_item_name AND os.field_name = 'current_stock' AND os.is_active = TRUE
        LEFT JOIN overrides ov  ON ov.stock_item_name = sm.stock_item_name AND ov.field_name = 'total_velocity' AND ov.is_active = TRUE
        LEFT JOIN overrides owv ON owv.stock_item_name = sm.stock_item_name AND owv.field_name = 'wholesale_velocity' AND owv.is_active = TRUE
        LEFT JOIN overrides oov ON oov.stock_item_name = sm.stock_item_name AND oov.field_name = 'online_velocity' AND oov.is_active = TRUE
        LEFT JOIN overrides osv ON osv.stock_item_name = sm.stock_item_name AND osv.field_name = 'store_velocity' AND osv.is_active = TRUE
        LEFT JOIN overrides on2 ON on2.stock_item_name = sm.stock_item_name AND on2.field_name = 'note' AND on2.is_active = TRUE
        WHERE {where}
        ORDER BY sm.{sort_col} {direction} NULLS LAST
    """

    with get_db() as conn:
        with conn.cursor() as cur:
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
                vel_by_sku = fetch_batch_velocities(cur, category_name, range_start, range_end)

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
        st = compute_effective_status(vals["eff_stock"], vals["eff_total"], lead_time)

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

    return results


class HazardousUpdate(BaseModel):
    is_hazardous: bool


@router.patch("/skus/{stock_item_name}/hazardous")
def toggle_hazardous(stock_item_name: str, req: HazardousUpdate):
    """Toggle hazardous flag on a stock item."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE stock_items SET is_hazardous = %s, updated_at = NOW() WHERE tally_name = %s RETURNING tally_name, is_hazardous",
                (req.is_hazardous, stock_item_name),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Stock item not found")
        conn.commit()
    return dict(row)


@router.get("/brands/{category_name}/skus/{stock_item_name}/positions")
def get_positions(
    category_name: str,
    stock_item_name: str,
    from_date: str = Query(None),
    to_date: str = Query(None),
):
    """Daily stock position data for charting."""
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
):
    """Transaction history for a specific SKU."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT txn_date, quantity, is_inward, channel, voucher_type,
                       party_name, rate, amount, voucher_number
                FROM transactions
                WHERE stock_item_name = %s
                ORDER BY txn_date DESC, id DESC
                LIMIT %s
            """, (stock_item_name, limit))
            rows = cur.fetchall()
    return [dict(r) for r in rows]


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
):
    """Full calculation breakdown for a single SKU — ground-up transparency."""
    # Resolve date range
    range_start, range_end = resolve_date_range(from_date, to_date)

    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. Closing balance from Tally (stock_items table)
            cur.execute(
                "SELECT closing_balance FROM stock_items WHERE tally_name = %s",
                (stock_item_name,),
            )
            si_row = cur.fetchone()
            closing_balance_tally = float(si_row["closing_balance"]) if si_row else None

            # 2. Computed_at and current_stock from sku_metrics
            cur.execute(
                "SELECT current_stock, computed_at FROM sku_metrics WHERE stock_item_name = %s",
                (stock_item_name,),
            )
            sm_row = cur.fetchone()
            current_stock = float(sm_row["current_stock"]) if sm_row else 0.0
            computed_at = sm_row["computed_at"].isoformat() if sm_row and sm_row["computed_at"] else None

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
                SELECT channel, is_inward,
                       COUNT(*) AS cnt,
                       SUM(quantity) AS total_qty
                FROM transactions
                WHERE stock_item_name = %s
                  AND txn_date >= %s AND txn_date <= %s
                GROUP BY channel, is_inward
                ORDER BY channel, is_inward
            """, (stock_item_name, range_start, range_end))
            txn_groups = [dict(r) for r in cur.fetchall()]

            # 5. Supplier lookup
            cur.execute("""
                SELECT name, lead_time_default, lead_time_sea, lead_time_air
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
        "closing_balance_from_tally": closing_balance_tally,
        "last_computed": computed_at,
        "data_as_of": data_as_of.isoformat() if data_as_of else None,
        "fy_period": f"Apr 1, {FY_START_DATE.year} — Mar 31, {FY_END_DATE.year}",
        "overrides": overrides_by_field,
    }

    # Position Reconstruction
    total_inward = sum(p["inward_qty"] for p in positions)
    total_outward = sum(p["outward_qty"] for p in positions)
    implied_opening = (closing_balance_tally or 0) - total_inward + total_outward
    position_reconstruction = {
        "implied_opening": round(implied_opening, 2),
        "total_inward": round(total_inward, 2),
        "total_outward": round(total_outward, 2),
        "closing_balance": closing_balance_tally,
        "formula": f"{round(implied_opening, 2)} (implied opening) + {round(total_inward, 2)} (total in) - {round(total_outward, 2)} (total out) = {closing_balance_tally} (closing from Tally)",
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
        confidence_reason = f"Based on {in_stock_count} in-stock days of data (high = >90 days)"
    elif in_stock_count >= 30:
        confidence = "medium"
        confidence_reason = f"Based on {in_stock_count} in-stock days of data (medium = 30-90 days)"
    else:
        confidence = "low"
        confidence_reason = f"Based on {in_stock_count} in-stock days of data (low = <30 days)"

    periods_json = [
        {"from": p["from"].isoformat(), "to": p["to"].isoformat(), "days": p["days"]}
        for p in in_stock_periods
    ]

    velocity_section = {
        "in_stock_days": in_stock_count,
        "out_of_stock_days": oos_count,
        "in_stock_pct": round(in_stock_count / total_days * 100, 1) if total_days > 0 else 0,
        "in_stock_periods": periods_json,
        "out_of_stock_exclusion_reason": "Days with zero stock are excluded because unmet demand is invisible — including them would undercount the true demand rate",
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
        "formula": f"{round(demand_total, 2)} units sold during {in_stock_count} in-stock days = {total_vel} units/day = {round(total_vel * 30, 2)} units/month" if in_stock_count > 0 else "No in-stock days — velocity cannot be calculated",
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
    status, suggested_qty = determine_reorder_status(eff_stock, days_to_so, lead_time, eff_total_vel)
    buffer_multiplier = 1.3
    threshold_warning = lead_time + 30

    if eff_total_vel > 0:
        reorder_formula = f"{eff_total_vel} units/day x {lead_time} days lead time x {buffer_multiplier} safety buffer = {round(eff_total_vel * lead_time * buffer_multiplier, 1)} -> {suggested_qty} units"
    else:
        reorder_formula = "No demand data — suggested quantity cannot be calculated"

    if days_to_so is not None:
        days_str = str(days_to_so)
        if status == "ok":
            status_reason = f"{days_str} days remaining > lead time ({lead_time}d) + 30d buffer = {threshold_warning}d threshold"
        elif status == "warning":
            status_reason = f"{days_str} days remaining <= {threshold_warning}d threshold (lead time + 30d buffer)"
        elif status == "critical":
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
        "suggested_qty": suggested_qty,
        "formula": reorder_formula,
        "status": status,
        "status_reason": status_reason,
        "status_thresholds": f"critical: <={lead_time}d | warning: <={threshold_warning}d | ok: >{threshold_warning}d",
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
