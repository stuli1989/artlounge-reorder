"""
Targeted recompute — recomputes positions + metrics for specific SKUs.

Used after party reclassification to immediately update affected SKU metrics
without running the full computation pipeline.

Skips ABC/XYZ classification (relative rankings need all items — updated on next nightly sync).
"""
from collections import defaultdict
from datetime import date, timedelta

from config.settings import FY_START_DATE
from engine.stock_position import (
    build_daily_positions_from_snapshots_and_txns,
    upsert_daily_positions,
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
    DEFAULT_LEAD_TIME,
)
from engine.pipeline import (
    batch_upsert_sku_metrics,
    batch_upsert_brand_metrics,
    fetch_sku_metrics_for_category,
    fetch_current_stock_from_positions,
    compute_last_sale_date,
    compute_zero_activity_days,
    _empty_metrics,
    _fetch_setting,
)
from engine.aggregation import compute_brand_metrics
from engine.classification import (
    compute_safety_buffer,
    fetch_buffer_settings,
    fetch_classification_settings,
    fetch_use_xyz_global,
)


def find_affected_skus(db_conn, party_name: str) -> list[str]:
    """Find all SKUs that have transactions with the given entity."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT stock_item_name FROM transactions WHERE entity = %s",
            (party_name,),
        )
        return [row[0] for row in cur.fetchall()]


def find_affected_categories(db_conn, sku_names: list[str]) -> set[str]:
    """Find category names for the given SKUs."""
    if not sku_names:
        return set()
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT category_name FROM stock_items WHERE name = ANY(%s)",
            (sku_names,),
        )
        return {row[0] for row in cur.fetchall()}


def recompute_skus_for_party(db_conn, party_name: str) -> dict:
    """Recompute positions + metrics for all SKUs affected by a party reclassification."""
    today = date.today()
    fy_start = FY_START_DATE

    sku_names = find_affected_skus(db_conn, party_name)
    if not sku_names:
        return {"skus_recomputed": 0, "brands_recomputed": 0, "affected_skus": []}

    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT name, category_name, opening_balance, closing_balance,
                   reorder_intent, is_active
            FROM stock_items
            WHERE name = ANY(%s)
        """, (sku_names,))
        cols = [d[0] for d in cur.description]
        items = []
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["opening_balance"] = float(d["opening_balance"] or 0)
            d["closing_balance"] = float(d["closing_balance"] or 0)
            items.append(d)

    # Fetch transactions using new ledger schema
    all_txns = defaultdict(list)
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT stock_item_name, txn_date, stock_change, txn_type,
                   entity, entity_type, channel, is_demand, facility
            FROM transactions
            WHERE stock_item_name = ANY(%s)
            ORDER BY stock_item_name, txn_date, id
        """, (sku_names,))
        for row in cur.fetchall():
            all_txns[row[0]].append({
                "date": row[1],
                "quantity": abs(row[2]),
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

    categories = find_affected_categories(db_conn, sku_names)
    supplier_map = {}
    if categories:
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT sc.name AS category_name,
                       s.name, s.lead_time_default, s.lead_time_sea, s.lead_time_air,
                       s.buffer_override, s.typical_order_months
                FROM stock_categories sc
                JOIN suppliers s ON UPPER(s.name) = UPPER(sc.name)
                WHERE sc.name = ANY(%s)
            """, (list(categories),))
            for row in cur.fetchall():
                supplier_map[row[0]] = {
                    "name": row[1],
                    "lead_time_default": row[2],
                    "lead_time_sea": row[3],
                    "lead_time_air": row[4],
                    "buffer_override": float(row[5]) if row[5] is not None else None,
                    "typical_order_months": row[6],
                }

    buffer_settings = fetch_buffer_settings(db_conn)
    class_settings = fetch_classification_settings(db_conn)
    use_xyz_global = fetch_use_xyz_global(db_conn)

    # Get current stock from latest positions
    current_stock_map = fetch_current_stock_from_positions(db_conn)

    metrics_batch = []
    for item in items:
        sku_name = item["name"]
        txns = all_txns.get(sku_name, [])

        current_stock = current_stock_map.get(sku_name, item["closing_balance"])

        if not txns:
            metrics_batch.append(_empty_metrics(sku_name, item["category_name"], current_stock))
            continue

        # Build positions from transactions (no snapshots)
        positions = build_daily_positions_from_snapshots_and_txns(
            stock_item_name=sku_name,
            snapshot_by_date={},
            transactions=txns,
            start_date=fy_start,
            end_date=today,
        )
        upsert_daily_positions(db_conn, positions)

        velocity = calculate_velocity(sku_name, positions)
        last_sale_date = compute_last_sale_date(txns)
        zero_activity_days = compute_zero_activity_days(positions)
        total_in_stock_days = velocity["total_in_stock_days"]
        zero_activity_ratio = (
            round(zero_activity_days / total_in_stock_days, 4)
            if total_in_stock_days > 0 else None
        )

        import_history = detect_import_history(sku_name, txns)

        supplier = supplier_map.get(item["category_name"])
        lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME
        coverage = compute_coverage_days(
            lead_time,
            supplier["typical_order_months"] if supplier else None,
        )

        days_to_stockout = calculate_days_to_stockout(current_stock, velocity["total_velocity"])

        intent = item.get("reorder_intent", "normal")
        status, suggested_qty = determine_reorder_status(
            current_stock, days_to_stockout, lead_time, velocity["total_velocity"],
            coverage_period=coverage, reorder_intent=intent,
        )

        stockout_date = None
        if days_to_stockout is not None and days_to_stockout > 0:
            stockout_date = today + timedelta(days=int(days_to_stockout))

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

    # WMA velocity + trend
    wma_window = int(class_settings.get("wma_window_days", 90))
    trend_up = class_settings.get("trend_up_threshold", 1.2)
    trend_down = class_settings.get("trend_down_threshold", 0.8)

    sku_names_with_velocity = [m["stock_item_name"] for m in metrics_batch if m.get("total_velocity", 0) > 0]
    wma_by_sku = {}
    if sku_names_with_velocity:
        with db_conn.cursor() as cur:
            wma_by_sku = fetch_batch_wma_velocities(cur, sku_names_with_velocity, today, wma_window)

    for m in metrics_batch:
        wma_row = wma_by_sku.get(m["stock_item_name"])
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

    # Safety buffer recomputation (preserve existing ABC/XYZ from DB)
    existing_class = {}
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT stock_item_name, abc_class, xyz_class, demand_cv, total_revenue
            FROM sku_metrics WHERE stock_item_name = ANY(%s)
        """, (sku_names,))
        for row in cur.fetchall():
            existing_class[row[0]] = {
                "abc_class": row[1], "xyz_class": row[2],
                "demand_cv": float(row[3]) if row[3] else None,
                "total_revenue": float(row[4]) if row[4] else 0,
            }

    stock_items_by_name = {item["name"]: item for item in items}
    for m in metrics_batch:
        ec = existing_class.get(m["stock_item_name"], {})
        m["abc_class"] = ec.get("abc_class", "C")
        m["xyz_class"] = ec.get("xyz_class")
        m["demand_cv"] = ec.get("demand_cv")
        m["total_revenue"] = ec.get("total_revenue", 0)

        abc = m["abc_class"]
        xyz = m["xyz_class"]
        supplier = supplier_map.get(m["category_name"])
        supplier_buf_override = None
        if supplier and supplier.get("buffer_override") is not None:
            supplier_buf_override = supplier["buffer_override"]
        buf = compute_safety_buffer(abc, xyz, buffer_settings,
                                     supplier_override=supplier_buf_override,
                                     use_xyz=use_xyz_global)
        m["safety_buffer"] = buf

        # Final reorder status with safety buffer
        current_stock = m["current_stock"]
        total_vel = m["total_velocity"]
        item_data = stock_items_by_name.get(m["stock_item_name"], {})
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
            m["estimated_stockout_date"] = today + timedelta(days=int(days_to_stockout))
        else:
            m["estimated_stockout_date"] = None

    batch_upsert_sku_metrics(db_conn, metrics_batch)
    db_conn.commit()

    dead_stock_threshold = _fetch_setting(db_conn, 'dead_stock_threshold_days', 90, int)
    slow_mover_threshold = _fetch_setting(db_conn, 'slow_mover_velocity_threshold', 0.1, float)
    brand_batch = []
    for cat_name in categories:
        sku_metrics = fetch_sku_metrics_for_category(db_conn, cat_name)
        supplier = supplier_map.get(cat_name)
        brand_data = compute_brand_metrics(
            cat_name, sku_metrics, supplier,
            dead_stock_threshold=dead_stock_threshold,
            slow_mover_threshold=slow_mover_threshold,
            today=today,
        )
        brand_batch.append(brand_data)
    batch_upsert_brand_metrics(db_conn, brand_batch)
    db_conn.commit()

    return {
        "skus_recomputed": len(metrics_batch),
        "brands_recomputed": len(categories),
        "affected_skus": sku_names,
    }
