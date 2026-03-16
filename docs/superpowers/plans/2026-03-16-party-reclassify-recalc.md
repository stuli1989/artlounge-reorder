# Party Reclassification Fix — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a user reclassifies a party's channel via the UI, (a) the change persists across nightly syncs and (b) all affected SKU metrics recalculate immediately.

**Architecture:** Add `is_manual` flag to parties table so auto-classification skips manually-set parties. After reclassification, find affected SKUs and run a targeted recompute (positions → velocity → WMA → reorder status → brand rollup) synchronously in the API endpoint.

**Tech Stack:** Python, FastAPI, PostgreSQL, psycopg2

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/db/migration_v5_manual_party.sql` | Add `is_manual` column to parties |
| Modify | `src/extraction/party_classifier.py` | Skip `is_manual=true` in auto-classify |
| Modify | `src/api/routes/parties.py` | Set `is_manual`, trigger targeted recalc |
| Create | `src/engine/targeted_recompute.py` | Recompute positions + metrics for a set of SKUs |
| Create | `src/tests/test_targeted_recompute.py` | Tests for targeted recompute |
| Create | `src/tests/test_manual_party_override.py` | Tests for is_manual flag behavior |

---

### Task 1: DB Migration — add `is_manual` to parties

**Files:**
- Create: `src/db/migration_v5_manual_party.sql`

- [ ] **Step 1: Write migration SQL**

```sql
-- migration_v5_manual_party.sql
-- Add is_manual flag to parties so manual UI reclassifications survive nightly auto-classify

ALTER TABLE parties ADD COLUMN IF NOT EXISTS is_manual BOOLEAN DEFAULT FALSE;

