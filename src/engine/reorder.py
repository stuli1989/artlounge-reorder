"""
Reorder computation for Unicommerce data.

F2:  effective_stock = available_stock (no openPurchase)
F11: days_to_stockout = effective_stock / recent_velocity
F13: coverage_period from turns-per-year logic
F15: reorder_qty — buffer on coverage only, NOT on lead time demand
F16: reorder_status — LOST_SALES, DEAD_STOCK, URGENT, REORDER, HEALTHY statuses
"""
from datetime import date

DEFAULT_LEAD_TIME = 180  # days (sea freight default)


def compute_coverage_days(lead_time: int, typical_order_months: int | None = None) -> int:
    """F13: Compute coverage period in days.

    If typical_order_months is set (per-supplier config), use it directly.
    Otherwise auto-calculate from lead time using turns-per-year logic.
    """
    if typical_order_months is not None:
        return typical_order_months * 30

    fy_days = 365
    turns = min(max(1, fy_days // lead_time), 6)
    return fy_days // turns


def must_stock_fallback_qty(coverage_period: int) -> int:
    """Minimum order quantity for must_stock items with no velocity data.

    Conservative: max(1, coverage_period / 90)
    """
    return max(1, round(coverage_period / 90))


def calculate_days_to_stockout(effective_stock: float, velocity: float) -> float | None:
    """F11: days_to_stockout = effective_stock / velocity.

    Uses recent_velocity for the most current demand signal.

    Edge cases:
    - velocity=0, stock>0 → None (no demand, display as "No demand")
    - velocity=0, stock<=0 → 0
    - stock<=0 → 0
    """
    if velocity <= 0:
        if effective_stock <= 0:
            return 0
        return None  # No demand
    if effective_stock <= 0:
        return 0  # Already out of stock
    return round(effective_stock / velocity, 1)


def detect_import_history(stock_item_name: str, transactions: list[dict]) -> dict:
    """Find import shipments (GRNs from suppliers)."""
    imports = [
        t for t in transactions
        if t.get("channel") == "supplier" and t.get("is_inward", False)
    ]

    if not imports:
        return {
            "last_import_date": None,
            "last_import_qty": None,
            "last_import_supplier": None,
        }

    imports.sort(key=lambda t: t.get("date") or t.get("txn_date"))

    last = imports[-1]
    return {
        "last_import_date": last.get("date") or last.get("txn_date"),
        "last_import_qty": last["quantity"],
        "last_import_supplier": "",
    }


def determine_reorder_status(
    current_stock: float,
    days_to_stockout: float | None,
    supplier_lead_time: int,
    total_velocity: float,
    safety_buffer: float = 1.3,
    coverage_period: int = 0,
    reorder_intent: str = "normal",
    open_purchase: float = 0,
) -> tuple[str, float | None]:
    """
    F15+F16: Determine reorder status and suggested order quantity.

    Buffer applies to coverage demand ONLY — not to lead time demand.
    This prevents double-buffering.

    Formula:
        demand_during_lead  = velocity × lead_time          (best estimate, NO buffer)
        stock_at_arrival    = max(0, effective_stock - demand_during_lead)
        order_for_coverage  = velocity × coverage_period × safety_buffer
        suggested_qty       = max(0, (demand_during_lead + order_for_coverage) - effective_stock)

    Status mapping (F16):
        LOST_SALES   = velocity > 0 AND stock <= 0
        OUT_OF_STOCK = velocity = 0 AND stock <= 0
        DEAD_STOCK   = velocity = 0 AND stock > 0
        URGENT       = dts <= lead_time
        REORDER      = dts <= lead_time + warning_buffer
        HEALTHY      = otherwise

    Override logic:
        must_stock → minimum REORDER (URGENT only if formula agrees)
        do_not_reorder → show calculated status + qty=0 + suppressed flag
    """
    effective_stock = current_stock  # F2: no openPurchase

    # Determine raw status first
    if total_velocity > 0 and effective_stock <= 0:
        raw_status = "lost_sales"
    elif total_velocity <= 0 and effective_stock <= 0:
        raw_status = "out_of_stock"
    elif total_velocity <= 0 and effective_stock > 0:
        raw_status = "dead_stock"
    elif days_to_stockout is not None and days_to_stockout <= supplier_lead_time:
        raw_status = "urgent"
    elif days_to_stockout is not None and days_to_stockout <= supplier_lead_time + max(30, int(supplier_lead_time * 0.5)):
        raw_status = "reorder"
    else:
        raw_status = "healthy"

    # Compute suggested quantity
    suggested_qty = None
    if total_velocity > 0:
        demand_during_lead = total_velocity * supplier_lead_time  # NO buffer
        order_for_coverage = total_velocity * coverage_period * safety_buffer  # buffer HERE only
        suggested_qty = max(0, round(demand_during_lead + order_for_coverage - effective_stock))
        if suggested_qty == 0:
            suggested_qty = None

    # Apply intent overrides
    status = raw_status

    if reorder_intent == "must_stock":
        if total_velocity <= 0:
            # Must-stock with no velocity: force REORDER with conservative qty
            status = "reorder"
            if suggested_qty is None:
                suggested_qty = must_stock_fallback_qty(coverage_period)
        elif status in ("healthy",):
            # Must-stock with velocity but HEALTHY status: bump to REORDER
            status = "reorder"
        # URGENT stays URGENT (formula agrees)
        # REORDER stays REORDER
        # lost_sales stays lost_sales

    elif reorder_intent == "do_not_reorder":
        # Show calculated status but suppress quantity
        suggested_qty = None

    return (status, suggested_qty)


def get_supplier_for_category(db_conn, category_name: str) -> dict | None:
    """Find the supplier for a brand/category by matching supplier name to category name."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT name, lead_time_default, lead_time_sea, lead_time_air
            FROM suppliers
            WHERE UPPER(name) = UPPER(%s)
            LIMIT 1
        """, (category_name,))
        row = cur.fetchone()
        if row:
            return {
                "name": row[0],
                "lead_time_default": row[1],
                "lead_time_sea": row[2],
                "lead_time_air": row[3],
            }
    return None
