"""
Full computation pipeline — reconstructs stock positions, calculates velocity,
determines reorder status, and rolls up to brand level.

V2 additions: ABC/XYZ classification, WMA velocity, trend detection, variable
safety buffers, incremental computation.
"""
from datetime import date, timedelta

import psycopg2.extras

from engine.stock_position import (
    reconstruct_daily_positions,
    upsert_daily_positions,
    fetch_transactions_for_item,
)
from engine.velocity import (
    calculate_velocity,
    fetch_batch_wma_velocities,
    velocities_from_batch_row,
    detect_trend,
)
from engine.reorder import (
    calculate_days_to_stockout,
    compute_coverage_days,
    detect_import_history,
    determine_reorder_status,
    get_supplier_for_category,
    must_stock_fallback_qty,
    DEFAULT_LEAD_TIME,
)
from engine.aggregation import compute_brand_metrics
from engine.classification import (
    compute_abc_classification,
    compute_xyz_classification,
    compute_safety_buffer,
    fetch_buffer_settings,
    fetch_classification_settings,
    fetch_use_xyz_global,
)
from engine.backdate_physical_stock import adjust_opening_for_physical_stock


def identify_changed_items(db_conn) -> set[str]:
    """Find items with new transactions since last pipeline run."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT stock_item_name FROM transactions
            WHERE created_at > (SELECT COALESCE(MAX(computed_at), '1970-01-01') FROM sku_metrics)
        """)
        return {row[0] for row in cur.fetchall()}