-- Mark parties that were already manually classified (have classified_at set
-- and aren't using a default auto-classification rule) as manual.
-- Conservative: don't auto-set is_manual for existing rows; only new UI saves set it.
```

- [ ] **Step 2: Run migration**

Run: `PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -f src/db/migration_v5_manual_party.sql`
Expected: `ALTER TABLE` success

- [ ] **Step 3: Verify column exists**

Run: `PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "\d parties"`
Expected: `is_manual` column with type `boolean`, default `false`

- [ ] **Step 4: Commit**

```bash
git add src/db/migration_v5_manual_party.sql
git commit -m "feat: add is_manual column to parties table for manual override persistence"
```

---

### Task 2: Party classifier — respect `is_manual` flag

**Files:**
- Modify: `src/extraction/party_classifier.py:85-119` (`auto_classify_all_parties`)

- [ ] **Step 1: Write test for is_manual skip behavior**

Create `src/tests/test_manual_party_override.py`:

```python
"""Tests that auto-classification skips manually-classified parties."""
import pytest
from unittest.mock import MagicMock, patch
from extraction.party_classifier import auto_classify_all_parties, classify_party


def test_auto_classify_skips_manual_parties(tmp_path):
    """auto_classify_all_parties should only process unclassified AND non-manual parties."""
    # The function queries WHERE channel = 'unclassified' AND (is_manual IS NOT TRUE)
    # We verify the SQL includes the is_manual check by inspecting the call
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    # No unclassified parties
    mock_cursor.fetchall.return_value = []

    result = auto_classify_all_parties(mock_conn)
    assert result == {}

    # Verify the SQL used includes is_manual filter
    call_args = mock_cursor.execute.call_args_list[0]
    sql = call_args[0][0]
    assert "is_manual" in sql, "auto_classify query must filter out is_manual parties"


def test_classify_party_art_lounge_india_default():
    """Art Lounge India defaults to internal via EXACT_PARTY_RULES."""
    channel, confidence = classify_party("Art Lounge India")
    assert channel == "internal"
    assert confidence == "high"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_manual_party_override.py -v`
Expected: FAIL — the current SQL doesn't include `is_manual`

- [ ] **Step 3: Update `auto_classify_all_parties` to skip manual parties**

In `src/extraction/party_classifier.py`, change the query at line 92-96 from:
```python
cur.execute("""
    SELECT tally_name, tally_parent FROM parties
    WHERE channel = 'unclassified'
""")
```
to:
```python
cur.execute("""
    SELECT tally_name, tally_parent FROM parties
    WHERE channel = 'unclassified'
      AND (is_manual IS NOT TRUE)
""")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_manual_party_override.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/extraction/party_classifier.py src/tests/test_manual_party_override.py
git commit -m "feat: auto_classify_all_parties skips manually-classified parties"
```

---

### Task 3: Targeted recompute function

**Files:**
- Create: `src/engine/targeted_recompute.py`
- Create: `src/tests/test_targeted_recompute.py`

This is the core new code. It recomputes positions, velocity, WMA, reorder status, and brand rollups for a specific set of SKUs. It does NOT re-run ABC/XYZ (those are relative rankings needing all items — they update on next nightly sync).

- [ ] **Step 1: Write test**

Create `src/tests/test_targeted_recompute.py`:

```python
"""Tests for targeted SKU recompute after party reclassification."""
import pytest
from unittest.mock import MagicMock, patch, call
from engine.targeted_recompute import find_affected_skus, recompute_skus_for_party


def test_find_affected_skus():
    """Should return distinct SKU names for a party."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchall.return_value = [
        ("SKU-A",), ("SKU-B",), ("SKU-C",),
    ]

    result = find_affected_skus(mock_conn, "Art Lounge India")
    assert result == ["SKU-A", "SKU-B", "SKU-C"]

    sql = mock_cursor.execute.call_args[0][0]
    assert "stock_item_name" in sql
    assert "party_name" in sql
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_targeted_recompute.py::test_find_affected_skus -v`
Expected: FAIL — module doesn't exist yet

- [ ] **Step 3: Implement `targeted_recompute.py`**

Create `src/engine/targeted_recompute.py`:

```python
"""
Targeted recompute — recomputes positions + metrics for specific SKUs.

Used after party reclassification to immediately update affected SKU metrics
without running the full computation pipeline.

Skips ABC/XYZ classification (relative rankings need all items — updated on next nightly sync).
"""
from datetime import date, timedelta

from config.settings import FY_START_DATE
from engine.stock_position import reconstruct_daily_positions, upsert_daily_positions
from engine.velocity import (
    calculate_velocity,
    fetch_batch_wma_velocities,
    velocities_from_batch_row,
    detect_trend,
)
from engine.reorder import (
    calculate_days_to_stockout,
    compute_coverage_days,
    detect_import_history,
    determine_reorder_status,
    must_stock_fallback_qty,
    DEFAULT_LEAD_TIME,
)
from engine.pipeline import (
    batch_upsert_sku_metrics,
    batch_upsert_brand_metrics,
    fetch_sku_metrics_for_category,
    compute_last_sale_date,
    compute_zero_activity_days,
    _fetch_dead_stock_threshold,
    _fetch_slow_mover_threshold,
)
from engine.aggregation import compute_brand_metrics
from engine.classification import (
    compute_safety_buffer,
    fetch_buffer_settings,
    fetch_classification_settings,
    fetch_use_xyz_global,
)


def find_affected_skus(db_conn, party_name: str) -> list[str]:
    """Find all SKUs that have transactions with the given party."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT stock_item_name FROM transactions WHERE party_name = %s",
            (party_name,),
        )
        return [row[0] for row in cur.fetchall()]


def find_affected_categories(db_conn, sku_names: list[str]) -> set[str]:
    """Find category names for the given SKUs."""
    if not sku_names:
        return set()
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT category_name FROM stock_items WHERE tally_name = ANY(%s)",
            (sku_names,),
        )
        return {row[0] for row in cur.fetchall()}


