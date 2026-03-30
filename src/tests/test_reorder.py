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


def test_reorder_qty_plenty_of_stock():
    """When stock exceeds lead_time demand, order covers lead + coverage - stock."""
    # velocity=2, lead_time=120, coverage=180, buffer=1.3, stock=400
    # demand_during_lead = 2 * 120 = 240  (NO buffer on lead time)
    # order_for_coverage = 2 * 180 * 1.3 = 468
    # suggested = max(0, round(240 + 468 - 400)) = 308
    status, qty = determine_reorder_status(
        current_stock=400, days_to_stockout=200.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "healthy"
    assert qty == 308


def test_reorder_qty_will_stockout_before_arrival():
    """Critical items that stock out before arrival: large order needed."""
    # velocity=2, lead_time=120, coverage=180, buffer=1.3, stock=100
    # demand_during_lead = 2 * 120 = 240  (NO buffer on lead time)
    # order_for_coverage = 2 * 180 * 1.3 = 468
    # suggested = max(0, round(240 + 468 - 100)) = 608
    status, qty = determine_reorder_status(
        current_stock=100, days_to_stockout=50.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "urgent"
    assert qty == 608


def test_reorder_qty_out_of_stock():
    """Out-of-stock items with velocity: stocked_out status, order for lead + coverage."""
    # velocity=2, lead_time=120, coverage=180, buffer=1.3, stock=0
    # demand_during_lead = 2 * 120 = 240
    # order_for_coverage = 2 * 180 * 1.3 = 468
    # suggested = max(0, round(240 + 468 - 0)) = 708
    status, qty = determine_reorder_status(
        current_stock=0, days_to_stockout=0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "lost_sales"
    assert qty == 708


def test_reorder_qty_out_of_stock_not_inflated():
    """Verify out-of-stock qty uses demand_during_lead WITHOUT buffer."""
    # demand_during_lead = 2 * 120 = 240  (NO buffer)
    # order_for_coverage = 2 * 180 * 1.3 = 468
    # suggested = 240 + 468 - 0 = 708
    # Old formula with buffer on lead: 2*120*1.3 + 2*180*1.3 = 312+468 = 780
    status, qty = determine_reorder_status(
        current_stock=0, days_to_stockout=0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert qty == 708  # NOT 780 (no buffer on lead time)


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
    # order_for_coverage = 3.88 * 90 * 1.3 ≈ 454
    assert qty == 454
    assert status == "lost_sales"


def test_coverage_only_mode_with_stock():
    """Coverage-only with stock: stock offsets coverage demand."""
    status, qty = determine_reorder_status(
        current_stock=100, days_to_stockout=25.8, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=False,
    )
    # order_for_coverage = 3.88 * 90 * 1.3 ≈ 454
    # suggested = max(0, 454 - 100) = 354
    assert qty == 354


def test_full_mode_unchanged():
    """Full mode (default): same as before."""
    status, qty = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=True,
    )
    # demand_lead = 3.88 * 90 ≈ 349
    # order_cov = 3.88 * 90 * 1.3 ≈ 454
    # suggested = max(0, 349 + 454 - 0) = 803
    assert qty == 803


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