def run_computation_pipeline(db_conn, incremental=False):
    """Recompute all derived metrics from raw transaction data.

    If incremental=True, only recomputes items with new transactions.
    ABC/XYZ classification always runs for all items (relative ranking).
    """
    from config.settings import FY_START_DATE

    fy_start = FY_START_DATE
    today = date.today()

    # Determine which items to process
    changed_items = None
    if incremental:
        changed_items = identify_changed_items(db_conn)
        # Also include items with no sku_metrics row
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT tally_name FROM stock_items
                WHERE tally_name NOT IN (SELECT stock_item_name FROM sku_metrics)
            """)
            new_items = {row[0] for row in cur.fetchall()}
        changed_items = changed_items | new_items
        if not changed_items:
            print("  No changed items — skipping position reconstruction.")
        else:
            print(f"  Incremental: {len(changed_items)} items changed since last run.")

    # 1. Get all stock items (filter inactive for position reconstruction)
    all_stock_items = fetch_all_stock_items(db_conn)
    active_items = [i for i in all_stock_items if i.get("is_active", True)]
    inactive_count = len(all_stock_items) - len(active_items)
    print(f"  {len(active_items)} active items ({inactive_count} inactive skipped for reconstruction).")

    # Determine which items need position reconstruction
    if incremental and changed_items is not None:
        items_to_process = [i for i in active_items if i["tally_name"] in changed_items]
    else:
        items_to_process = active_items

    # Pre-fetch thresholds
    dead_stock_threshold = _fetch_dead_stock_threshold(db_conn)
    slow_mover_threshold = _fetch_slow_mover_threshold(db_conn)
    class_settings = fetch_classification_settings(db_conn)
    buffer_settings = fetch_buffer_settings(db_conn)
    use_xyz_global = fetch_use_xyz_global(db_conn)

    # Pre-fetch backdate Physical Stock settings
    backdate_enabled_global = _fetch_setting(db_conn, 'backdate_physical_stock', 'false', str) == 'true'
    backdate_grace_days_global = _fetch_setting(db_conn, 'physical_stock_grace_days', 90, int)

    # Pre-fetch per-supplier backdate overrides, joining through stock_categories
    # for consistent keying (same join as fetch_all_supplier_mappings)
    backdate_overrides = {}
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT sc.tally_name AS category_name,
                   s.backdate_physical_stock, s.physical_stock_grace_days
            FROM stock_categories sc
            JOIN suppliers s ON UPPER(s.name) = UPPER(sc.tally_name)
            WHERE s.backdate_physical_stock IS NOT NULL
               OR s.physical_stock_grace_days IS NOT NULL
        """)
        for row in cur.fetchall():
            backdate_overrides[row[0].upper()] = {
                "enabled": row[1],
                "grace_days": row[2],
            }
    if backdate_enabled_global:
        print(f"  Backdate Physical Stock: ON (grace={backdate_grace_days_global}d, {len(backdate_overrides)} brand overrides)")

    # Pre-fetch ALL transactions in one query (avoids N+1)
    all_txns = fetch_all_transactions(db_conn)
    print(f"  Loaded transactions for {len(all_txns)} items in bulk.")

    # Pre-compute supplier mapping per category (avoids N+1)
    supplier_map = fetch_all_supplier_mappings(db_conn)
    print(f"  Loaded supplier mappings for {len(supplier_map)} categories.")

    # ── Phase 1: Position reconstruction + flat velocity ──
    processed = 0
    metrics_batch = []  # Collect for batch upsert
    daily_positions_by_sku = {}  # For XYZ classification

    # Process items needing reconstruction
    for i, item in enumerate(items_to_process):
        txns = all_txns.get(item["tally_name"], [])
        current_stock = item["closing_balance"] or 0

        if not txns:
            metrics_batch.append({
                "stock_item_name": item["tally_name"],
                "category_name": item["category_name"],
                "current_stock": current_stock,
                "wholesale_velocity": 0,
                "online_velocity": 0,
                "total_velocity": 0,
                "total_in_stock_days": 0,
                "velocity_start_date": None,
                "velocity_end_date": None,
                "days_to_stockout": None,
                "estimated_stockout_date": None,
                "last_import_date": None,
                "last_import_qty": None,
                "last_import_supplier": None,
                "reorder_status": "out_of_stock" if current_stock <= 0 else "no_data",
                "reorder_qty_suggested": None,
                "last_sale_date": None,
                "total_zero_activity_days": 0,
            })
            continue

        # Apply backdate Physical Stock preprocessing
        category = item["category_name"].upper() if item.get("category_name") else ""
        ovr = backdate_overrides.get(category, {})
        bd_enabled = ovr.get("enabled") if ovr.get("enabled") is not None else backdate_enabled_global
        bd_grace = ovr.get("grace_days") if ovr.get("grace_days") is not None else backdate_grace_days_global

        effective_opening = item["opening_balance"]
        effective_txns = txns
        if bd_enabled:
            effective_opening, effective_txns = adjust_opening_for_physical_stock(
                opening_balance=item["opening_balance"] or 0,
                transactions=txns,
                fy_start=fy_start,
                grace_days=bd_grace,
            )

        # Reconstruct daily positions
        positions = reconstruct_daily_positions(
            stock_item_name=item["tally_name"],
            closing_balance=current_stock,
            opening_date=fy_start,
            transactions=effective_txns,
            end_date=today,
            tally_opening=effective_opening,
        )

        # Save positions
        upsert_daily_positions(db_conn, positions)
        daily_positions_by_sku[item["tally_name"]] = positions

        # Calculate flat velocity
        velocity = calculate_velocity(item["tally_name"], positions)

        # Dead stock metrics
        last_sale_date = compute_last_sale_date(txns)
        opening_gap = (item["opening_balance"] or 0) - positions[0]["opening_qty"] if positions else 0.0
        zero_activity_days = compute_zero_activity_days(positions, opening_gap)

        # Import history
        import_history = detect_import_history(item["tally_name"], txns)

        # Supplier lead time
        supplier = supplier_map.get(item["category_name"])
        lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME
        coverage = compute_coverage_days(
            lead_time,
            supplier["typical_order_months"] if supplier else None,
        )

        # Days to stockout (using flat velocity initially — will be updated after classification)
        days_to_stockout = calculate_days_to_stockout(current_stock, velocity["total_velocity"])

        # Reorder status (preliminary — will be recomputed with safety buffer)
        status, suggested_qty = determine_reorder_status(
            current_stock, days_to_stockout, lead_time, velocity["total_velocity"],
            coverage_period=coverage,
        )

        # Intent-based override
        intent = item.get("reorder_intent", "normal")
        if intent == "must_stock" and status in ("no_data", "out_of_stock"):
            status = "critical"
            if suggested_qty is None:
                suggested_qty = must_stock_fallback_qty(lead_time + coverage)
        elif intent == "do_not_reorder":
            status = "no_data"
            suggested_qty = None

        # Estimated stockout date
        stockout_date = None
        if days_to_stockout is not None and days_to_stockout > 0:
            stockout_date = today + timedelta(days=int(days_to_stockout))

        m = {
            "stock_item_name": item["tally_name"],
            "category_name": item["category_name"],
            "current_stock": current_stock,
            **velocity,
            "days_to_stockout": days_to_stockout,
            "estimated_stockout_date": stockout_date,
            "last_import_date": import_history.get("last_import_date"),
            "last_import_qty": import_history.get("last_import_qty"),
            "last_import_supplier": import_history.get("last_import_supplier"),
            "reorder_status": status,
            "reorder_qty_suggested": suggested_qty,
            "last_sale_date": last_sale_date,
            "total_zero_activity_days": zero_activity_days,
        }
        metrics_batch.append(m)

        processed += 1
        if (i + 1) % 500 == 0:
            db_conn.commit()
            print(f"  Processed {i + 1}/{len(items_to_process)} items...")

    # Add inactive items with minimal metrics
    for item in all_stock_items:
        if not item.get("is_active", True):
            current_stock = item["closing_balance"] or 0
            metrics_batch.append({
                "stock_item_name": item["tally_name"],
                "category_name": item["category_name"],
                "current_stock": current_stock,
                "wholesale_velocity": 0,
                "online_velocity": 0,
                "total_velocity": 0,
                "total_in_stock_days": 0,
                "velocity_start_date": None,
                "velocity_end_date": None,
                "days_to_stockout": None,
                "estimated_stockout_date": None,
                "last_import_date": None,
                "last_import_qty": None,
                "last_import_supplier": None,
                "reorder_status": "out_of_stock" if current_stock <= 0 else "no_data",
                "reorder_qty_suggested": None,
                "last_sale_date": None,
                "total_zero_activity_days": 0,
            })

    db_conn.commit()
    print(f"  {processed} items with transactions computed.")

    # ── Phase 2: ABC/XYZ classification (always full set) ──
    print("  Computing ABC classification...")
    compute_abc_classification(
        metrics_batch, all_txns,
        a_threshold=class_settings["abc_a_threshold"],
        b_threshold=class_settings["abc_b_threshold"],
    )

    print("  Computing XYZ classification...")
    # For incremental: load existing positions for unchanged items
    if incremental and changed_items:
        # XYZ needs daily positions — load from DB for unchanged items
        unchanged_skus = [m["stock_item_name"] for m in metrics_batch
                          if m["stock_item_name"] not in daily_positions_by_sku]
        if unchanged_skus:
            loaded = _fetch_daily_positions_bulk(db_conn, unchanged_skus)
            daily_positions_by_sku.update(loaded)

    compute_xyz_classification(metrics_batch, daily_positions_by_sku)

    # ── Phase 3: WMA velocity + trend detection ──
    print("  Computing WMA velocities and trends...")
    sku_names_with_velocity = [m["stock_item_name"] for m in metrics_batch if m.get("total_velocity", 0) > 0]
    wma_window = int(class_settings.get("wma_window_days", 90))

    wma_by_sku = {}
    if sku_names_with_velocity:
        with db_conn.cursor() as cur:
            # Process in batches of 5000 to avoid oversized queries
            for batch_start in range(0, len(sku_names_with_velocity), 5000):
                batch = sku_names_with_velocity[batch_start:batch_start + 5000]
                batch_result = fetch_batch_wma_velocities(cur, batch, today, wma_window)
                wma_by_sku.update(batch_result)

    trend_up = class_settings.get("trend_up_threshold", 1.2)
    trend_down = class_settings.get("trend_down_threshold", 0.8)

    for m in metrics_batch:
        sku = m["stock_item_name"]
        wma_row = wma_by_sku.get(sku)
        if wma_row:
            wma_w, wma_o, wma_s, wma_t = velocities_from_batch_row(wma_row)
            m["wma_wholesale_velocity"] = round(wma_w, 4)
            m["wma_online_velocity"] = round(wma_o, 4)
            m["wma_total_velocity"] = round(wma_t, 4)
        else:
            m["wma_wholesale_velocity"] = 0
            m["wma_online_velocity"] = 0
            m["wma_total_velocity"] = 0

        flat_total = m.get("total_velocity", 0)
        wma_total = m.get("wma_total_velocity", 0)
        direction, ratio = detect_trend(flat_total, wma_total, trend_up, trend_down)
        m["trend_direction"] = direction
        m["trend_ratio"] = ratio

    # ── Phase 4: Safety buffers + reorder recomputation ──
    print("  Computing safety buffers and final reorder status...")
    stock_items_by_name = {item["tally_name"]: item for item in all_stock_items}
    for m in metrics_batch:
        abc = m.get("abc_class")
        xyz = m.get("xyz_class")
        item_data = stock_items_by_name.get(m["stock_item_name"], {})
        item_xyz_pref = item_data.get("use_xyz_buffer")  # None/True/False
        use_xyz = item_xyz_pref if item_xyz_pref is not None else use_xyz_global
        buf = compute_safety_buffer(abc, xyz, buffer_settings, use_xyz=use_xyz)
        # Apply per-brand buffer override
        supplier = supplier_map.get(m["category_name"])
        if supplier and supplier.get("buffer_override") is not None:
            buf = supplier["buffer_override"]
        m["safety_buffer"] = buf

        # Recompute reorder status with variable safety buffer
        current_stock = m["current_stock"]
        total_vel = m["total_velocity"]
        lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME
        coverage = compute_coverage_days(
            lead_time,
            supplier["typical_order_months"] if supplier else None,
        )
        days_to_stockout = calculate_days_to_stockout(current_stock, total_vel)

        status, suggested_qty = determine_reorder_status(
            current_stock, days_to_stockout, lead_time, total_vel,
            safety_buffer=buf, coverage_period=coverage,
        )

        # Re-apply intent override
        intent = item_data.get("reorder_intent", "normal")
        if intent == "must_stock" and status in ("no_data", "out_of_stock"):
            status = "critical"
            if suggested_qty is None:
                suggested_qty = must_stock_fallback_qty(lead_time + coverage)
        elif intent == "do_not_reorder":
            status = "no_data"
            suggested_qty = None

        m["days_to_stockout"] = days_to_stockout
        m["reorder_status"] = status
        m["reorder_qty_suggested"] = suggested_qty
        if days_to_stockout is not None and days_to_stockout > 0:
            m["estimated_stockout_date"] = today + timedelta(days=int(days_to_stockout))
        else:
            m["estimated_stockout_date"] = None

    # ── Phase 5: Batch upsert ──
    print(f"  Batch-upserting {len(metrics_batch)} SKU metrics...")
    batch_upsert_sku_metrics(db_conn, metrics_batch)
    db_conn.commit()

    # ── Phase 6: Brand rollups ──
    print("  Computing brand rollups...")
    if incremental and changed_items:
        # Only rollup brands that contain changed items
        changed_categories = set()
        for m in metrics_batch:
            if m["stock_item_name"] in changed_items:
                changed_categories.add(m["category_name"])
        categories = [{"tally_name": c} for c in changed_categories]
        # But we also need to re-rollup for ABC distribution changes (all brands)
        # Since ABC is always full, just do all brands
        categories = fetch_all_categories(db_conn)
    else:
        categories = fetch_all_categories(db_conn)

    brand_batch = []
    for cat in categories:
        sku_metrics = fetch_sku_metrics_for_category(db_conn, cat["tally_name"])
        supplier = supplier_map.get(cat["tally_name"])
        brand_data = compute_brand_metrics(
            cat["tally_name"], sku_metrics, supplier,
            dead_stock_threshold=dead_stock_threshold,
            slow_mover_threshold=slow_mover_threshold,
            today=today,
        )
        brand_batch.append(brand_data)

    batch_upsert_brand_metrics(db_conn, brand_batch)
    db_conn.commit()
    print("  Computation pipeline complete.")


