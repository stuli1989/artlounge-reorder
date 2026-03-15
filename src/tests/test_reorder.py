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


def test_reorder_qty_includes_coverage():
    """Suggested qty should cover lead_time + coverage_period."""
    # velocity=2, lead_time=120, coverage=180, buffer=1.3, stock=240
    # raw_need = 2 * (120+180) * 1.3 = 780, suggested = 780-240 = 540
    status, qty = determine_reorder_status(
        current_stock=240, days_to_stockout=120.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "critical"
    assert qty == 540


def test_reorder_qty_zero_coverage_matches_old():
    """With coverage_period=0, formula matches the old behavior."""
    # raw_need = 2*(120+0)*1.3 = 312, suggested = 312-240 = 72
    status, qty = determine_reorder_status(
        current_stock=240, days_to_stockout=120.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=0,
    )
    assert status == "critical"
    assert qty == 72


def test_warning_thresholds_use_lead_time_not_coverage():
    """Warning/critical thresholds based on lead_time only, not coverage."""
    # 200 days of stock, lead_time=120, warning_buffer=max(30,60)=60
    # threshold = 120+60 = 180. 200 > 180 → OK
    status, qty = determine_reorder_status(
        current_stock=400, days_to_stockout=200.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "ok"
