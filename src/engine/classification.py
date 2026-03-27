"""
ABC/XYZ classification and variable safety buffer computation.

F14: Safety buffer — supplier override as MULTIPLIER on matrix (not replacement)
F17: ABC — revenue-based Pareto (sellingPrice × quantity for dispatched items)
F18: XYZ — demand variability using CALENDAR WEEKS (Mon-Sun), not stitched days
"""
import math
from datetime import timedelta

# Channels counted as demand for revenue calculation
_DEMAND_CHANNELS = {"wholesale", "online", "store"}


def compute_abc_classification(
    metrics_batch: list[dict],
    all_txns: dict[str, list[dict]],
    a_threshold: float = 0.80,
    b_threshold: float = 0.95,
    mrp_lookup: dict = None,
):
    """F17: Classify SKUs into A/B/C based on revenue contribution.

    Revenue = quantity * mrp (from catalog) for dispatched demand items.
    Falls back to |amount| if mrp_lookup is not provided.

    Mutates metrics_batch entries: sets abc_class, total_revenue.
    """
    revenue_by_sku = {}
    for m in metrics_batch:
        sku = m["stock_item_name"]
        txns = all_txns.get(sku, [])
        total_rev = 0.0
        mrp = float(mrp_lookup.get(sku, 0)) if mrp_lookup else 0
        for t in txns:
            if t.get("is_demand") and not t.get("is_inward", True):
                total_rev += t.get("quantity", 0) * mrp
        revenue_by_sku[sku] = total_rev

    sorted_skus = sorted(revenue_by_sku.items(), key=lambda x: x[1], reverse=True)
    grand_total = sum(r for _, r in sorted_skus)

    abc_map = {}
    cumulative = 0.0
    for sku, rev in sorted_skus:
        if rev == 0:
            abc_map[sku] = "C"
            continue
        cumulative += rev
        pct = cumulative / grand_total if grand_total > 0 else 1.0
        if pct <= a_threshold:
            abc_map[sku] = "A"
        elif pct <= b_threshold:
            abc_map[sku] = "B"
        else:
            abc_map[sku] = "C"

    for m in metrics_batch:
        sku = m["stock_item_name"]
        m["abc_class"] = abc_map.get(sku, "C")
        m["total_revenue"] = revenue_by_sku.get(sku, 0)


def compute_xyz_classification(
    metrics_batch: list[dict],
    daily_positions_by_sku: dict[str, list[dict]],
):
    """F18: Classify SKUs into X/Y/Z using CALENDAR WEEKS (Mon-Sun).

    FIXED from Tally version: uses ISO calendar weeks instead of stitching
    non-contiguous in-stock days sequentially. This preserves temporal structure.

    Rules:
    - Group in-stock days into calendar weeks (Mon-Sun)
    - Only include weeks where SKU was in-stock >= 4 days
    - Require minimum 4 qualifying weeks (28 in-stock days equivalent)
    - CV = population_stddev / mean of qualifying weekly demands

    Mutates metrics_batch: sets xyz_class, demand_cv.
    """
    for m in metrics_batch:
        sku = m["stock_item_name"]
        positions = daily_positions_by_sku.get(sku, [])

        # Group positions by ISO calendar week (year, week_number)
        weeks = {}  # (year, week) → {"demand": float, "in_stock_days": int}
        for p in positions:
            pos_date = p.get("position_date")
            if pos_date is None:
                continue
            iso_year, iso_week, _ = pos_date.isocalendar()
            key = (iso_year, iso_week)

            if key not in weeks:
                weeks[key] = {"demand": 0.0, "in_stock_days": 0}

            if p.get("is_in_stock"):
                weeks[key]["in_stock_days"] += 1
                w_out = max(0, float(p.get("wholesale_out", 0)))
                o_out = max(0, float(p.get("online_out", 0)))
                s_out = max(0, float(p.get("store_out", 0)))
                weeks[key]["demand"] += w_out + o_out + s_out

        # Only include weeks where in-stock >= 4 days
        qualifying_weeks = [
            w for w in weeks.values()
            if w["in_stock_days"] >= 4
        ]

        if len(qualifying_weeks) < 4:
            m["xyz_class"] = None
            m["demand_cv"] = None
            continue

        weekly_demands = [w["demand"] for w in qualifying_weeks]
        mean = sum(weekly_demands) / len(weekly_demands)

        if mean <= 0:
            m["xyz_class"] = None
            m["demand_cv"] = None
            continue

        variance = sum((d - mean) ** 2 for d in weekly_demands) / len(weekly_demands)
        stddev = math.sqrt(variance)
        cv = stddev / mean

        m["demand_cv"] = round(cv, 4)
        if cv < 0.5:
            m["xyz_class"] = "X"
        elif cv <= 1.0:
            m["xyz_class"] = "Y"
        else:
            m["xyz_class"] = "Z"


def compute_safety_buffer(
    abc_class: str | None,
    xyz_class: str | None,
    buffer_settings: dict[str, float],
    supplier_override: float | None = None,
    use_xyz: bool = True,
) -> float:
    """F14: Look up safety buffer from ABC×XYZ matrix.

    Supplier override is a MULTIPLIER on the matrix (not a replacement).
    Example: supplier_override=1.1 × matrix AX=1.2 → effective buffer=1.32

    Fallback: 1.3 if no classification.
    """
    if not abc_class:
        base = 1.3
    elif use_xyz and xyz_class:
        key = f"buffer_{abc_class.lower()}{xyz_class.lower()}"
        base = buffer_settings.get(key, 1.3)
    else:
        key = f"buffer_{abc_class.lower()}"
        base = buffer_settings.get(key, 1.3)

    if supplier_override is not None:
        return round(base * supplier_override, 4)
    return base


def fetch_buffer_settings(db_conn) -> dict[str, float]:
    """Load all buffer_* settings from app_settings."""
    settings = {}
    with db_conn.cursor() as cur:
        cur.execute("SELECT key, value FROM app_settings WHERE key LIKE 'buffer_%'")
        for row in cur.fetchall():
            try:
                settings[row[0]] = float(row[1])
            except (ValueError, TypeError):
                pass
    return settings


def fetch_use_xyz_global(db_conn) -> bool:
    """Read use_xyz_buffer toggle from app_settings. Default False."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT value FROM app_settings WHERE key = 'use_xyz_buffer'")
        row = cur.fetchone()
        return row[0].lower() == 'true' if row else False


def fetch_classification_settings(db_conn) -> dict:
    """Load ABC/XYZ threshold settings."""
    defaults = {
        "abc_a_threshold": 0.80,
        "abc_b_threshold": 0.95,
        "wma_window_days": 90,
        "trend_up_threshold": 1.2,
        "trend_down_threshold": 0.8,
        "min_velocity_sample_days": 14,
    }
    with db_conn.cursor() as cur:
        keys = list(defaults.keys())
        cur.execute(
            "SELECT key, value FROM app_settings WHERE key = ANY(%s)",
            (keys,),
        )
        for row in cur.fetchall():
            try:
                defaults[row[0]] = float(row[1])
            except (ValueError, TypeError):
                pass
    return defaults
