"""Tests for backdate_physical_stock preprocessing."""
from datetime import date
from engine.backdate_physical_stock import adjust_opening_for_physical_stock


def _txn(d, qty, inward=True, vtype="Physical Stock", channel="ignore", party=""):
    return {
        "date": d, "quantity": qty, "is_inward": inward,
        "voucher_type": vtype, "channel": channel,
        "party_name": party, "phys_stock_diff": None,
    }


def test_zero_opening_with_grace_period_physical_stock():
    """Item with opening=0 and Physical Stock on Jun 9 -> opening becomes 3, PhysStock removed."""
    txns = [
        _txn(date(2025, 6, 9), 3.0),
        _txn(date(2025, 8, 31), 2.0, inward=False, vtype="Sales Store", channel="store"),
    ]
    adj_opening, adj_txns = adjust_opening_for_physical_stock(
        opening_balance=0.0, transactions=txns, fy_start=date(2025, 4, 1), grace_days=90,
    )
    assert adj_opening == 3.0
    assert len(adj_txns) == 1
    assert adj_txns[0]["voucher_type"] == "Sales Store"


def test_multiple_physical_stock_uses_last_value():
    """Multiple SET-TO entries in grace period -> use last one's quantity."""
    txns = [
        _txn(date(2025, 6, 8), 0.0),
        _txn(date(2025, 6, 9), 0.0),
        _txn(date(2025, 6, 9), 3.0),
        _txn(date(2025, 8, 31), 1.0, inward=False, vtype="Sales Store", channel="store"),
    ]
    adj_opening, adj_txns = adjust_opening_for_physical_stock(
        opening_balance=0.0, transactions=txns, fy_start=date(2025, 4, 1), grace_days=90,
    )
    assert adj_opening == 3.0
    assert len(adj_txns) == 1


def test_nonzero_opening_not_affected():
    """Item with opening > 0 is never affected, even if it has Physical Stock."""
    txns = [
        _txn(date(2025, 6, 8), 5.0),
        _txn(date(2025, 8, 31), 1.0, inward=False, vtype="Sales Store", channel="store"),
    ]
    adj_opening, adj_txns = adjust_opening_for_physical_stock(
        opening_balance=7.0, transactions=txns, fy_start=date(2025, 4, 1), grace_days=90,
    )
    assert adj_opening == 7.0
    assert len(adj_txns) == 2


def test_physical_stock_outside_grace_not_affected():
    """Physical Stock after grace period is not removed."""
    txns = [
        _txn(date(2025, 9, 1), 5.0),
        _txn(date(2025, 10, 1), 1.0, inward=False, vtype="Sales Store", channel="store"),
    ]
    adj_opening, adj_txns = adjust_opening_for_physical_stock(
        opening_balance=0.0, transactions=txns, fy_start=date(2025, 4, 1), grace_days=90,
    )
    assert adj_opening == 0.0
    assert len(adj_txns) == 2


def test_mixed_grace_and_midyear_physical_stock():
    """Grace-period Physical Stock is backdated, mid-year corrections stay."""
    txns = [
        _txn(date(2025, 6, 8), 0.0),
        _txn(date(2025, 6, 9), 3.0),
        _txn(date(2025, 8, 31), 1.0, inward=False, vtype="Sales Store", channel="store"),
        _txn(date(2025, 9, 1), 4.0),
    ]
    adj_opening, adj_txns = adjust_opening_for_physical_stock(
        opening_balance=0.0, transactions=txns, fy_start=date(2025, 4, 1), grace_days=90,
    )
    assert adj_opening == 3.0
    assert len(adj_txns) == 2
    assert adj_txns[0]["voucher_type"] == "Sales Store"
    assert adj_txns[1]["voucher_type"] == "Physical Stock"
    assert adj_txns[1]["date"] == date(2025, 9, 1)


def test_no_physical_stock_at_all():
    """Item with no Physical Stock entries is not affected."""
    txns = [
        _txn(date(2025, 5, 1), 2.0, inward=False, vtype="Sales", channel="online"),
    ]
    adj_opening, adj_txns = adjust_opening_for_physical_stock(
        opening_balance=0.0, transactions=txns, fy_start=date(2025, 4, 1), grace_days=90,
    )
    assert adj_opening == 0.0
    assert len(adj_txns) == 1


def test_setting_disabled_returns_unchanged():
    """When enabled=False, return original values untouched."""
    txns = [
        _txn(date(2025, 6, 9), 3.0),
        _txn(date(2025, 8, 31), 1.0, inward=False, vtype="Sales Store", channel="store"),
    ]
    adj_opening, adj_txns = adjust_opening_for_physical_stock(
        opening_balance=0.0, transactions=txns, fy_start=date(2025, 4, 1), grace_days=90, enabled=False,
    )
    assert adj_opening == 0.0
    assert len(adj_txns) == 2
