# T09: Daily Stock Position Reconstruction

## Prerequisites
- T08 completed (transactions loaded in database)

## Objective
Implement the algorithm that reconstructs daily stock levels for every SKU from opening balance + cumulative transactions.

## File to Create

### `engine/stock_position.py`

#### Main Function: `reconstruct_daily_positions(...) -> list[dict]`

```python
def reconstruct_daily_positions(
    stock_item_name: str,
    opening_balance: float,
    opening_date: date,      # FY start: 2025-04-01
    transactions: list,       # Sorted by date, each has: date, quantity, is_inward, channel, voucher_type
    end_date: date            # Today
) -> list[dict]:
```

**Algorithm:**
1. Start with `running_balance = opening_balance` on `opening_date`
2. For each day from `opening_date` to `end_date`:
   - Sum all transactions for that day
   - Apply channel rules (see below)
   - Record: opening_qty, inward_qty, outward_qty, closing_qty, channel breakdowns, is_in_stock
   - Update running_balance for next day

**Channel rules for balance and velocity:**

| Channel | Affects Balance? | Counted as Demand? | How |
|---------|-----------------|-------------------|-----|
| supplier | Yes (inward) | No | day_inward += qty |
| wholesale | Yes (outward) | Yes | day_outward += qty, day_wholesale_out += qty |
| online | Yes (outward) | Yes | day_outward += qty, day_online_out += qty |
| store | Yes (outward) | Yes | day_outward += qty, day_store_out += qty |
| internal | **NO** | No | Skip entirely (Art Lounge India - Purchase = accounting entries) |
| ignore (Physical Stock) | Yes | **No** | Apply to balance (day_inward or day_outward) but NOT to wholesale/online/store_out |

**Credit Note handling:**
- Voucher type "Credit Note" = returns. Treat as inward for balance (stock comes back).
- Do NOT count in any velocity metric.

```python
if txn['voucher_type'] == 'Credit Note':
    day_inward += txn['quantity']
    # Don't add to any channel outward — it's a return, not demand
```

**Output per day:**
```python
{
    'stock_item_name': str,
    'position_date': date,
    'opening_qty': float,
    'inward_qty': float,
    'outward_qty': float,
    'closing_qty': float,
    'wholesale_out': float,
    'online_out': float,
    'store_out': float,
    'is_in_stock': bool,  # closing_qty > 0
}
```

#### Helper: `upsert_daily_positions(db_conn, positions: list[dict])`
- Bulk insert into `daily_stock_positions` table
- Use `ON CONFLICT (stock_item_name, position_date) DO UPDATE`

#### Helper: `fetch_transactions_for_item(db_conn, stock_item_name: str) -> list[dict]`
- Query transactions table for this SKU
- Order by txn_date, id
- Return list of dicts with: date, quantity, is_inward, channel, voucher_type

## Test Case: Speedball Sealer

SKU: "Speedball Monalisa Gold Leaf Sealer Waterbased 2 Oz"

Expected results:
- Opening balance: 45 (Apr 1, 2025)
- Apr 1 - Jun 7: In stock (68 days, balance > 0)
- Jun 8 (Physical Stock adjustment of 45 out): balance drops to 0
- Jun 8 - Nov 25: Out of stock (171 days, balance <= 0)
- Nov 26 (Import +250): back in stock
- Nov 26 - Feb 24: In stock (91 days)
- Feb 24 closing: 18 units

Key assertions:
1. Physical Stock on Jun 8 zeroes balance but is NOT in wholesale_out/online_out
2. Art Lounge India - Purchase entries are completely skipped
3. Credit Note on Dec 18 (+60) increases balance, is NOT in any outward channel
4. MAGENTO2 entries go to online_out
5. All other customer entries go to wholesale_out

## Acceptance Criteria
- [ ] Algorithm walks day-by-day from opening_date to end_date
- [ ] Internal channel transactions completely skipped
- [ ] Physical Stock adjustments affect balance but not channel demand breakdowns
- [ ] Credit Notes treated as inward for balance, excluded from demand
- [ ] `is_in_stock` = True only when closing_qty > 0
- [ ] Database upsert handles re-computation without duplicates
- [ ] Test case: Speedball Sealer shows 159 total in-stock days (68 + 91)
