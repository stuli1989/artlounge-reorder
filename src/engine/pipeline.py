"""
Full computation pipeline for ledger-based data.

Recomputes stock positions, velocity, classification, reorder status,
and brand rollups from transaction ledger data.

No snapshots. No backward reconstruction. No Physical Stock workarounds.
"""
from collections import defaultdict
from datetime import date, timedelta

import psycopg2.extras

from engine.stock_position import (
    build_daily_positions_from_snapshots_and_txns,
    upsert_daily_positions,
)
from engine.velocity import (
    calculate_velocity,
    fetch_batch_wma_velocities,
    velocities_from_batch_row,
    detect_trend,
    MIN_SAMPLE_DAYS,
)
from engine.reorder import (
    calculate_days_to_stockout,
    compute_coverage_days,
    detect_import_history,
    determine_reorder_status,
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


def identify_changed_items(db_conn) -> set[str]:
    """Find items with new transactions since last pipeline run."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT stock_item_name FROM transactions
            WHERE created_at > (SELECT COALESCE(MAX(computed_at), '1970-01-01') FROM sku_metrics)
        """)
        return {row[0] for row in cur.fetchall()}


def run_computation_pipeline(db_conn, incremental=False, phases=None, scope=None):
    """Recompute all derived metrics from raw data.

    If incremental=True, only recomputes items with new transactions.
    ABC/XYZ classification always runs for all items (relative ranking).

    phases: optional set/list of phase numbers to run (1-6).
        1=positions, 2=flat velocity, 3=ABC/XYZ, 4=WMA+trend,
        5=buffer+reorder, 6=rollups.
        None = run all phases.
    scope: optional dict with 'sku' or 'brand' key to limit processing.
    """
    from config.settings import FY_START_DATE

    fy_start = FY_START_DATE
    today = date.today()

    # Determine which items to process
    changed_items = None
    if incremental:
        changed_items = identify_changed_items(db_conn)
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT name FROM stock_items
                WHERE name NOT IN (SELECT stock_item_name FROM sku_metrics)
            """)
            new_items = {row[0] for row in cur.fetchall()}
        changed_items = changed_items | new_items
        if not changed_items:
            print("  No changed items — skipping position reconstruction.")
        else:
            print(f"  Incremental: {len(changed_items)} items changed since last run.")

    # 1. Get all stock items
    all_stock_items = fetch_all_stock_items(db_conn)
    active_items = [i for i in all_stock_items if i.get("is_active", True)]
    inactive_count = len(all_stock_items) - len(active_items)
    print(f"  {len(active_items)} active items ({inactive_count} inactive skipped).")

    # Apply scope filter
    if scope:
        if scope.get("sku"):
            active_items = [i for i in active_items if i["name"] == scope["sku"]]
        elif scope.get("brand"):
            active_items = [i for i in active_items if i["category_name"] == scope["brand"]]

    if incremental and changed_items is not None:
        items_to_process = [i for i in active_items if i["name"] in changed_items]
    else:
        items_to_process = active_items

    # Pre-fetch settings
    dead_stock_threshold = _fetch_setting(db_conn, 'dead_stock_threshold_days', 90, int)
    slow_mover_threshold = _fetch_setting(db_conn, 'slow_mover_velocity_threshold', 0.1, float)
    class_settings = fetch_classification_settings(db_conn)
    buffer_settings = fetch_buffer_settings(db_conn)
    use_xyz_global = fetch_use_xyz_global(db_conn)

    # Pre-fetch ALL transactions in one query (avoids N+1)
    all_txns = fetch_all_transactions(db_conn)
    print(f"  Loaded transactions for {len(all_txns)} items in bulk.")

    # Pre-fetch current stock from latest daily_stock_positions
    current_stock_map = fetch_current_stock_from_positions(db_conn)
    print(f"  Loaded current stock for {len(current_stock_map)} items from positions.")

    # Pre-compute supplier mapping per category
    supplier_map = fetch_all_supplier_mappings(db_conn)
    print(f"  Loaded supplier mappings for {len(supplier_map)} categories.")

    # Pre-fetch MRP lookup for ABC classification
    mrp_lookup = fetch_mrp_lookup(db_conn)
    print(f"  Loaded MRP data for {len(mrp_lookup)} items.")

    # ── Phase 1+2: Rebuild positions + flat velocity ──
    processed = 0
    metrics_batch = []
    daily_positions_by_sku = {}

    if phases is None or 1 in phases or 2 in phases:
        for i, item in enumerate(items_to_process):
            sku_name = item["name"]
            txns = all_txns.get(sku_name, [])

            # Get current stock from positions (or fallback to closing_balance)
            current_stock = current_stock_map.get(
                sku_name, item.get("closing_balance", 0) or 0
            )

            if not txns:
                metrics_batch.append(_empty_metrics(sku_name, item["category_name"], current_stock))
                continue

            if phases is None or 1 in phases:
                # Build daily positions from transactions (no snapshots)
                positions = build_daily_positions_from_snapshots_and_txns(
                    stock_item_name=sku_name,
                    snapshot_by_date={},
                    transactions=txns,
                    start_date=fy_start,
                    end_date=today,
                )
                upsert_daily_positions(db_conn, positions)
            else:
                # Load existing positions from DB
                positions = _fetch_daily_positions_bulk(db_conn, [sku_name]).get(sku_name, [])
                if not positions:
                    metrics_batch.append(_empty_metrics(sku_name, item["category_name"], current_stock))
                    continue

            daily_positions_by_sku[sku_name] = positions

            # Calculate flat velocity
            velocity = calculate_velocity(sku_name, positions)

            # Dead stock metrics
            last_sale_date = compute_last_sale_date(txns)
            zero_activity_days = compute_zero_activity_days(positions)
            total_in_stock_days = velocity["total_in_stock_days"]
            zero_activity_ratio = (
                round(zero_activity_days / total_in_stock_days, 4)
                if total_in_stock_days > 0 else None
            )

            # Import history
            import_history = detect_import_history(sku_name, txns)

            # Supplier lead time
            supplier = supplier_map.get(item["category_name"])
            lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME
            coverage = compute_coverage_days(
                lead_time,
                supplier["typical_order_months"] if supplier else None,
            )

            # Days to stockout (using flat velocity initially)
            days_to_stockout = calculate_days_to_stockout(current_stock, velocity["total_velocity"])

            # Reorder status (preliminary — recomputed after classification)
            intent = item.get("reorder_intent", "normal")
            status, suggested_qty = determine_reorder_status(
                current_stock, days_to_stockout, lead_time, velocity["total_velocity"],
                coverage_period=coverage, reorder_intent=intent,
            )

            # Estimated stockout date (cap at 3650 days to avoid overflow)
            stockout_date = None
            if days_to_stockout is not None and days_to_stockout > 0:
                capped_days = min(int(days_to_stockout), 3650)
                stockout_date = today + timedelta(days=capped_days)

            m = {
                "stock_item_name": sku_name,
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
                "zero_activity_ratio": zero_activity_ratio,
            }
            metrics_batch.append(m)

            processed += 1
            if (i + 1) % 500 == 0:
                db_conn.commit()
                print(f"  Processed {i + 1}/{len(items_to_process)} items...")

        # Add inactive items with minimal metrics
        for item in all_stock_items:
            if not item.get("is_active", True):
                current_stock = current_stock_map.get(
                    item["name"], item.get("closing_balance", 0) or 0
                )
                metrics_batch.append(_empty_metrics(item["name"], item["category_name"], current_stock))

        db_conn.commit()
        print(f"  {processed} items with data computed.")

        # Refresh current_stock_map from freshly-built positions
        fresh_stock_map = fetch_current_stock_from_positions(db_conn)
        if fresh_stock_map:
            print(f"  Refreshed current stock for {len(fresh_stock_map)} items from positions.")
            for m in metrics_batch:
                sku = m["stock_item_name"]
                if sku in fresh_stock_map:
                    m["current_stock"] = fresh_stock_map[sku]

    # If we skipped phase 1+2, load existing metrics for classification phases
    if not metrics_batch and (phases is not None and 1 not in phases and 2 not in phases):
        metrics_batch = _load_existing_metrics(db_conn, items_to_process, all_stock_items)

    # ── Phase 3: ABC/XYZ classification (always full set) ──
    if phases is None or 3 in phases:
        print("  Computing ABC classification...")
        compute_abc_classification(
            metrics_batch, all_txns,
            a_threshold=class_settings["abc_a_threshold"],
            b_threshold=class_settings["abc_b_threshold"],
            mrp_lookup=mrp_lookup,
        )

        print("  Computing XYZ classification...")
        if incremental and changed_items:
            unchanged_skus = [m["stock_item_name"] for m in metrics_batch
                              if m["stock_item_name"] not in daily_positions_by_sku]
            if unchanged_skus:
                loaded = _fetch_daily_positions_bulk(db_conn, unchanged_skus)
                daily_positions_by_sku.update(loaded)
        compute_xyz_classification(metrics_batch, daily_positions_by_sku)

    # ── Phase 4: WMA velocity + trend detection ──
    if phases is None or 4 in phases:
        print("  Computing WMA velocities and trends...")
        sku_names_with_velocity = [m["stock_item_name"] for m in metrics_batch if m.get("total_velocity", 0) > 0]
        wma_window = int(class_settings.get("wma_window_days", 90))

        wma_by_sku = {}
        if sku_names_with_velocity:
            with db_conn.cursor() as cur:
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

    # ── Phase 5: Safety buffers + reorder recomputation ──
    if phases is None or 5 in phases:
        print("  Computing safety buffers and final reorder status...")
        stock_items_by_name = {item["name"]: item for item in all_stock_items}
        for m in metrics_batch:
            abc = m.get("abc_class")
            xyz = m.get("xyz_class")
            item_data = stock_items_by_name.get(m["stock_item_name"], {})

            # Safety buffer: supplier override is a MULTIPLIER (F14)
            supplier = supplier_map.get(m["category_name"])
            supplier_buf_override = None
            if supplier and supplier.get("buffer_override") is not None:
                supplier_buf_override = supplier["buffer_override"]

            buf = compute_safety_buffer(abc, xyz, buffer_settings,
                                         supplier_override=supplier_buf_override,
                                         use_xyz=use_xyz_global)
            m["safety_buffer"] = buf

            # Recompute reorder with final safety buffer
            current_stock = m["current_stock"]
            total_vel = m["total_velocity"]
            lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME
            coverage = compute_coverage_days(
                lead_time,
                supplier["typical_order_months"] if supplier else None,
            )
            days_to_stockout = calculate_days_to_stockout(current_stock, total_vel)

            intent = item_data.get("reorder_intent", "normal")
            status, suggested_qty = determine_reorder_status(
                current_stock, days_to_stockout, lead_time, total_vel,
                safety_buffer=buf, coverage_period=coverage,
                reorder_intent=intent,
            )

            m["days_to_stockout"] = days_to_stockout
            m["reorder_status"] = status
            m["reorder_qty_suggested"] = suggested_qty
            if days_to_stockout is not None and days_to_stockout > 0:
                capped_days = min(int(days_to_stockout), 3650)
                m["estimated_stockout_date"] = today + timedelta(days=capped_days)
            else:
                m["estimated_stockout_date"] = None

    # ── Batch upsert ──
    print(f"  Batch-upserting {len(metrics_batch)} SKU metrics...")
    batch_upsert_sku_metrics(db_conn, metrics_batch)
    db_conn.commit()

    # ── Phase 6: Brand rollups ──
    if phases is None or 6 in phases:
        print("  Computing brand rollups...")
        categories = fetch_all_categories(db_conn)

        brand_batch = []
        for cat in categories:
            sku_metrics = fetch_sku_metrics_for_category(db_conn, cat["name"])
            supplier = supplier_map.get(cat["name"])
            brand_data = compute_brand_metrics(
                cat["name"], sku_metrics, supplier,
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
            SELECT name, sku_code, category_name, opening_balance, closing_balance,
                   reorder_intent, is_active
            FROM stock_items
            ORDER BY category_name, name
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
    """Read all transactions, mapped to pipeline dict format."""
    result = defaultdict(list)
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT stock_item_name, txn_date, stock_change, txn_type,
                   entity, entity_type, channel, is_demand, facility
            FROM transactions ORDER BY stock_item_name, txn_date
        """)
        for row in cur.fetchall():
            result[row[0]].append({
                "date": row[1],
                "quantity": float(abs(row[2])),
                "is_inward": row[3] == "IN",
                "channel": row[6],
                "return_type": "CIR" if row[4] == "PUTAWAY_CIR"
                          else "RTO" if row[4] == "PUTAWAY_RTO" else None,
                "voucher_type": row[4],
                "entity": row[4],
                "entity_type": row[5],
                "is_demand": row[7],
                "facility": row[8],
                "amount": None,
            })
    return dict(result)


