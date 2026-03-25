"""
Brand-level metric aggregation from SKU metrics.

F19: Dead stock detection (available_stock > 0 AND no dispatch in threshold days)
F20: Slow mover (ABC-aware: exclude A-class)
F23: Brand rollups with min_days_to_stockout
"""
from datetime import date as date_type


def compute_brand_metrics(
    category_name: str,
    sku_metrics_list: list[dict],
    supplier: dict | None,
    dead_stock_threshold: int = 90,
    slow_mover_threshold: float = 0.1,
    today: date_type | None = None,
) -> dict:
    """F23: Aggregate SKU metrics to brand level (single-pass).

    Adds min_days_to_stockout to complement velocity-weighted average,
    which can mask critical slow-moving SKUs.
    """
    if today is None:
        today = date_type.today()

    total = len(sku_metrics_list)
    in_stock = 0
    out_of_stock = 0
    critical = 0
    warning = 0
    ok = 0
    no_data = 0
    stocked_out = 0
    no_demand = 0
    dead_stock = 0
    slow_mover = 0
    a_class = 0
    b_class = 0
    c_class = 0
    inactive = 0
    weighted_sum = 0.0
    weight_total = 0.0
    min_dts = None  # min_days_to_stockout

    for s in sku_metrics_list:
        stock = s.get("current_stock", 0)
        status = s.get("reorder_status")
        vel = s.get("total_velocity", 0)
        abc = s.get("abc_class")

        if stock > 0:
            in_stock += 1
            # F19: Dead stock — has stock but no recent dispatch
            lsd = s.get("last_sale_date")
            if lsd is None or (today - lsd).days >= dead_stock_threshold:
                dead_stock += 1
            # F20: Slow mover — ABC-aware (exclude A-class)
            if (vel > 0 and vel < slow_mover_threshold
                    and abc != "A"
                    and s.get("reorder_intent", "normal") == "normal"):
                slow_mover += 1
        else:
            out_of_stock += 1

        # Status counts — expanded for UC
        if status == "critical":
            critical += 1
        elif status == "warning":
            warning += 1
        elif status == "ok":
            ok += 1
        elif status == "stocked_out":
            stocked_out += 1
        elif status == "no_demand":
            no_demand += 1
        elif status in ("no_data", "out_of_stock"):
            no_data += 1

        # ABC class counts
        if abc == "A":
            a_class += 1
        elif abc == "B":
            b_class += 1
        elif abc == "C":
            c_class += 1

        if not s.get("is_active", True):
            inactive += 1

        # Days to stockout for weighted average
        dts = s.get("days_to_stockout")
        if dts is not None and vel > 0:
            weighted_sum += dts * vel
            weight_total += vel

        # min_days_to_stockout — include 0 so active stockouts are visible
        if dts is not None and dts >= 0:
            if min_dts is None or dts < min_dts:
                min_dts = dts

    avg_days = round(weighted_sum / weight_total, 1) if weight_total > 0 else None

    return {
        "category_name": category_name,
        "total_skus": total,
        "in_stock_skus": in_stock,
        "out_of_stock_skus": out_of_stock,
        "critical_skus": critical,
        "warning_skus": warning,
        "ok_skus": ok,
        "no_data_skus": no_data,
        "stocked_out_skus": stocked_out,
        "no_demand_skus": no_demand,
        "avg_days_to_stockout": avg_days,
        "min_days_to_stockout": min_dts,
        "dead_stock_skus": dead_stock,
        "slow_mover_skus": slow_mover,
        "primary_supplier": supplier.get("name") if supplier else None,
        "supplier_lead_time": supplier.get("lead_time_default") if supplier else None,
        "a_class_skus": a_class,
        "b_class_skus": b_class,
        "c_class_skus": c_class,
        "inactive_skus": inactive,
    }
