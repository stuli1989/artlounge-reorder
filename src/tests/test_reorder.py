from engine.reorder import compute_coverage_days, determine_reorder_status


def test_coverage_days_from_typical_months():
    assert compute_coverage_days(lead_time=120, typical_order_months=6) == 180


def test_coverage_days_from_typical_months_3():
    assert compute_coverage_days(lead_time=90, typical_order_months=3) == 90


def test_coverage_days_auto_from_lead_time_120():
    # 120-day lead time: 365//120 = 3 turns, 365//3 = 121
    assert compute_coverage_days(lead_time=120, typical_order_months=None) == 121


def test_coverage_days_auto_90():
    # 90-day lead time: 365//90 = 4 turns, 365//4 = 91
    assert compute_coverage_days(lead_time=90, typical_order_months=None) == 91


def test_coverage_days_auto_180():
    # 180-day lead time: 365//180 = 2 turns, 365//2 = 182
    assert compute_coverage_days(lead_time=180, typical_order_months=None) == 182


def test_coverage_days_auto_30_capped():
    # 30-day lead time: 365//30 = 12 turns, capped to 6, 365//6 = 60
    assert compute_coverage_days(lead_time=30, typical_order_months=None) == 60


def test_coverage_days_auto_very_long():
    # 300-day lead time: 365//300 = 1 turn, 365//1 = 365
    assert compute_coverage_days(lead_time=300, typical_order_months=None) == 365


def test_reorder_qty_stock_exceeds_wait_period():
    """When stock exceeds wait-period demand, order target minus stock."""
    # velocity=2, lead_time=120, coverage=180, buffer=1.3, stock=400
    # wait_period = 2 * 120 = 240
    # post_arrival = 2 * 180 * 1.3 = 468
    # stock(400) > wait(240) → order = ceil(240 + 468 - 400) = ceil(308) = 308
    status, qty = determine_reorder_status(
        current_stock=400, days_to_stockout=200.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "healthy"
    assert qty == 308


def test_reorder_qty_stock_below_wait_period():
    """When stock won't last wait period, order only post-arrival needs."""
    # velocity=2, lead_time=120, coverage=180, buffer=1.3, stock=100
    # wait_period = 2 * 120 = 240
    # post_arrival = 2 * 180 * 1.3 = 468
    # stock(100) <= wait(240) → order = ceil(468) = 468
    status, qty = determine_reorder_status(
        current_stock=100, days_to_stockout=50.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "urgent"
    assert qty == 468


def test_reorder_qty_out_of_stock():
    """Out-of-stock: wait gap is sunk cost, order post-arrival only."""
    # velocity=2, lead_time=120, coverage=180, buffer=1.3, stock=0
    # wait_period = 2 * 120 = 240
    # post_arrival = 2 * 180 * 1.3 = 468
    # stock(0) <= wait(240) → order = ceil(468) = 468
    status, qty = determine_reorder_status(
        current_stock=0, days_to_stockout=0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "lost_sales"
    assert qty == 468


def test_reorder_qty_negative_stock_not_inflated():
    """Negative stock should NOT inflate order — still just post-arrival."""
    # velocity=2, lead_time=120, coverage=180, buffer=1.3, stock=-50
    # wait_period = 2 * 120 = 240
    # post_arrival = 2 * 180 * 1.3 = 468
    # stock(-50) <= wait(240) → order = ceil(468) = 468
    status, qty = determine_reorder_status(
        current_stock=-50, days_to_stockout=0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert qty == 468  # NOT inflated by negative stock


def test_reorder_qty_stock_equals_wait_period():
    """Boundary: stock exactly equals wait-period demand — use post-arrival only."""
    # velocity=2, lead_time=120, stock=240
    # wait_period = 2 * 120 = 240
    # post_arrival = 2 * 180 * 1.3 = 468
    # stock(240) <= wait(240) → order = ceil(468) = 468
    # Also continuous: case 2 would give ceil(240+468-240) = 468
    status, qty = determine_reorder_status(
        current_stock=240, days_to_stockout=120.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert qty == 468


def test_reorder_qty_zero_coverage():
    """With coverage_period=0, no order needed (nothing to cover after arrival)."""
    status, qty = determine_reorder_status(
        current_stock=240, days_to_stockout=120.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=0,
    )
    assert status == "urgent"
    assert qty is None


def test_warning_thresholds_use_lead_time_not_coverage():
    """Warning/critical thresholds based on lead_time only, not coverage."""
    # 200 days of stock, lead_time=120, warning_buffer=max(30,60)=60
    # threshold = 120+60 = 180. 200 > 180 → OK
    status, qty = determine_reorder_status(
        current_stock=400, days_to_stockout=200.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "healthy"


def test_no_velocity_no_demand():
    """Items with zero velocity and positive stock return no_demand."""
    status, qty = determine_reorder_status(
        current_stock=100, days_to_stockout=None,
        supplier_lead_time=120, total_velocity=0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "dead_stock"
    assert qty is None


def test_coverage_only_mode_zero_stock():
    """Coverage-only: stock=0 should not include lead demand."""
    status, qty = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=False,
    )
    # order_for_coverage = ceil(3.88 * 90 * 1.3) = ceil(453.96) = 454
    assert qty == 454
    assert status == "lost_sales"


def test_coverage_only_mode_with_stock():
    """Coverage-only with stock: stock offsets coverage demand."""
    status, qty = determine_reorder_status(
        current_stock=100, days_to_stockout=25.8, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=False,
    )
    # order_for_coverage = 3.88 * 90 * 1.3 = 453.96
    # suggested = ceil(453.96 - 100) = ceil(353.96) = 354
    assert qty == 354


def test_full_mode_stock_below_wait():
    """Full mode with stock below wait period: order post-arrival only."""
    status, qty = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=True,
    )
    # wait = 3.88 * 90 = 349.2
    # post = 3.88 * 90 * 1.3 = 453.96
    # stock(0) <= wait(349.2) → order = ceil(453.96) = 454
    assert qty == 454


def test_default_is_full_mode():
    """Default param should be True (full mode)."""
    _, qty_default = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
    )
    _, qty_full = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=True,
    )
    assert qty_default == qty_full


def test_coverage_only_status_unchanged():
    """Coverage-only should NOT change status — only qty."""
    status_full, _ = determine_reorder_status(
        current_stock=20, days_to_stockout=5.0, supplier_lead_time=90,
        total_velocity=4.0, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=True,
    )
    status_cov, _ = determine_reorder_status(
        current_stock=20, days_to_stockout=5.0, supplier_lead_time=90,
        total_velocity=4.0, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=False,
    )
    assert status_full == status_cov  # both should be "urgent"


def test_sku_0102016_example():
    """Real-world example: SKU 0102016, velocity 0.0278/day, 90d lead, 90d coverage.
    Ops team expects: post_arrival only = ceil(0.0278 * 90 * 1.3) = ceil(3.2526) = 4 units."""
    status, qty = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=90,
        total_velocity=0.0278, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=True,
    )
    assert status == "lost_sales"
    assert qty == 4  # ceil(0.0278 * 90 * 1.3) = ceil(3.2526) = 4


def test_rounding_up():
    """Verify ceil rounding: 3.1 → 4, not 3."""
    # velocity=0.5, lead=10, coverage=10, buffer=1.3, stock=0
    # wait = 0.5*10 = 5, post = 0.5*10*1.3 = 6.5
    # stock(0) <= wait(5) → order = ceil(6.5) = 7
    status, qty = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=10,
        total_velocity=0.5, safety_buffer=1.3, coverage_period=10,
    )
    assert qty == 7