def fetch_current_stock_from_positions(db_conn) -> dict[str, float]:
    """Get latest closing_qty per SKU from daily_stock_positions."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (stock_item_name)
                stock_item_name, closing_qty
            FROM daily_stock_positions
            ORDER BY stock_item_name, position_date DESC
        """)
        return {row[0]: float(row[1]) for row in cur.fetchall()}


def fetch_mrp_lookup(db_conn) -> dict[str, float]:
    """Load MRP per SKU for ABC revenue calculation."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT sku_code, COALESCE(mrp, 0) FROM stock_items WHERE mrp IS NOT NULL")
        return {row[0]: float(row[1]) for row in cur.fetchall()}


def fetch_all_supplier_mappings(db_conn) -> dict[str, dict]:
    """Pre-compute supplier info for all categories."""
    mapping = {}
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT sc.name AS category_name,
                   s.name, s.lead_time_default, s.lead_time_sea, s.lead_time_air,
                   s.buffer_override, s.typical_order_months
            FROM stock_categories sc
            JOIN suppliers s ON UPPER(s.name) = UPPER(sc.name)
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
        cur.execute("SELECT name FROM stock_categories ORDER BY name")
        return [{"name": row[0]} for row in cur.fetchall()]


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
            JOIN stock_items si ON si.name = sm.stock_item_name
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
    """Load daily positions from DB for a list of SKUs."""
    result = defaultdict(list)
    if not sku_names:
        return dict(result)
    with db_conn.cursor() as cur:
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


def _load_existing_metrics(db_conn, items_to_process, all_stock_items):
    """Load existing sku_metrics when skipping early phases."""
    metrics_batch = []
    sku_names = [i["name"] for i in items_to_process]
    # Also include inactive items
    for item in all_stock_items:
        if not item.get("is_active", True):
            sku_names.append(item["name"])
    if not sku_names:
        return metrics_batch
    with db_conn.cursor() as cur:
        for batch_start in range(0, len(sku_names), 5000):
            batch = sku_names[batch_start:batch_start + 5000]
            cur.execute("""
                SELECT stock_item_name, category_name, current_stock,
                       wholesale_velocity, online_velocity, total_velocity,
                       total_in_stock_days, velocity_start_date, velocity_end_date,
                       days_to_stockout, estimated_stockout_date,
                       last_import_date, last_import_qty, last_import_supplier,
                       reorder_status, reorder_qty_suggested,
                       last_sale_date, total_zero_activity_days,
                       abc_class, xyz_class, demand_cv, total_revenue,
                       wma_wholesale_velocity, wma_online_velocity, wma_total_velocity,
                       trend_direction, trend_ratio, safety_buffer,
                       zero_activity_ratio, min_sample_met
                FROM sku_metrics WHERE stock_item_name = ANY(%s)
            """, (batch,))
            cols = [desc[0] for desc in cur.description]
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                # Convert Decimals to float
                for k in ("current_stock", "wholesale_velocity", "online_velocity",
                           "total_velocity", "days_to_stockout", "reorder_qty_suggested",
                           "total_revenue", "safety_buffer", "demand_cv", "trend_ratio",
                           "wma_wholesale_velocity", "wma_online_velocity", "wma_total_velocity",
                           "zero_activity_ratio"):
                    if d.get(k) is not None:
                        d[k] = float(d[k])
                metrics_batch.append(d)
    return metrics_batch


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
        zero_activity_ratio, min_sample_met,
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
        %(zero_activity_ratio)s, %(min_sample_met)s,
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
        zero_activity_ratio = EXCLUDED.zero_activity_ratio,
        min_sample_met = EXCLUDED.min_sample_met,
        computed_at = NOW()
"""

