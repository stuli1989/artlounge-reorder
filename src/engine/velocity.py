"""
Velocity calculation — units per day during active (sellable) periods only.

Velocity = total demand during active days / count of active days

A day is "active" (is_in_stock=True) if closing_qty > 0 OR if real demand
(wholesale/online/store sales) occurred. This ensures days with negative
closing balances due to Tally data quality issues are still counted when
items were clearly selling. Inactive days (no stock AND no sales) are
excluded from both numerator and denominator, so stockouts don't dilute
the velocity estimate.
"""
from datetime import date, timedelta

from config.settings import FY_START_DATE, FY_END_DATE


def find_in_stock_periods(daily_positions: list[dict]) -> list[dict]:
    """
    Group contiguous active days into periods.

    A day is active (is_in_stock) if closing_qty > 0 or demand occurred.
    Returns list of {"from": date, "to": date, "days": int}.
    """
    periods = []
    current_start = None

    for p in daily_positions:
        if p["is_in_stock"]:
            if current_start is None:
                current_start = p["position_date"]
        else:
            if current_start is not None:
                # Previous day was the end of an in-stock period
                prev_date = p["position_date"]
                end_date = prev_date - timedelta(days=1)
                days = (end_date - current_start).days + 1
                periods.append({"from": current_start, "to": end_date, "days": days})
                current_start = None

    # Close final period if still in stock at end of range
    if current_start is not None:
        end_date = daily_positions[-1]["position_date"]
        days = (end_date - current_start).days + 1
        periods.append({"from": current_start, "to": end_date, "days": days})

    return periods


def calculate_velocity(stock_item_name: str, daily_positions: list[dict]) -> dict:
    """
    Calculate wholesale, online, and total velocity from daily positions.

    Only active days (is_in_stock: closing_qty > 0 or demand occurred) are included.
    Returns units/day values (multiply by 30 for monthly display).
    """
    in_stock_days = [p for p in daily_positions if p["is_in_stock"]]

    if not in_stock_days:
        return {
            "wholesale_velocity": 0,
            "online_velocity": 0,
            "total_velocity": 0,
            "total_in_stock_days": 0,
            "velocity_start_date": None,
            "velocity_end_date": None,
        }

    total_wholesale_out = sum(p["wholesale_out"] for p in in_stock_days)
    total_online_out = sum(p["online_out"] for p in in_stock_days)
    total_store_out = sum(p["store_out"] for p in in_stock_days)
    num_days = len(in_stock_days)

    wholesale_v = total_wholesale_out / num_days
    online_v = total_online_out / num_days
    store_v = total_store_out / num_days

    return {
        "wholesale_velocity": round(wholesale_v, 4),
        "online_velocity": round(online_v, 4),
        "total_velocity": round(wholesale_v + online_v + store_v, 4),
        "total_in_stock_days": num_days,
        "velocity_start_date": in_stock_days[0]["position_date"],
        "velocity_end_date": in_stock_days[-1]["position_date"],
    }


def resolve_date_range(from_date: str | None, to_date: str | None) -> tuple[date, date]:
    """Resolve optional date strings to actual range, defaulting to FY start/today."""
    range_start = date.fromisoformat(from_date) if from_date else FY_START_DATE
    range_end = date.fromisoformat(to_date) if to_date else min(date.today(), FY_END_DATE)
    return range_start, range_end


def fetch_batch_velocities(cur, sku_names: list[str], range_start: date, range_end: date) -> dict[str, dict]:
    """Batch-query daily_stock_positions for per-SKU velocity aggregates in a date range.

    The is_in_stock column includes days with demand even if closing_qty <= 0,
    so velocity calculations correctly capture all real selling activity.

    Returns {stock_item_name: {in_stock_days, wholesale_total, online_total, store_total}}.
    """
    if not sku_names:
        return {}
    cur.execute("""
        SELECT dsp.stock_item_name,
               COUNT(*) FILTER (WHERE dsp.is_in_stock) AS in_stock_days,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.wholesale_out ELSE 0 END), 0) AS wholesale_total,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.online_out ELSE 0 END), 0) AS online_total,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.store_out ELSE 0 END), 0) AS store_total
        FROM daily_stock_positions dsp
        WHERE dsp.stock_item_name = ANY(%s)
        AND dsp.position_date >= %s AND dsp.position_date <= %s
        GROUP BY dsp.stock_item_name
    """, (sku_names, range_start, range_end))
    return {row["stock_item_name"]: dict(row) for row in cur.fetchall()}


def velocities_from_batch_row(vel_row: dict | None) -> tuple[float, float, float, float]:
    """Convert a batch velocity row to (wholesale, online, store, total) daily rates.

    Returns (0, 0, 0, 0) if vel_row is None or has zero in-stock days.
    """
    if not vel_row or vel_row["in_stock_days"] <= 0:
        return 0.0, 0.0, 0.0, 0.0
    isd = float(vel_row["in_stock_days"])
    w = float(vel_row["wholesale_total"]) / isd
    o = float(vel_row["online_total"]) / isd
    s = float(vel_row["store_total"]) / isd
    return w, o, s, w + o + s


def opt_float(v):
    """Convert to float if not None, else return None."""
    return float(v) if v is not None else None


def fetch_batch_wma_velocities(
    cur, sku_names: list[str], range_end: date, window_days: int = 90,
) -> dict[str, dict]:
    """Batch-query daily_stock_positions for per-SKU velocity over a trailing window.

    Same shape as fetch_batch_velocities but filtered to last `window_days` of data.
    Returns {stock_item_name: {in_stock_days, wholesale_total, online_total, store_total}}.
    Works with both dict cursors (API) and tuple cursors (pipeline).
    """
    if not sku_names:
        return {}
    window_start = range_end - timedelta(days=window_days)
    cur.execute("""
        SELECT dsp.stock_item_name,
               COUNT(*) FILTER (WHERE dsp.is_in_stock) AS in_stock_days,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.wholesale_out ELSE 0 END), 0) AS wholesale_total,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.online_out ELSE 0 END), 0) AS online_total,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.store_out ELSE 0 END), 0) AS store_total
        FROM daily_stock_positions dsp
        WHERE dsp.stock_item_name = ANY(%s)
        AND dsp.position_date >= %s AND dsp.position_date <= %s
        GROUP BY dsp.stock_item_name
    """, (sku_names, window_start, range_end))
    cols = [desc[0] for desc in cur.description]
    result = {}
    for row in cur.fetchall():
        if isinstance(row, dict):
            d = dict(row)
        else:
            d = dict(zip(cols, row))
        result[d["stock_item_name"]] = d
    return result


def detect_trend(
    flat_velocity: float,
    wma_velocity: float,
    up_threshold: float = 1.2,
    down_threshold: float = 0.8,
) -> tuple[str, float | None]:
    """Compare WMA velocity to flat velocity to detect trend direction.

    Returns (direction, ratio) where direction is 'up', 'down', or 'flat'.
    """
    if flat_velocity <= 0 and wma_velocity <= 0:
        return ("flat", None)
    if flat_velocity <= 0 and wma_velocity > 0:
        return ("up", None)
    ratio = wma_velocity / flat_velocity
    if ratio > up_threshold:
        return ("up", round(ratio, 3))
    elif ratio < down_threshold:
        return ("down", round(ratio, 3))
    else:
        return ("flat", round(ratio, 3))
