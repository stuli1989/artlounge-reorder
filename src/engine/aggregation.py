"""
Brand-level metric aggregation from SKU metrics.
"""
from datetime import date as date_type


def compute_brand_metrics(
    category_name: str,
    sku_metrics_list: list[dict],
    supplier: dict | None,
    dead_stock_threshold: int = 30,
    slow_mover_threshold: float = 0.1,
    today: date_type | None = None,
) -> dict:
    """Aggregate SKU metrics to brand level (single-pass)."""
    if today is None:
        today = date_type.today()

    total = len(sku_metrics_list)
    in_stock = 0
    out_of_stock = 0
    critical = 0
    warning = 0
    ok = 0
    no_data = 0
    dead_stock = 0
    slow_mover = 0
    a_class = 0
    b_class = 0
    c_class = 0
    inactive = 0
    weighted_sum = 0.0
    weight_total = 0.0

    for s in sku_metrics_list:
        stock = s.get("current_stock", 0)
        status = s.get("reorder_status")
        vel = s.get("total_velocity", 0)
        if stock > 0:
            in_stock += 1
            # Dead stock check: has stock but no recent demand sales
            lsd = s.get("last_sale_date")
            if lsd is None or (today - lsd).days >= dead_stock_threshold:
                dead_stock += 1
            # Slow mover: has stock, has some velocity but low, not already classified
            if (vel > 0 and vel < slow_mover_threshold
                    and s.get("reorder_intent", "normal") == "normal"):
                slow_mover += 1
        else:
            out_of_stock += 1
        if status == "critical":
            critical += 1
        elif status == "warning":
            warning += 1
        elif status == "ok":
            ok += 1
        elif status == "no_data":
            no_data += 1
        # ABC class counts
        abc = s.get("abc_class")
        if abc == "A":
            a_class += 1
        elif abc == "B":
            b_class += 1
        elif abc == "C":
            c_class += 1
        # Inactive count
        if not s.get("is_active", True):
            inactive += 1
        dts = s.get("days_to_stockout")
        if dts is not None and vel > 0:
            weighted_sum += dts * vel
            weight_total += vel

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
        "dead_stock_skus": dead_stock,
        "slow_mover_skus": slow_mover,
        "avg_days_to_stockout": avg_days,
        "primary_supplier": supplier.get("name") if supplier else None,
        "supplier_lead_time": supplier.get("lead_time_default") if supplier else None,
        "a_class_skus": a_class,
        "b_class_skus": b_class,
        "c_class_skus": c_class,
        "inactive_skus": inactive,
    }