_SKU_METRICS_DEFAULTS = {
    "wholesale_velocity": 0, "online_velocity": 0, "total_velocity": 0,
    "total_in_stock_days": 0, "velocity_start_date": None, "velocity_end_date": None,
    "days_to_stockout": None, "estimated_stockout_date": None,
    "last_import_date": None, "last_import_qty": None, "last_import_supplier": None,
    "reorder_status": "out_of_stock", "reorder_qty_suggested": None,
    "last_sale_date": None, "total_zero_activity_days": 0,
    "abc_class": "C", "xyz_class": None, "demand_cv": None, "total_revenue": 0,
    "wma_wholesale_velocity": 0, "wma_online_velocity": 0, "wma_total_velocity": 0,
    "trend_direction": "flat", "trend_ratio": None, "safety_buffer": 1.3,
    "zero_activity_ratio": None, "min_sample_met": True,
}

_BRAND_METRICS_UPSERT_SQL = """
    INSERT INTO brand_metrics (
        category_name, total_skus, in_stock_skus, out_of_stock_skus,
        critical_skus, warning_skus, ok_skus, no_data_skus,
        stocked_out_skus, no_demand_skus,
        dead_stock_skus, slow_mover_skus, avg_days_to_stockout, min_days_to_stockout,
        primary_supplier, supplier_lead_time,
        a_class_skus, b_class_skus, c_class_skus, inactive_skus,
        computed_at
    ) VALUES (
        %(category_name)s, %(total_skus)s, %(in_stock_skus)s, %(out_of_stock_skus)s,
        %(critical_skus)s, %(warning_skus)s, %(ok_skus)s, %(no_data_skus)s,
        %(stocked_out_skus)s, %(no_demand_skus)s,
        %(dead_stock_skus)s, %(slow_mover_skus)s, %(avg_days_to_stockout)s, %(min_days_to_stockout)s,
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
        stocked_out_skus = EXCLUDED.stocked_out_skus,
        no_demand_skus = EXCLUDED.no_demand_skus,
        dead_stock_skus = EXCLUDED.dead_stock_skus,
        slow_mover_skus = EXCLUDED.slow_mover_skus,
        avg_days_to_stockout = EXCLUDED.avg_days_to_stockout,
        min_days_to_stockout = EXCLUDED.min_days_to_stockout,
        primary_supplier = EXCLUDED.primary_supplier,
        supplier_lead_time = EXCLUDED.supplier_lead_time,
        a_class_skus = EXCLUDED.a_class_skus,
        b_class_skus = EXCLUDED.b_class_skus,
        c_class_skus = EXCLUDED.c_class_skus,
        inactive_skus = EXCLUDED.inactive_skus,
        computed_at = NOW()
"""


