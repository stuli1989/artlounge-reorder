"""
Velocity calculation for Unicommerce data.

F7:  velocity = net_demand / in_stock_days (min 14 in-stock days)
F8:  per-channel velocity clamped at max(0, ...)
F9:  recent_velocity over trailing window (default 90 days)
F10: trend = recent_velocity / flat_velocity with edge case fixes
"""
from datetime import date, timedelta

MIN_SAMPLE_DAYS = 14  # Minimum in-stock days for reliable velocity


def find_in_stock_periods(daily_positions: list[dict]) -> list[dict]:
    """
    Group contiguous active days into periods.

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
                prev_date = p["position_date"]
                end_date = prev_date - timedelta(days=1)
                days = (end_date - current_start).days + 1
                periods.append({"from": current_start, "to": end_date, "days": days})
                current_start = None

    if current_start is not None and daily_positions:
        end_date = daily_positions[-1]["position_date"]
        days = (end_date - current_start).days + 1
        periods.append({"from": current_start, "to": end_date, "days": days})

    return periods


def calculate_velocity(item_code: str, daily_positions: list[dict]) -> dict:
    """
    Calculate wholesale, online, store, and total velocity from daily positions.

    F7: velocity = net_demand / in_stock_days
    F8: per-channel velocity clamped at max(0, ...)

    Min sample guard: if in_stock_days < 14, velocity is marked unreliable.
    Negative net demand (more returns than dispatches) → velocity clamped to 0.
    """
    in_stock_days = [p for p in daily_positions if p["is_in_stock"]]
    num_days = len(in_stock_days)

    if num_days == 0:
        return {
            "wholesale_velocity": 0,
            "online_velocity": 0,
            "total_velocity": 0,
            "total_in_stock_days": 0,
            "velocity_start_date": None,
            "velocity_end_date": None,
            "min_sample_met": False,
        }

    total_wholesale_out = sum(float(p.get("wholesale_out", 0)) for p in in_stock_days)
    total_online_out = sum(float(p.get("online_out", 0)) for p in in_stock_days)
    total_store_out = sum(float(p.get("store_out", 0)) for p in in_stock_days)

    # F8: per-channel velocity clamped at 0
    wholesale_v = max(0, total_wholesale_out / num_days)
    online_v = max(0, total_online_out / num_days)
    store_v = max(0, total_store_out / num_days)
    total_v = wholesale_v + online_v + store_v

    min_sample_met = num_days >= MIN_SAMPLE_DAYS

    return {
        "wholesale_velocity": round(wholesale_v, 4),
        "online_velocity": round(online_v, 4),
        "total_velocity": round(total_v, 4),
        "total_in_stock_days": num_days,
        "velocity_start_date": in_stock_days[0]["position_date"],
        "velocity_end_date": in_stock_days[-1]["position_date"],
        "min_sample_met": min_sample_met,
    }


def calculate_recent_velocity(
    daily_positions: list[dict],
    window_days: int = 90,
    end_date: date = None,
) -> dict:
    """
    F9: Calculate velocity over a trailing window.

    Same formula as flat velocity but restricted to last N days.
    Same min sample guard (14 in-stock days in window).
    """
    if end_date is None:
        end_date = date.today()
    window_start = end_date - timedelta(days=window_days)

    windowed = [
        p for p in daily_positions
        if p.get("position_date") and window_start <= p["position_date"] <= end_date
    ]

    in_stock = [p for p in windowed if p["is_in_stock"]]
    num_days = len(in_stock)

    if num_days == 0:
        return {"recent_velocity": 0, "recent_in_stock_days": 0, "recent_min_sample_met": False}

    total_out = sum(
        max(0, float(p.get("wholesale_out", 0)))
        + max(0, float(p.get("online_out", 0)))
        + max(0, float(p.get("store_out", 0)))
        for p in in_stock
    )

    recent_v = max(0, total_out / num_days)

    return {
        "recent_velocity": round(recent_v, 4),
        "recent_in_stock_days": num_days,
        "recent_min_sample_met": num_days >= MIN_SAMPLE_DAYS,
    }


DEFAULT_LOOKBACK_DAYS = 365


def resolve_date_range(from_date: str | None, to_date: str | None, lookback_days: int | None = None) -> tuple[date, date]:
    """Resolve optional date strings to actual range.

    Default: rolling window of lookback_days (default 365) ending today.
    Override via app_settings key 'velocity_lookback_days'.
    """
    range_end = date.fromisoformat(to_date) if to_date else date.today()
    if from_date:
        range_start = date.fromisoformat(from_date)
    else:
        days = lookback_days if lookback_days is not None else DEFAULT_LOOKBACK_DAYS
        range_start = range_end - timedelta(days=days)
    return range_start, range_end


def fetch_batch_velocities(cur, sku_names: list[str], range_start: date, range_end: date) -> dict[str, dict]:
    """Batch-query daily_stock_positions for per-SKU velocity aggregates."""
    if not sku_names:
        return {}
    cur.execute("""
        SELECT dsp.item_code,
               COUNT(*) FILTER (WHERE dsp.is_in_stock) AS in_stock_days,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.wholesale_out ELSE 0 END), 0) AS wholesale_total,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.online_out ELSE 0 END), 0) AS online_total,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.store_out ELSE 0 END), 0) AS store_total
        FROM daily_stock_positions dsp
        WHERE dsp.item_code = ANY(%s)
        AND dsp.position_date >= %s AND dsp.position_date <= %s
        GROUP BY dsp.item_code
    """, (sku_names, range_start, range_end))
    return {row["item_code"]: dict(row) for row in cur.fetchall()}


def velocities_from_batch_row(vel_row: dict | None) -> tuple[float, float, float, float]:
    """Convert a batch velocity row to (wholesale, online, store, total) daily rates.

    Per-channel rates clamped at 0 (F8).
    Returns (0, 0, 0, 0) if vel_row is None or has zero in-stock days.
    """
    if not vel_row or vel_row["in_stock_days"] <= 0:
        return 0.0, 0.0, 0.0, 0.0
    isd = float(vel_row["in_stock_days"])
    w = max(0, float(vel_row["wholesale_total"]) / isd)
    o = max(0, float(vel_row["online_total"]) / isd)
    s = max(0, float(vel_row["store_total"]) / isd)
    return w, o, s, w + o + s


def fetch_batch_wma_velocities(
    cur, sku_names: list[str], range_end: date, window_days: int = 90,
) -> dict[str, dict]:
    """Batch-query daily_stock_positions for per-SKU velocity over a trailing window (F9)."""
    if not sku_names:
        return {}
    window_start = range_end - timedelta(days=window_days)
    cur.execute("""
        SELECT dsp.item_code,
               COUNT(*) FILTER (WHERE dsp.is_in_stock) AS in_stock_days,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.wholesale_out ELSE 0 END), 0) AS wholesale_total,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.online_out ELSE 0 END), 0) AS online_total,
               COALESCE(SUM(CASE WHEN dsp.is_in_stock THEN dsp.store_out ELSE 0 END), 0) AS store_total
        FROM daily_stock_positions dsp
        WHERE dsp.item_code = ANY(%s)
        AND dsp.position_date >= %s AND dsp.position_date <= %s
        GROUP BY dsp.item_code
    """, (sku_names, window_start, range_end))
    cols = [desc[0] for desc in cur.description]
    result = {}
    for row in cur.fetchall():
        if isinstance(row, dict):
            d = dict(row)
        else:
            d = dict(zip(cols, row))
        result[d["item_code"]] = d
    return result


def detect_trend(
    flat_velocity: float,
    wma_velocity: float,
    up_threshold: float = 1.2,
    down_threshold: float = 0.8,
) -> tuple[str, float | None]:
    """F10: Compare recent velocity to flat velocity to detect trend.

    Fixed edge cases:
    - flat=0, recent>0 → UP (newly activated)
    - flat=0, recent=0 → FLAT
    - recent=0, flat>0 → DOWN
    """
    if flat_velocity <= 0 and wma_velocity <= 0:
        return ("flat", None)
    if flat_velocity <= 0 and wma_velocity > 0:
        return ("up", None)  # Newly activated
    if wma_velocity <= 0 and flat_velocity > 0:
        return ("down", 0.0)  # Demand died
    ratio = wma_velocity / flat_velocity
    if ratio >= up_threshold:
        return ("up", round(ratio, 3))
    elif ratio <= down_threshold:
        return ("down", round(ratio, 3))
    else:
        return ("flat", round(ratio, 3))


def opt_float(v):
    """Convert to float if not None, else return None."""
    return float(v) if v is not None else None