# ──────────────────────────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────────────────────────

def fetch_all_stock_items(db_conn) -> list[dict]:
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT tally_name, category_name, opening_balance, closing_balance,
                   reorder_intent, is_active, use_xyz_buffer
            FROM stock_items
            ORDER BY category_name, tally_name
        """)
        cols = [d[0] for d in cur.description]
        rows = []
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["opening_balance"] = float(d["opening_balance"] or 0)
            d["closing_balance"] = float(d["closing_balance"] or 0)
            rows.append(d)
        return rows


def fetch_all_transactions(db_conn) -> dict[str, list[dict]]:
    """Fetch ALL transactions in one query, grouped by stock_item_name."""
    from collections import defaultdict
    result = defaultdict(list)
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT stock_item_name, txn_date AS date, quantity, is_inward,
                   channel, voucher_type, party_name, amount, phys_stock_diff
            FROM transactions
            ORDER BY stock_item_name, txn_date, id
        """)
        cols = [desc[0] for desc in cur.description]
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["quantity"] = float(d["quantity"])
            if d.get("phys_stock_diff") is not None:
                d["phys_stock_diff"] = float(d["phys_stock_diff"])
            item_name = d.pop("stock_item_name")
            result[item_name].append(d)
    return dict(result)


def fetch_all_supplier_mappings(db_conn) -> dict[str, dict]:
    """Pre-compute supplier info for all categories."""
    mapping = {}
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT sc.tally_name AS category_name,
                   s.name, s.lead_time_default, s.lead_time_sea, s.lead_time_air,
                   s.buffer_override, s.typical_order_months
            FROM stock_categories sc
            JOIN suppliers s ON UPPER(s.name) = UPPER(sc.tally_name)
        """)
        for row in cur.fetchall():
            mapping[row[0]] = {
                "name": row[1],
                "lead_time_default": row[2],
                "lead_time_sea": row[3],
                "lead_time_air": row[4],
                "buffer_override": float(row[5]) if row[5] is not None else None,
                "typical_order_months": row[6],
            }
    return mapping


def fetch_all_categories(db_conn) -> list[dict]:
    with db_conn.cursor() as cur:
        cur.execute("SELECT tally_name FROM stock_categories ORDER BY tally_name")
        return [{"tally_name": row[0]} for row in cur.fetchall()]


def fetch_sku_metrics_for_category(db_conn, category_name: str) -> list[dict]:
    numeric_cols = {"current_stock", "wholesale_velocity", "online_velocity",
                    "total_velocity", "days_to_stockout", "reorder_qty_suggested",
                    "total_revenue", "safety_buffer"}
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT sm.stock_item_name, sm.current_stock, sm.wholesale_velocity, sm.online_velocity,
                   sm.total_velocity, sm.total_in_stock_days, sm.days_to_stockout, sm.reorder_status,
                   sm.reorder_qty_suggested, sm.last_sale_date, sm.abc_class, sm.xyz_class,
                   sm.total_revenue, sm.safety_buffer,
                   si.reorder_intent, si.is_active
            FROM sku_metrics sm
            JOIN stock_items si ON si.tally_name = sm.stock_item_name
            WHERE sm.category_name = %s
        """, (category_name,))
        cols = [d[0] for d in cur.description]
        rows = []
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            for c in numeric_cols:
                if d.get(c) is not None:
                    d[c] = float(d[c])
            rows.append(d)
        return rows