def batch_upsert_sku_metrics(db_conn, metrics_list: list[dict]):
    """Batch upsert SKU metrics."""
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


def compute_last_sale_date(transactions: list[dict]):
    """F21: Find the most recent demand dispatch date."""
    last = None
    for t in transactions:
        if (t.get("channel") in _DEMAND_CHANNELS and not t.get("is_inward")):
            d = t.get("date") or t.get("txn_date")
            if d is not None and (last is None or d > last):
                last = d
    return last


def compute_zero_activity_days(positions: list[dict]) -> int:
    """F22: Count days where item had stock but zero movement."""
    count = 0
    for p in positions:
        if (p.get("closing_qty", 0) > 0
                and p.get("inward_qty", 0) == 0
                and p.get("outward_qty", 0) == 0):
            count += 1
    return count


def _empty_metrics(sku_name: str, category_name: str, current_stock: float) -> dict:
    """Return empty metrics dict for items with no data."""
    status = "out_of_stock" if current_stock <= 0 else "no_demand"
    return {
        "stock_item_name": sku_name,
        "category_name": category_name,
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
        "reorder_status": status,
        "reorder_qty_suggested": None,
        "last_sale_date": None,
        "total_zero_activity_days": 0,
        "zero_activity_ratio": None,
        "min_sample_met": False,
    }


def _fetch_setting(db_conn, key: str, default, cast=str):
    """Read a single key from app_settings with type casting."""
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
            row = cur.fetchone()
            return cast(row[0]) if row else default
    except Exception:
        return default
