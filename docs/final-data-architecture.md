# Final Data Architecture — UC Reorder Pipeline

## The Formula (Proven)

### Stock Calculation
```
Physical Stock = Backward walk from UC Inventory Snapshot
Sellable Stock = UC Inventory Snapshot `inventory` field (excludes blocked + bad)
```

### Daily Position History (for velocity)
```
Backward walk from today's snapshot:

For each day going backward:
  closing[today] = snapshot (physical = inventory + blocked + bad)
  closing[d-1]   = closing[d] + demand_on_d - supply_on_d

Where:
  demand_on_d = BHW PICKLIST from ledger (negative stock_change)
              + KG SP dispatches on day d
  supply_on_d = GRN, INVENTORY_ADJUSTMENT, GATEPASS, PUTAWAY_CIR/RTO from ledger
```

### Velocity
```
velocity = total_SP_dispatches / in_stock_days    (for KG demand)
         + total_PICKLIST / in_stock_days          (for BHW demand)

Channel assignment:
  BHW PICKLIST: channel from sale_order_code prefix (SO=wholesale, MA-=online, B2C=online)
  KG SP: channel from shipping package channel field (CUSTOM_SHOP=store, CUSTOM=wholesale, MAGENTO2=online)
```

## Data Sources & Nightly Sync

### 1. Transaction Ledger (Export Job API)
**Pull:** Nightly, last 3 days per facility, all 3 facilities
**Use for:**
- GRN (supplier inward) — dates, quantities ✅
- INVENTORY_ADJUSTMENT (stock loads, corrections) — dates, quantities ✅
- INBOUND/OUTBOUND_GATEPASS (inter-facility transfers) — dates, quantities ✅
- PUTAWAY_CIR/RTO (customer returns) — dates, quantities ✅
- PICKLIST at BHW (demand) — dates, quantities, sale order codes ✅
- PUTAWAY_CANCELLED_ITEM (cancelled pick returns) — dates, quantities ✅
- PUTAWAY_PICKLIST_ITEM (pick corrections) — dates, quantities ✅

**EXCLUDE:** INVOICES (broken quantities — inflated by varying multipliers)
**EXCLUDE:** PICKLIST at KG (incomplete — counter sales missing)

### 2. Shipping Package API (KG only)
**Pull:** Nightly, DISPATCHED status, PPETPLKALAGHODA facility
**Use for:** KG demand — dispatch dates, SKU quantities, channel
**Why:** Captures counter sales (CUSTOM_SHOP channel) that PICKLIST misses

### 3. Inventory Snapshot API
**Pull:** Nightly, all SKUs, all facilities
**Use for:**
- Current sellable stock (`inventory` field)
- Blocked items (`inventoryBlocked`)
- Bad inventory (`badInventory`)
- Backward walk anchor (physical = inventory + blocked + bad)

### 4. Catalog API
**Pull:** Nightly
**Use for:** SKU master (names, brands, MRP for ABC classification)

## Reconciliation Proof

| SKU | Day 0 (backward walk) | Expected | Status |
|-----|----------------------|----------|--------|
| 8811-2 | 0.0 | 0 | **PERFECT** |
| 2320617 | 0.0 | 0 | **PERFECT** |
| 3041981 | 0.0 | 0 | **PERFECT** |
| 839911C | 0.0 | 0 | **PERFECT** |
| 285585 | 0.0 | 0 | **PERFECT** |
| 3800-178 | 0.0 | 0 | **PERFECT** |
| KUP16X20 | 0.0 | 0 | **PERFECT** |
| 0308744 | 0.0 | 0 | **PERFECT** |
| HLB-W105 | 0.0 | 0 | **PERFECT** |
| L-525-4B | 0.0 | 0 | **PERFECT** |
| L-FT700-3-0-BK | 0.0 | 0 | **PERFECT** |
| 6312 | 0.0 | 0 | **PERFECT** (with API ledger data) |
| 1414644 | -3.0 | 0 | 3-unit gap (see investigation doc) |

**12/13 SKUs tally perfectly from Day 0 to today.**

## Key Findings From Investigation

1. **INVOICES in Transaction Ledger have broken quantities** — inflated by 1x, 4x, or 144x per invoice. Always exclude.

2. **PICKLIST at Kala Ghoda is incomplete** — counter sales (CUSTOM_SHOP channel) don't generate PICKLIST entries. Use Shipping Package API instead.

3. **PICKLIST at Bhiwandi is occasionally incomplete** — rare cases where items are dispatched without PICKLIST entries (see 1414644 investigation). ~0.3% error rate.

4. **Transaction Ledger API returns more complete data than CSV exports** — always use Export Job API, not manual CSV downloads.

5. **Ali Bhiwandi is stock-counting only** — 100% INVENTORY_ADJUSTMENT (weekly ADD/REMOVE cycles). No demand, no commerce.

6. **UC Inventory Snapshot is the only 100% accurate current stock source** — use for reorder calculations and as backward walk anchor.

## Architecture Diagram

```
                    NIGHTLY SYNC
                         |
         +-----------+---+---+-----------+
         |           |       |           |
    Ledger API    KG SP    Snapshot   Catalog
    (3 facilities) (KG only) (all)    (all)
         |           |       |           |
         v           v       v           v
    transactions   kg_demand  current   stock_items
    (non-INVOICES)  (correct   stock    (MRP, brands)
                    channel+qty)
         |           |       |
         +-----+-----+       |
               |              |
        Backward Walk    Anchor Point
        (day by day)     (today's physical)
               |
               v
      daily_stock_positions
               |
               v
      velocity, ABC/XYZ, reorder
               |
               v
         sku_metrics + brand_metrics
               |
               v
         FastAPI -> Dashboard
```

## What Changes From Current Pipeline

| Component | Current | New |
|-----------|---------|-----|
| Stock source | Ledger forward walk from 0 | Snapshot anchor + backward walk |
| BHW demand | PICKLIST from ledger | Same (no change) |
| KG demand | Excluded (INVOICES broken) | Shipping Package API |
| ALI handling | All ledger entities | Same (no change) |
| Current stock | Derived from formula | UC Snapshot `inventory` field |
| Position building | Forward walk | Backward walk from snapshot |
| INVOICES | Excluded | Still excluded |

## Remaining Work

1. Update pipeline to use backward walk instead of forward walk
2. Add KG Shipping Package pull to nightly sync
3. Add Inventory Snapshot pull for current stock + anchor
4. Scale validation: test 50+ SKUs across brands
5. Investigate 1414644 process gap with operations team
6. Deploy updated pipeline to Railway