def recompute_skus_for_party(db_conn, party_name: str) -> dict:
    """
    Recompute positions + metrics for all SKUs affected by a party reclassification.

    Returns summary: {skus_recomputed, brands_recomputed, affected_skus}
    """
    today = date.today()
    fy_start = FY_START_DATE

    # 1. Find affected SKUs
    sku_names = find_affected_skus(db_conn, party_name)
    if not sku_names:
        return {"skus_recomputed": 0, "brands_recomputed": 0, "affected_skus": []}

    # 2. Load stock items for affected SKUs
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT tally_name, category_name, opening_balance, closing_balance,
                   reorder_intent, is_active, use_xyz_buffer
            FROM stock_items
            WHERE tally_name = ANY(%s)
        """, (sku_names,))
        cols = [d[0] for d in cur.description]
        items = []
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["opening_balance"] = float(d["opening_balance"] or 0)
            d["closing_balance"] = float(d["closing_balance"] or 0)
            items.append(d)

    # 3. Load transactions for affected SKUs
    from collections import defaultdict
    all_txns = defaultdict(list)
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT stock_item_name, txn_date AS date, quantity, is_inward,
                   channel, voucher_type, party_name, amount
            FROM transactions
            WHERE stock_item_name = ANY(%s)
            ORDER BY stock_item_name, txn_date, id
        """, (sku_names,))
        cols_t = [desc[0] for desc in cur.description]
        for row in cur.fetchall():
            d = dict(zip(cols_t, row))
            d["quantity"] = float(d["quantity"])
            item_name = d.pop("stock_item_name")
            all_txns[item_name].append(d)

    # 4. Load supplier mappings for affected categories
    categories = find_affected_categories(db_conn, sku_names)
    supplier_map = {}
    if categories:
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT sc.tally_name AS category_name,
                       s.name, s.lead_time_default, s.lead_time_sea, s.lead_time_air,
                       s.buffer_override, s.typical_order_months
                FROM stock_categories sc
                JOIN suppliers s ON UPPER(s.name) = UPPER(sc.tally_name)
                WHERE sc.tally_name = ANY(%s)
            """, (list(categories),))
            for row in cur.fetchall():
                supplier_map[row[0]] = {
                    "name": row[1],
                    "lead_time_default": row[2],
                    "lead_time_sea": row[3],
                    "lead_time_air": row[4],
                    "buffer_override": float(row[5]) if row[5] is not None else None,
                    "typical_order_months": row[6],
                }

    # 5. Pre-fetch settings
    buffer_settings = fetch_buffer_settings(db_conn)
    class_settings = fetch_classification_settings(db_conn)
    use_xyz_global = fetch_use_xyz_global(db_conn)

    # 6. Recompute positions + velocity for each SKU
    metrics_batch = []
    for item in items:
        txns = all_txns.get(item["tally_name"], [])
        current_stock = item["closing_balance"] or 0

        if not txns:
            metrics_batch.append(_empty_metrics(item, current_stock))
            continue

        # Reconstruct daily positions
        positions = reconstruct_daily_positions(
            stock_item_name=item["tally_name"],
            closing_balance=current_stock,
            opening_date=fy_start,
            transactions=txns,
            end_date=today,
            tally_opening=item["opening_balance"],
        )
        upsert_daily_positions(db_conn, positions)

        # Flat velocity
        velocity = calculate_velocity(item["tally_name"], positions)

        # Dead stock metrics
        last_sale_date = compute_last_sale_date(txns)
        opening_gap = (item["opening_balance"] or 0) - positions[0]["opening_qty"] if positions else 0.0
        zero_activity_days = compute_zero_activity_days(positions, opening_gap)

        # Import history
        import_history = detect_import_history(item["tally_name"], txns)

        # Supplier lead time
        supplier = supplier_map.get(item["category_name"])
        lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME
        coverage = compute_coverage_days(
            lead_time,
            supplier["typical_order_months"] if supplier else None,
        )

        # Days to stockout
        days_to_stockout = calculate_days_to_stockout(current_stock, velocity["total_velocity"])

        # Reorder status (preliminary)
        status, suggested_qty = determine_reorder_status(
            current_stock, days_to_stockout, lead_time, velocity["total_velocity"],
            coverage_period=coverage,
        )

        # Intent override
        intent = item.get("reorder_intent", "normal")
        if intent == "must_stock" and status in ("no_data", "out_of_stock"):
            status = "critical"
            if suggested_qty is None:
                suggested_qty = must_stock_fallback_qty(lead_time + coverage)
        elif intent == "do_not_reorder":
            status = "no_data"
            suggested_qty = None

        stockout_date = None
        if days_to_stockout is not None and days_to_stockout > 0:
            stockout_date = today + timedelta(days=int(days_to_stockout))

        m = {
            "stock_item_name": item["tally_name"],
            "category_name": item["category_name"],
            "current_stock": current_stock,
            **velocity,
            "days_to_stockout": days_to_stockout,
            "estimated_stockout_date": stockout_date,
            "last_import_date": import_history.get("last_import_date"),
            "last_import_qty": import_history.get("last_import_qty"),
            "last_import_supplier": import_history.get("last_import_supplier"),
            "reorder_status": status,
            "reorder_qty_suggested": suggested_qty,
            "last_sale_date": last_sale_date,
            "total_zero_activity_days": zero_activity_days,
        }
        metrics_batch.append(m)

    # 7. WMA velocity + trend (read from just-written positions)
    wma_window = int(class_settings.get("wma_window_days", 90))
    trend_up = class_settings.get("trend_up_threshold", 1.2)
    trend_down = class_settings.get("trend_down_threshold", 0.8)

    sku_names_with_velocity = [m["stock_item_name"] for m in metrics_batch if m.get("total_velocity", 0) > 0]
    wma_by_sku = {}
    if sku_names_with_velocity:
        with db_conn.cursor() as cur:
            wma_by_sku = fetch_batch_wma_velocities(cur, sku_names_with_velocity, today, wma_window)

    for m in metrics_batch:
        wma_row = wma_by_sku.get(m["stock_item_name"])
        if wma_row:
            wma_w, wma_o, wma_s, wma_t = velocities_from_batch_row(wma_row)
            m["wma_wholesale_velocity"] = round(wma_w, 4)
            m["wma_online_velocity"] = round(wma_o, 4)
            m["wma_total_velocity"] = round(wma_t, 4)
        else:
            m["wma_wholesale_velocity"] = 0
            m["wma_online_velocity"] = 0
            m["wma_total_velocity"] = 0

        flat_total = m.get("total_velocity", 0)
        wma_total = m.get("wma_total_velocity", 0)
        direction, ratio = detect_trend(flat_total, wma_total, trend_up, trend_down)
        m["trend_direction"] = direction
        m["trend_ratio"] = ratio

    # 8. Safety buffer recomputation (preserve existing ABC/XYZ from DB)
    existing_class = {}
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT stock_item_name, abc_class, xyz_class, demand_cv, total_revenue
            FROM sku_metrics WHERE stock_item_name = ANY(%s)
        """, (sku_names,))
        for row in cur.fetchall():
            existing_class[row[0]] = {
                "abc_class": row[1], "xyz_class": row[2],
                "demand_cv": float(row[3]) if row[3] else None,
                "total_revenue": float(row[4]) if row[4] else 0,
            }

    stock_items_by_name = {item["tally_name"]: item for item in items}
    for m in metrics_batch:
        ec = existing_class.get(m["stock_item_name"], {})
        m["abc_class"] = ec.get("abc_class", "C")
        m["xyz_class"] = ec.get("xyz_class")
        m["demand_cv"] = ec.get("demand_cv")
        m["total_revenue"] = ec.get("total_revenue", 0)

        abc = m["abc_class"]
        xyz = m["xyz_class"]
        item_data = stock_items_by_name.get(m["stock_item_name"], {})
        item_xyz_pref = item_data.get("use_xyz_buffer")
        use_xyz = item_xyz_pref if item_xyz_pref is not None else use_xyz_global
        buf = compute_safety_buffer(abc, xyz, buffer_settings, use_xyz=use_xyz)

        supplier = supplier_map.get(m["category_name"])
        if supplier and supplier.get("buffer_override") is not None:
            buf = supplier["buffer_override"]
        m["safety_buffer"] = buf

        # Final reorder status with safety buffer
        current_stock = m["current_stock"]
        total_vel = m["total_velocity"]
        lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME
        coverage = compute_coverage_days(
            lead_time,
            supplier["typical_order_months"] if supplier else None,
        )
        days_to_stockout = calculate_days_to_stockout(current_stock, total_vel)

        status, suggested_qty = determine_reorder_status(
            current_stock, days_to_stockout, lead_time, total_vel,
            safety_buffer=buf, coverage_period=coverage,
        )

        intent = item_data.get("reorder_intent", "normal")
        if intent == "must_stock" and status in ("no_data", "out_of_stock"):
            status = "critical"
            if suggested_qty is None:
                suggested_qty = must_stock_fallback_qty(lead_time + coverage)
        elif intent == "do_not_reorder":
            status = "no_data"
            suggested_qty = None

        m["days_to_stockout"] = days_to_stockout
        m["reorder_status"] = status
        m["reorder_qty_suggested"] = suggested_qty
        if days_to_stockout is not None and days_to_stockout > 0:
            m["estimated_stockout_date"] = today + timedelta(days=int(days_to_stockout))
        else:
            m["estimated_stockout_date"] = None

    # 9. Batch upsert SKU metrics
    batch_upsert_sku_metrics(db_conn, metrics_batch)
    db_conn.commit()

    # 10. Brand rollups for affected categories
    dead_stock_threshold = _fetch_dead_stock_threshold(db_conn)
    slow_mover_threshold = _fetch_slow_mover_threshold(db_conn)
    brand_batch = []
    for cat_name in categories:
        sku_metrics = fetch_sku_metrics_for_category(db_conn, cat_name)
        supplier = supplier_map.get(cat_name)
        brand_data = compute_brand_metrics(
            cat_name, sku_metrics, supplier,
            dead_stock_threshold=dead_stock_threshold,
            slow_mover_threshold=slow_mover_threshold,
            today=today,
        )
        brand_batch.append(brand_data)
    batch_upsert_brand_metrics(db_conn, brand_batch)
    db_conn.commit()

    return {
        "skus_recomputed": len(metrics_batch),
        "brands_recomputed": len(categories),
        "affected_skus": sku_names,
    }


