"""Backdate early Physical Stock entries as FY opening balance.

When enabled, items with zero opening balance that received Physical Stock
entries within a grace period from FY start have those entries treated as
the opening balance. The Physical Stock transactions within the grace window
are removed from the transaction list so they don't double-count.

This fixes velocity inflation caused by a late warehouse stock count:
the item appears to have stock from April 1 instead of June 8.
"""
from datetime import date, timedelta


def adjust_opening_for_physical_stock(
    opening_balance: float,
    transactions: list[dict],
    fy_start: date,
    grace_days: int = 90,
    enabled: bool = True,
) -> tuple[float, list[dict]]:
    """Adjust opening balance and filter transactions for backdate logic.

    Returns (adjusted_opening, filtered_transactions).
    If the feature is disabled, opening > 0, or no Physical Stock entries
    fall within the grace window, returns the inputs unchanged.
    """
    if not enabled or opening_balance != 0:
        return opening_balance, transactions

    grace_cutoff = fy_start + timedelta(days=grace_days)

    # Find Physical Stock SET-TO entries within grace period
    grace_phys = []
    for t in transactions:
        if (t["voucher_type"] == "Physical Stock"
                and t["date"] < grace_cutoff
                and t.get("phys_stock_diff") is None):  # SET-TO only, not additive
            grace_phys.append(t)

    if not grace_phys:
        return opening_balance, transactions

    # Use the last SET-TO value as the effective opening balance
    adjusted_opening = grace_phys[-1]["quantity"]

    # Remove grace-period Physical Stock from the transaction list
    grace_set = set(id(t) for t in grace_phys)
    filtered_txns = [t for t in transactions if id(t) not in grace_set]

    return adjusted_opening, filtered_txns