def _fetch_daily_positions_bulk(db_conn, sku_names: list[str]) -> dict[str, list[dict]]:
    """Load daily positions from DB for a list of SKUs (used by incremental XYZ)."""
    from collections import defaultdict
    result = defaultdict(list)
    if not sku_names:
        return dict(result)
    with db_conn.cursor() as cur:
        # Process in batches
        for batch_start in range(0, len(sku_names), 5000):
            batch = sku_names[batch_start:batch_start + 5000]
            cur.execute("""
                SELECT stock_item_name, position_date, opening_qty, closing_qty,
                       inward_qty, outward_qty, wholesale_out, online_out, store_out, is_in_stock
                FROM daily_stock_positions
                WHERE stock_item_name = ANY(%s)
                ORDER BY stock_item_name, position_date
            """, (batch,))
            cols = [desc[0] for desc in cur.description]
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                for k in ("opening_qty", "closing_qty", "inward_qty", "outward_qty",
                           "wholesale_out", "online_out", "store_out"):
                    d[k] = float(d[k])
                item = d.pop("stock_item_name")
                result[item].append(d)
    return dict(result)


_SKU_METRICS_UPSERT_SQL = """
    INSERT INTO sku_metrics (
        stock_item_name, category_name, current_stock,
        wholesale_velocity, online_velocity, total_velocity,
        total_in_stock_days, velocity_start_date, velocity_end_date,
        days_to_stockout, estimated_stockout_date,
        last_import_date, last_import_qty, last_import_supplier,
        reorder_status, reorder_qty_suggested,
        last_sale_date, total_zero_activity_days,
        abc_class, xyz_class, demand_cv, total_revenue,
        wma_wholesale_velocity, wma_online_velocity, wma_total_velocity,
        trend_direction, trend_ratio, safety_buffer,
        computed_at
    ) VALUES (
        %(stock_item_name)s, %(category_name)s, %(current_stock)s,
        %(wholesale_velocity)s, %(online_velocity)s, %(total_velocity)s,
        %(total_in_stock_days)s, %(velocity_start_date)s, %(velocity_end_date)s,
        %(days_to_stockout)s, %(estimated_stockout_date)s,
        %(last_import_date)s, %(last_import_qty)s, %(last_import_supplier)s,
        %(reorder_status)s, %(reorder_qty_suggested)s,
        %(last_sale_date)s, %(total_zero_activity_days)s,
        %(abc_class)s, %(xyz_class)s, %(demand_cv)s, %(total_revenue)s,
        %(wma_wholesale_velocity)s, %(wma_online_velocity)s, %(wma_total_velocity)s,
        %(trend_direction)s, %(trend_ratio)s, %(safety_buffer)s,
        NOW()
    )
    ON CONFLICT (stock_item_name) DO UPDATE SET
        category_name = EXCLUDED.category_name,
        current_stock = EXCLUDED.current_stock,
        wholesale_velocity = EXCLUDED.wholesale_velocity,
        online_velocity = EXCLUDED.online_velocity,
        total_velocity = EXCLUDED.total_velocity,
        total_in_stock_days = EXCLUDED.total_in_stock_days,
        velocity_start_date = EXCLUDED.velocity_start_date,
        velocity_end_date = EXCLUDED.velocity_end_date,
        days_to_stockout = EXCLUDED.days_to_stockout,
        estimated_stockout_date = EXCLUDED.estimated_stockout_date,
        last_import_date = EXCLUDED.last_import_date,
        last_import_qty = EXCLUDED.last_import_qty,
        last_import_supplier = EXCLUDED.last_import_supplier,
        reorder_status = EXCLUDED.reorder_status,
        reorder_qty_suggested = EXCLUDED.reorder_qty_suggested,
        last_sale_date = EXCLUDED.last_sale_date,
        total_zero_activity_days = EXCLUDED.total_zero_activity_days,
        abc_class = EXCLUDED.abc_class,
        xyz_class = EXCLUDED.xyz_class,
        demand_cv = EXCLUDED.demand_cv,
        total_revenue = EXCLUDED.total_revenue,
        wma_wholesale_velocity = EXCLUDED.wma_wholesale_velocity,
        wma_online_velocity = EXCLUDED.wma_online_velocity,
        wma_total_velocity = EXCLUDED.wma_total_velocity,
        trend_direction = EXCLUDED.trend_direction,
        trend_ratio = EXCLUDED.trend_ratio,
        safety_buffer = EXCLUDED.safety_buffer,
        computed_at = NOW()
"""