def _empty_metrics(item: dict, current_stock: float) -> dict:
    """Return zero-velocity metrics for an item with no transactions."""
    return {
        "stock_item_name": item["tally_name"],
        "category_name": item["category_name"],
        "current_stock": current_stock,
        "wholesale_velocity": 0, "online_velocity": 0, "total_velocity": 0,
        "total_in_stock_days": 0,
        "velocity_start_date": None, "velocity_end_date": None,
        "days_to_stockout": None, "estimated_stockout_date": None,
        "last_import_date": None, "last_import_qty": None, "last_import_supplier": None,
        "reorder_status": "out_of_stock" if current_stock <= 0 else "no_data",
        "reorder_qty_suggested": None,
        "last_sale_date": None, "total_zero_activity_days": 0,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_targeted_recompute.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/engine/targeted_recompute.py src/tests/test_targeted_recompute.py
git commit -m "feat: targeted recompute function for party reclassification"
```

---

### Task 4: Update reclassify API endpoint

**Files:**
- Modify: `src/api/routes/parties.py:62-89`

- [ ] **Step 1: Update the classify endpoint to set `is_manual` and trigger recompute**

Replace the `classify_party` function in `src/api/routes/parties.py` (lines 62-89) with:

```python
@router.post("/parties/classify")
def classify_party(req: ClassifyRequest, user: dict = Depends(require_role("purchaser"))):
    """Classify a party's channel, update transactions, and recompute affected SKU metrics."""
    if req.channel not in VALID_CHANNELS:
        raise HTTPException(400, f"Invalid channel '{req.channel}'. Must be one of: {', '.join(sorted(VALID_CHANNELS))}")

    with get_db() as conn:
        with conn.cursor() as cur:
            # Update party with is_manual flag
            cur.execute("""
                UPDATE parties SET channel = %s, classified_at = NOW(), is_manual = TRUE
                WHERE tally_name = %s
            """, (req.channel, req.tally_name))

            if cur.rowcount == 0:
                raise HTTPException(404, f"Party '{req.tally_name}' not found")

            # Update transactions for this party
            cur.execute("""
                UPDATE transactions SET channel = %s
                WHERE party_name = %s
            """, (req.channel, req.tally_name))
            txn_updated = cur.rowcount

        conn.commit()

        # Trigger targeted recompute for affected SKUs
        from engine.targeted_recompute import recompute_skus_for_party
        recompute_result = recompute_skus_for_party(conn, req.tally_name)

    return {
        "success": True,
        "party": req.tally_name,
        "channel": req.channel,
        "transactions_updated": txn_updated,
        **recompute_result,
    }
```

- [ ] **Step 2: Run existing tests**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/ -v -x --timeout=30`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add src/api/routes/parties.py
git commit -m "feat: reclassify endpoint sets is_manual and triggers targeted recompute"
```

---

### Task 5: Integration verification — reclassify Art Lounge India and check results

- [ ] **Step 1: Check current state before reclassification**

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "
SELECT tally_name, channel, is_manual FROM parties WHERE tally_name = 'Art Lounge India';
"
```
Expected: `internal`, `false`

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "
SELECT total_velocity, wholesale_velocity, online_velocity FROM sku_metrics
WHERE stock_item_name = 'WN AOC 37ML TITAN.W NY-1214';
"
```
Expected: total_velocity = 1.0058 (the old number based on 349 units)

- [ ] **Step 2: Run the reclassify via Python directly (since API may not be running)**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -c "
from api.database import get_db
from engine.targeted_recompute import recompute_skus_for_party

with get_db() as conn:
    with conn.cursor() as cur:
        cur.execute(\"\"\"
            UPDATE parties SET channel = 'online', classified_at = NOW(), is_manual = TRUE
            WHERE tally_name = 'Art Lounge India'
        \"\"\")
        cur.execute(\"\"\"
            UPDATE transactions SET channel = 'online'
            WHERE party_name = 'Art Lounge India'
        \"\"\")
    conn.commit()
    result = recompute_skus_for_party(conn, 'Art Lounge India')
    print(f'Recomputed: {result}')
"
```

- [ ] **Step 3: Verify updated metrics**

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "
SELECT tally_name, channel, is_manual FROM parties WHERE tally_name = 'Art Lounge India';
"
```
Expected: `online`, `true`

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "
SELECT total_velocity, wholesale_velocity, online_velocity,
       total_velocity * 347 AS implied_total_units
FROM sku_metrics
WHERE stock_item_name = 'WN AOC 37ML TITAN.W NY-1214';
"
```
Expected: `total_velocity` should now be higher (~490/347 ≈ 1.41), with online_velocity increased significantly (was 0.0375, should now include the 141 Art Lounge India units).

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: party reclassification now persists and triggers immediate recalculation

- Added is_manual flag to parties table (migration_v5)
- auto_classify_all_parties skips is_manual parties
- /parties/classify sets is_manual and triggers targeted recompute
- Targeted recompute rebuilds positions, velocity, WMA, reorder status, brand rollups
- Verified with Art Lounge India reclassification: velocity now includes internal-turned-online units"
```
