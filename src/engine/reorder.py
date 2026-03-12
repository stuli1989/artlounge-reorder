"""
Stockout prediction, import history detection, and reorder status flags.
"""
from datetime import date

DEFAULT_LEAD_TIME = 180  # days (sea freight default)


def calculate_days_to_stockout(current_stock: float, total_velocity: float) -> float | None:
    """Calculate days until stock runs out at current velocity."""
    if total_velocity <= 0:
        return None  # No demand data
    if current_stock <= 0:
        return 0  # Already out of stock
    return round(current_stock / total_velocity, 1)


def detect_import_history(stock_item_name: str, transactions: list[dict]) -> dict:
    """Find import shipments (purchases from suppliers)."""
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

    imports.sort(key=lambda t: t["txn_date"] if "txn_date" in t else t["date"])

    last = imports[-1]
    return {
        "last_import_date": last.get("txn_date", last.get("date")),
        "last_import_qty": last["quantity"],
        "last_import_supplier": last.get("party_name", last.get("party", "")),
    }


def determine_reorder_status(
    current_stock: float,
    days_to_stockout: float | None,
    supplier_lead_time: int,
    total_velocity: float,
) -> tuple[str, float | None]:
    """
    Determine reorder status and suggested order quantity.

    Returns (status, suggested_qty).
    """
    if total_velocity <= 0:
        if current_stock <= 0:
            return ("out_of_stock", None)
        return ("no_data", None)

    suggested_qty = round(total_velocity * supplier_lead_time * 1.3)

    if current_stock <= 0:
        return ("out_of_stock", suggested_qty)

    if days_to_stockout is None:
        return ("no_data", None)

    if days_to_stockout <= supplier_lead_time:
        return ("critical", suggested_qty)
    elif days_to_stockout <= supplier_lead_time + 30:
        return ("warning", suggested_qty)
    else:
        return ("ok", suggested_qty)


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