_SKU_METRICS_DEFAULTS = {
    "wholesale_velocity": 0, "online_velocity": 0, "total_velocity": 0,
    "total_in_stock_days": 0, "velocity_start_date": None, "velocity_end_date": None,
    "days_to_stockout": None, "estimated_stockout_date": None,
    "last_import_date": None, "last_import_qty": None, "last_import_supplier": None,
    "reorder_status": "no_data", "reorder_qty_suggested": None,
    "last_sale_date": None, "total_zero_activity_days": 0,
    "abc_class": "C", "xyz_class": None, "demand_cv": None, "total_revenue": 0,
    "wma_wholesale_velocity": 0, "wma_online_velocity": 0, "wma_total_velocity": 0,
    "trend_direction": "flat", "trend_ratio": None, "safety_buffer": 1.3,
}

_BRAND_METRICS_UPSERT_SQL = """
    INSERT INTO brand_metrics (
        category_name, total_skus, in_stock_skus, out_of_stock_skus,
        critical_skus, warning_skus, ok_skus, no_data_skus,
        dead_stock_skus, slow_mover_skus, avg_days_to_stockout,
        primary_supplier, supplier_lead_time,
        a_class_skus, b_class_skus, c_class_skus, inactive_skus,
        computed_at
    ) VALUES (
        %(category_name)s, %(total_skus)s, %(in_stock_skus)s, %(out_of_stock_skus)s,
        %(critical_skus)s, %(warning_skus)s, %(ok_skus)s, %(no_data_skus)s,
        %(dead_stock_skus)s, %(slow_mover_skus)s, %(avg_days_to_stockout)s,
        %(primary_supplier)s, %(supplier_lead_time)s,
        %(a_class_skus)s, %(b_class_skus)s, %(c_class_skus)s, %(inactive_skus)s,
        NOW()
    )
    ON CONFLICT (category_name) DO UPDATE SET
        total_skus = EXCLUDED.total_skus,
        in_stock_skus = EXCLUDED.in_stock_skus,
        out_of_stock_skus = EXCLUDED.out_of_stock_skus,
        critical_skus = EXCLUDED.critical_skus,
        warning_skus = EXCLUDED.warning_skus,
        ok_skus = EXCLUDED.ok_skus,
        no_data_skus = EXCLUDED.no_data_skus,
        dead_stock_skus = EXCLUDED.dead_stock_skus,
        slow_mover_skus = EXCLUDED.slow_mover_skus,
        avg_days_to_stockout = EXCLUDED.avg_days_to_stockout,
        primary_supplier = EXCLUDED.primary_supplier,
        supplier_lead_time = EXCLUDED.supplier_lead_time,
        a_class_skus = EXCLUDED.a_class_skus,
        b_class_skus = EXCLUDED.b_class_skus,
        c_class_skus = EXCLUDED.c_class_skus,
        inactive_skus = EXCLUDED.inactive_skus,
        computed_at = NOW()
"""


