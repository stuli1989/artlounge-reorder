"""
ABC/XYZ classification and variable safety buffer computation.

ABC: Revenue-based (A=top 80%, B=next 15%, C=bottom 5%)
XYZ: Demand variability (X=stable CV<0.5, Y=moderate 0.5-1.0, Z=erratic >1.0)
"""
import math
from datetime import timedelta

# Channels counted as demand for revenue calculation
_DEMAND_CHANNELS = {"wholesale", "online", "store"}
_EXCLUDED_VOUCHER_TYPES = {"Credit Note", "Debit Note"}


def compute_abc_classification(
    metrics_batch: list[dict],
    all_txns: dict[str, list[dict]],
    a_threshold: float = 0.80,
    b_threshold: float = 0.95,
):
    """Classify SKUs into A/B/C based on revenue contribution.

    Mutates metrics_batch entries: sets abc_class, total_revenue.
    """
    # Compute revenue per SKU from demand transactions
    revenue_by_sku = {}
    for m in metrics_batch:
        sku = m["stock_item_name"]
        txns = all_txns.get(sku, [])
        total_rev = 0.0
        for t in txns:
            if (t.get("channel") in _DEMAND_CHANNELS
                    and not t.get("is_inward")
                    and t.get("voucher_type") not in _EXCLUDED_VOUCHER_TYPES):
                total_rev += abs(float(t.get("amount") or 0))
        revenue_by_sku[sku] = total_rev

    # Sort SKUs by revenue descending
    sorted_skus = sorted(revenue_by_sku.items(), key=lambda x: x[1], reverse=True)
    grand_total = sum(r for _, r in sorted_skus)

    # Assign ABC based on cumulative revenue percentage
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

    # Mutate metrics batch
    for m in metrics_batch:
        sku = m["stock_item_name"]
        m["abc_class"] = abc_map.get(sku, "C")
        m["total_revenue"] = revenue_by_sku.get(sku, 0)


def compute_xyz_classification(
    metrics_batch: list[dict],
    daily_positions_by_sku: dict[str, list[dict]],
):
    """Classify SKUs into X/Y/Z based on demand variability (CV of weekly demand).

    Mutates metrics_batch: sets xyz_class, demand_cv.
    Requires minimum 4 weeks of in-stock data.
    """
    for m in metrics_batch:
        sku = m["stock_item_name"]
        positions = daily_positions_by_sku.get(sku, [])

        # Only consider in-stock days
        in_stock = [p for p in positions if p.get("is_in_stock")]
        if len(in_stock) < 28:  # Need at least 4 weeks
            m["xyz_class"] = None
            m["demand_cv"] = None
            continue

        # Bucket into weeks and sum demand
        weekly_demands = []
        week_demand = 0.0
        days_in_week = 0
        for p in in_stock:
            w_out = float(p.get("wholesale_out", 0))
            o_out = float(p.get("online_out", 0))
            s_out = float(p.get("store_out", 0))
            week_demand += w_out + o_out + s_out
            days_in_week += 1
            if days_in_week == 7:
                weekly_demands.append(week_demand)
                week_demand = 0.0
                days_in_week = 0
        # Include partial final week if >= 4 days
        if days_in_week >= 4:
            weekly_demands.append(week_demand)

        if len(weekly_demands) < 4:
            m["xyz_class"] = None
            m["demand_cv"] = None
            continue

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
    use_xyz: bool = True,
) -> float:
    """Look up safety buffer. ABC-only or ABC×XYZ matrix. Fallback 1.3."""
    if not abc_class:
        return 1.3
    if use_xyz and xyz_class:
        key = f"buffer_{abc_class.lower()}{xyz_class.lower()}"
        return buffer_settings.get(key, 1.3)
    # ABC-only lookup
    key = f"buffer_{abc_class.lower()}"
    return buffer_settings.get(key, 1.3)


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
