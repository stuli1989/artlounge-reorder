"""Shared logic for computing effective (override-applied) values."""
from engine.reorder import calculate_days_to_stockout, determine_reorder_status, DEFAULT_LEAD_TIME

# Canonical mapping from override field_name to sku_metrics column.
# store_velocity is NOT a column in sku_metrics — it's derived.
OVERRIDE_FIELD_TO_COLUMN = {
    "current_stock": "current_stock",
    "total_velocity": "total_velocity",
    "wholesale_velocity": "wholesale_velocity",
    "online_velocity": "online_velocity",
}


def compute_effective_values(
    computed_stock: float,
    computed_wholesale: float,
    computed_online: float,
    computed_total: float,
    stock_ovr: float | None = None,
    wholesale_ovr: float | None = None,
    online_ovr: float | None = None,
    store_ovr: float | None = None,
    total_ovr: float | None = None,
) -> dict:
    """
    Apply override layer to computed values.

    Priority for total velocity:
      1. total_velocity override exists → use it directly
      2. Any per-channel override exists → sum of effective channels
      3. No overrides → use computed total

    Returns dict with effective values and source flags.
    """
    computed_store = max(0, computed_total - computed_wholesale - computed_online)

    eff_stock = stock_ovr if stock_ovr is not None else computed_stock
    eff_wholesale = wholesale_ovr if wholesale_ovr is not None else computed_wholesale
    eff_online = online_ovr if online_ovr is not None else computed_online
    eff_store = store_ovr if store_ovr is not None else computed_store

    has_channel_ovr = wholesale_ovr is not None or online_ovr is not None or store_ovr is not None
    if total_ovr is not None:
        eff_total = total_ovr
    elif has_channel_ovr:
        eff_total = eff_wholesale + eff_online + eff_store
    else:
        eff_total = computed_total

    return {
        "eff_stock": eff_stock,
        "eff_wholesale": eff_wholesale,
        "eff_online": eff_online,
        "eff_store": eff_store,
        "eff_total": eff_total,
        "has_stock_override": stock_ovr is not None,
        "has_velocity_override": (
            total_ovr is not None or has_channel_ovr
        ),
    }


def compute_effective_status(
    eff_stock: float,
    eff_total: float,
    lead_time: int = DEFAULT_LEAD_TIME,
) -> dict:
    """Recalculate stockout + reorder status from effective values."""
    eff_days = calculate_days_to_stockout(eff_stock, eff_total)
    eff_status, eff_suggested = determine_reorder_status(
        eff_stock, eff_days, lead_time, eff_total,
    )
    return {
        "eff_days": eff_days,
        "eff_status": eff_status,
        "eff_suggested": eff_suggested,
    }
