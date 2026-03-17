"""
Lightweight recalculation of safety buffers, reorder status, and brand rollups.
Called when buffer settings change in the UI — no Tally sync needed.
"""
from decimal import Decimal
from datetime import date, timedelta
from collections import defaultdict

import psycopg2.extras

from engine.classification import compute_safety_buffer
from engine.reorder import calculate_days_to_stockout, compute_coverage_days, determine_reorder_status, must_stock_fallback_qty, DEFAULT_LEAD_TIME
from engine.aggregation import compute_brand_metrics
from engine.pipeline import batch_upsert_brand_metrics


def _to_float(val) -> float:
    """Convert Decimal/None to float."""
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


def recalculate_all_buffers(db_conn):
    """Recalculate safety_buffer, reorder_status, and reorder_qty for all SKUs,
    then update brand rollups. Uses current app_settings values.

    Designed for RealDictCursor connections (API database pool)."""

    # ── Fetch settings ──
    buffer_settings = {}
    with db_conn.cursor() as cur:
        cur.execute("SELECT key, value FROM app_settings WHERE key LIKE 'buffer_%%'")
        for row in cur.fetchall():
            try:
                buffer_settings[row["key"]] = float(row["value"])
            except (ValueError, TypeError):
                pass

    with db_conn.cursor() as cur:
        cur.execute("SELECT value FROM app_settings WHERE key = 'use_xyz_buffer'")
        row = cur.fetchone()
        use_xyz_global = row["value"].lower() == "true" if row else False

    # Fetch dead stock / slow mover thresholds
    with db_conn.cursor() as cur:
        cur.execute("SELECT key, value FROM app_settings WHERE key IN ('dead_stock_threshold_days', 'slow_mover_velocity_threshold')")
        threshold_settings = {row["key"]: row["value"] for row in cur.fetchall()}
    dead_stock_threshold = int(threshold_settings.get("dead_stock_threshold_days", "30"))
    slow_mover_threshold = float(threshold_settings.get("slow_mover_velocity_threshold", "0.1"))

    # ── Fetch supplier lead times ──
    supplier_map = {}
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT sc.tally_name AS category_name,
                   s.name, s.lead_time_default, s.lead_time_sea, s.lead_time_air,
                   s.buffer_override, s.typical_order_months
            FROM stock_categories sc
            JOIN suppliers s ON UPPER(s.name) = UPPER(sc.tally_name)
        """)
        for row in cur.fetchall():
            supplier_map[row["category_name"]] = {
                "name": row["name"],
                "lead_time_default": row["lead_time_default"],
                "lead_time_sea": row["lead_time_sea"],
                "lead_time_air": row["lead_time_air"],
                "buffer_override": float(row["buffer_override"]) if row["buffer_override"] is not None else None,
                "typical_order_months": row["typical_order_months"],
            }

    today = date.today()

    # ── Fetch all SKU metrics + per-item prefs ──
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT m.stock_item_name, m.category_name,
                   m.current_stock, m.total_velocity,
                   m.abc_class, m.xyz_class,
                   si.use_xyz_buffer AS item_xyz_pref,
                   si.reorder_intent
            FROM sku_metrics m
            LEFT JOIN stock_items si ON si.tally_name = m.stock_item_name
        """)
        rows = cur.fetchall()

    # ── Recompute for each SKU ──
    updates = []
    for row in rows:
        abc = row["abc_class"]
        xyz = row["xyz_class"]
        item_xyz_pref = row["item_xyz_pref"]
        use_xyz = item_xyz_pref if item_xyz_pref is not None else use_xyz_global

        buf = compute_safety_buffer(abc, xyz, buffer_settings, use_xyz=use_xyz)

        # Apply per-brand buffer override if set
        supplier = supplier_map.get(row["category_name"])
        if supplier and supplier.get("buffer_override") is not None:
            buf = supplier["buffer_override"]

        current_stock = _to_float(row["current_stock"])
        total_vel = _to_float(row["total_velocity"])
        lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME
        coverage = compute_coverage_days(
            lead_time, supplier.get("typical_order_months") if supplier else None
        )
        days_to_stockout = calculate_days_to_stockout(current_stock, total_vel)

        status, suggested_qty = determine_reorder_status(
            current_stock, days_to_stockout, lead_time, total_vel,
            safety_buffer=buf, coverage_period=coverage,
        )

        # Apply reorder intent overrides
        intent = row["reorder_intent"] or "normal"
        if intent == "must_stock" and status in ("no_data", "out_of_stock"):
            status = "critical"
            if suggested_qty is None:
                suggested_qty = must_stock_fallback_qty(lead_time + coverage)
        elif intent == "do_not_reorder":
            status = "no_data"
            suggested_qty = None

        est_date = None
        if days_to_stockout is not None and days_to_stockout > 0:
            est_date = today + timedelta(days=int(days_to_stockout))

        updates.append((
            buf, status, suggested_qty, days_to_stockout, est_date,
            row["stock_item_name"],
        ))

    # ── Batch update sku_metrics ──
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, """
            UPDATE sku_metrics
            SET safety_buffer = %s,
                reorder_status = %s,
                reorder_qty_suggested = %s,
                days_to_stockout = %s,
                estimated_stockout_date = %s
            WHERE stock_item_name = %s
        """, updates, page_size=1000)
    db_conn.commit()

    # ── Recompute brand rollups ──
    # Fetch ALL sku_metrics in one query and group by category in Python
    NUMERIC_COLS = {"current_stock", "wholesale_velocity", "online_velocity",
                    "total_velocity", "days_to_stockout", "reorder_qty_suggested",
                    "total_revenue", "safety_buffer"}

    by_category = defaultdict(list)
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT sm.stock_item_name, sm.category_name,
                   sm.current_stock, sm.wholesale_velocity, sm.online_velocity,
                   sm.total_velocity, sm.total_in_stock_days, sm.days_to_stockout, sm.reorder_status,
                   sm.reorder_qty_suggested, sm.last_sale_date, sm.abc_class, sm.xyz_class,
                   sm.total_revenue, sm.safety_buffer,
                   si.reorder_intent, si.is_active
            FROM sku_metrics sm
            JOIN stock_items si ON si.tally_name = sm.stock_item_name
        """)
        for r in cur.fetchall():
            d = dict(r)
            for c in NUMERIC_COLS:
                if d.get(c) is not None:
                    d[c] = float(d[c])
            by_category[d["category_name"]].append(d)

    # Also fetch categories with no SKUs so they get zero-count rollups
    with db_conn.cursor() as cur:
        cur.execute("SELECT tally_name FROM stock_categories ORDER BY tally_name")
        all_categories = [row["tally_name"] for row in cur.fetchall()]

    brand_batch = []
    for cat_name in all_categories:
        sku_rows = by_category.get(cat_name, [])
        supplier = supplier_map.get(cat_name)
        brand_data = compute_brand_metrics(
            cat_name, sku_rows, supplier,
            dead_stock_threshold=dead_stock_threshold,
            slow_mover_threshold=slow_mover_threshold,
            today=today,
        )
        brand_batch.append(brand_data)

    batch_upsert_brand_metrics(db_conn, brand_batch)
    db_conn.commit()

    return len(updates)