def batch_upsert_sku_metrics(db_conn, metrics_list: list[dict]):
    """Batch upsert SKU metrics using execute_batch for ~1000x fewer round-trips."""
    if not metrics_list:
        return
    for m in metrics_list:
        for k, v in _SKU_METRICS_DEFAULTS.items():
            m.setdefault(k, v)
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, _SKU_METRICS_UPSERT_SQL, metrics_list, page_size=1000)


def batch_upsert_brand_metrics(db_conn, brand_list: list[dict]):
    """Batch upsert brand metrics."""
    if not brand_list:
        return
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, _BRAND_METRICS_UPSERT_SQL, brand_list, page_size=1000)


# ──────────────────────────────────────────────────────────────────
# Dead stock helpers
# ──────────────────────────────────────────────────────────────────

_DEMAND_CHANNELS = {"wholesale", "online", "store"}
_EXCLUDED_VOUCHER_TYPES = {"Credit Note", "Debit Note"}


def compute_last_sale_date(transactions: list[dict]):
    """Find the most recent demand sale date."""
    last = None
    for t in transactions:
        if (t.get("channel") in _DEMAND_CHANNELS
                and not t.get("is_inward")
                and t.get("voucher_type") not in _EXCLUDED_VOUCHER_TYPES):
            d = t.get("date")
            if d is not None and (last is None or d > last):
                last = d
    return last


def compute_zero_activity_days(positions: list[dict], opening_gap: float = 0.0) -> int:
    """Count days where item had stock but zero inward and outward movement.

    Uses closing_qty directly (backward-reconstructed from Tally's authoritative
    closing balance) without adding opening_gap. The gap represents a one-time
    FY-start discrepancy and should not inflate every day's quantity.
    """
    count = 0
    for p in positions:
        if p.get("closing_qty", 0) > 0 and p.get("inward_qty", 0) == 0 and p.get("outward_qty", 0) == 0:
            count += 1
    return count


def _fetch_setting(db_conn, key: str, default, cast=str):
    """Read a single key from app_settings with type casting."""
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
            row = cur.fetchone()
            return cast(row[0]) if row else default
    except Exception:
        return default


def _fetch_dead_stock_threshold(db_conn) -> int:
    return _fetch_setting(db_conn, 'dead_stock_threshold_days', 30, int)


def _fetch_slow_mover_threshold(db_conn) -> float:
    return _fetch_setting(db_conn, 'slow_mover_velocity_threshold', 0.1, float)
