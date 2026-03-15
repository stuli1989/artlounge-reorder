from engine.reorder import compute_coverage_days


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
