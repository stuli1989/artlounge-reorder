"""
Full computation pipeline — reconstructs stock positions, calculates velocity,
determines reorder status, and rolls up to brand level.
"""
from datetime import date, timedelta

import psycopg2.extras

from engine.stock_position import (
    reconstruct_daily_positions,
    upsert_daily_positions,
    fetch_transactions_for_item,
)
from engine.velocity import calculate_velocity
from engine.reorder import (
    calculate_days_to_stockout,
    detect_import_history,
    determine_reorder_status,
    get_supplier_for_category,
    must_stock_fallback_qty,
    DEFAULT_LEAD_TIME,
)
from engine.aggregation import compute_brand_metrics


def run_computation_pipeline(db_conn):
    """Recompute all derived metrics from raw transaction data."""
    from config.settings import FY_START_DATE

    fy_start = FY_START_DATE
    today = date.today()

    # 1. Get all stock items
    stock_items = fetch_all_stock_items(db_conn)
    print(f"  Computing metrics for {len(stock_items)} stock items...")

    # Pre-fetch thresholds for brand rollup
    dead_stock_threshold = _fetch_dead_stock_threshold(db_conn)
    slow_mover_threshold = _fetch_slow_mover_threshold(db_conn)

    # Pre-fetch ALL transactions in one query (avoids N+1)
    all_txns = fetch_all_transactions(db_conn)
    print(f"  Loaded transactions for {len(all_txns)} items in bulk.")

    # Pre-compute supplier mapping per category (avoids N+1)
    supplier_map = fetch_all_supplier_mappings(db_conn)
    print(f"  Loaded supplier mappings for {len(supplier_map)} categories.")

    processed = 0
    for i, item in enumerate(stock_items):
        txns = all_txns.get(item["tally_name"], [])

        current_stock = item["closing_balance"] or 0

        if not txns:
            # No transactions — just set status based on stock level
            upsert_sku_metrics(db_conn, {
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

        # Reconstruct daily positions using BACKWARD method (from closing balance)
        positions = reconstruct_daily_positions(
            stock_item_name=item["tally_name"],
            closing_balance=current_stock,
            opening_date=fy_start,
            transactions=txns,
            end_date=today,
        )

        # Save positions (batch for performance)
        upsert_daily_positions(db_conn, positions)

        # Calculate velocity
        velocity = calculate_velocity(item["tally_name"], positions)

        # Dead stock metrics
        last_sale_date = compute_last_sale_date(txns)
        zero_activity_days = compute_zero_activity_days(positions)

        # Import history
        import_history = detect_import_history(item["tally_name"], txns)

        # Supplier lead time (from pre-computed map)
        supplier = supplier_map.get(item["category_name"])
        lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME

        # Days to stockout
        days_to_stockout = calculate_days_to_stockout(current_stock, velocity["total_velocity"])

        # Reorder status
        status, suggested_qty = determine_reorder_status(
            current_stock, days_to_stockout, lead_time, velocity["total_velocity"]
        )

        # Intent-based override (post-processing layer)
        intent = item.get("reorder_intent", "normal")
        if intent == "must_stock" and status in ("no_data", "out_of_stock"):
            status = "critical"
            if suggested_qty is None:
                suggested_qty = must_stock_fallback_qty(lead_time)
        elif intent == "do_not_reorder":
            status = "no_data"
            suggested_qty = None

        # Estimated stockout date
        stockout_date = None
        if days_to_stockout is not None and days_to_stockout > 0:
            stockout_date = today + timedelta(days=int(days_to_stockout))

        # Save SKU metrics
        upsert_sku_metrics(db_conn, {
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
        })

        processed += 1
        if (i + 1) % 500 == 0:
            db_conn.commit()  # Batch commit every 500 items
            print(f"  Processed {i + 1}/{len(stock_items)} items...")

    # Final commit for remaining SKU metrics
    db_conn.commit()
    print(f"  {processed} items with transactions computed.")

    # 3. Brand rollups
    print("  Computing brand rollups...")
    categories = fetch_all_categories(db_conn)
    for cat in categories:
        sku_metrics = fetch_sku_metrics_for_category(db_conn, cat["tally_name"])
        supplier = supplier_map.get(cat["tally_name"])
        brand_data = compute_brand_metrics(
            cat["tally_name"], sku_metrics, supplier,
            dead_stock_threshold=dead_stock_threshold,
            slow_mover_threshold=slow_mover_threshold,
            today=today,
        )
        upsert_brand_metrics(db_conn, brand_data)

    db_conn.commit()  # Single commit for all brand rollups
    print("  Computation pipeline complete.")


# ──────────────────────────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────────────────────────

def fetch_all_stock_items(db_conn) -> list[dict]:
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT tally_name, category_name, opening_balance, closing_balance, reorder_intent
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
                   channel, voucher_type, party_name
            FROM transactions
            ORDER BY stock_item_name, txn_date, id
        """)
        cols = [desc[0] for desc in cur.description]
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["quantity"] = float(d["quantity"])
            item_name = d.pop("stock_item_name")
            result[item_name].append(d)
    return dict(result)


def fetch_all_supplier_mappings(db_conn) -> dict[str, dict]:
    """Pre-compute supplier info for all categories.

    Matches suppliers to categories by name (suppliers are seeded with brand names).
    Falls back to joining through parties/transactions if tally_party is set.
    """
    mapping = {}
    with db_conn.cursor() as cur:
        # Primary: match supplier name to stock_categories name (how suppliers were seeded)
        cur.execute("""
            SELECT sc.tally_name AS category_name,
                   s.name, s.lead_time_default, s.lead_time_sea, s.lead_time_air
            FROM stock_categories sc
            JOIN suppliers s ON UPPER(s.name) = UPPER(sc.tally_name)
        """)
        for row in cur.fetchall():
            mapping[row[0]] = {
                "name": row[1],
                "lead_time_default": row[2],
                "lead_time_sea": row[3],
                "lead_time_air": row[4],
            }
    return mapping


def fetch_all_categories(db_conn) -> list[dict]:
    with db_conn.cursor() as cur:
        cur.execute("SELECT tally_name FROM stock_categories ORDER BY tally_name")
        return [{"tally_name": row[0]} for row in cur.fetchall()]


def fetch_sku_metrics_for_category(db_conn, category_name: str) -> list[dict]:
    numeric_cols = {"current_stock", "wholesale_velocity", "online_velocity",
                    "total_velocity", "days_to_stockout", "reorder_qty_suggested"}
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT sm.stock_item_name, sm.current_stock, sm.wholesale_velocity, sm.online_velocity,
                   sm.total_velocity, sm.total_in_stock_days, sm.days_to_stockout, sm.reorder_status,
                   sm.reorder_qty_suggested, sm.last_sale_date, si.reorder_intent
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


def upsert_sku_metrics(db_conn, m: dict):
    sql = """
        INSERT INTO sku_metrics (
            stock_item_name, category_name, current_stock,
            wholesale_velocity, online_velocity, total_velocity,
            total_in_stock_days, velocity_start_date, velocity_end_date,
            days_to_stockout, estimated_stockout_date,
            last_import_date, last_import_qty, last_import_supplier,
            reorder_status, reorder_qty_suggested,
            last_sale_date, total_zero_activity_days, computed_at
        ) VALUES (
            %(stock_item_name)s, %(category_name)s, %(current_stock)s,
            %(wholesale_velocity)s, %(online_velocity)s, %(total_velocity)s,
            %(total_in_stock_days)s, %(velocity_start_date)s, %(velocity_end_date)s,
            %(days_to_stockout)s, %(estimated_stockout_date)s,
            %(last_import_date)s, %(last_import_qty)s, %(last_import_supplier)s,
            %(reorder_status)s, %(reorder_qty_suggested)s,
            %(last_sale_date)s, %(total_zero_activity_days)s, NOW()
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
            computed_at = NOW()
    """
    # Fill defaults for missing keys
    defaults = {
        "wholesale_velocity": 0, "online_velocity": 0, "total_velocity": 0,
        "total_in_stock_days": 0, "velocity_start_date": None, "velocity_end_date": None,
        "days_to_stockout": None, "estimated_stockout_date": None,
        "last_import_date": None, "last_import_qty": None, "last_import_supplier": None,
        "reorder_status": "no_data", "reorder_qty_suggested": None,
        "last_sale_date": None, "total_zero_activity_days": 0,
    }
    for k, v in defaults.items():
        m.setdefault(k, v)

    with db_conn.cursor() as cur:
        cur.execute(sql, m)


def upsert_brand_metrics(db_conn, m: dict):
    sql = """
        INSERT INTO brand_metrics (
            category_name, total_skus, in_stock_skus, out_of_stock_skus,
            critical_skus, warning_skus, ok_skus, no_data_skus,
            dead_stock_skus, slow_mover_skus, avg_days_to_stockout, primary_supplier, supplier_lead_time, computed_at
        ) VALUES (
            %(category_name)s, %(total_skus)s, %(in_stock_skus)s, %(out_of_stock_skus)s,
            %(critical_skus)s, %(warning_skus)s, %(ok_skus)s, %(no_data_skus)s,
            %(dead_stock_skus)s, %(slow_mover_skus)s, %(avg_days_to_stockout)s, %(primary_supplier)s, %(supplier_lead_time)s, NOW()
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
            computed_at = NOW()
    """
    with db_conn.cursor() as cur:
        cur.execute(sql, m)


# ──────────────────────────────────────────────────────────────────
# Dead stock helpers
# ──────────────────────────────────────────────────────────────────

_DEMAND_CHANNELS = {"wholesale", "online", "store"}
_EXCLUDED_VOUCHER_TYPES = {"Credit Note", "Debit Note"}


def compute_last_sale_date(transactions: list[dict]):
    """Find the most recent demand sale date.

    Considers outward transactions on demand channels (wholesale, online, store),
    excluding Credit Notes and Debit Notes which are adjustments, not sales.
    """
    last = None
    for t in transactions:
        if (t.get("channel") in _DEMAND_CHANNELS
                and not t.get("is_inward")
                and t.get("voucher_type") not in _EXCLUDED_VOUCHER_TYPES):
            d = t.get("date")
            if d is not None and (last is None or d > last):
                last = d
    return last


def compute_zero_activity_days(positions: list[dict]) -> int:
    """Count days where item had stock but zero inward and outward movement."""
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
