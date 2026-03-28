# Investigation: SKU 1414644 (WN WOC 37ML TITANIUM WHITE) — 3-Unit Reconciliation Gap

## Summary

SKU 1414644 has a 3-unit gap between our ledger-derived stock (816) and UC physical stock (813). This document traces every movement to help the operations team identify the process issue.

## UC Physical Stock (Verified from Screenshots — March 28, 2026)

### PPETPL Bhiwandi
| Shelf | Total (Stock on Hand) | Available (ATP) | Blocked (Committed) |
|-------|----------------------|-----------------|---------------------|
| A16301 | 142 | 136 | 6 |
| E12402 | 2 | 2 | 0 |
| E02401 | 21 | 21 | 0 |
| F14201 | 600 | 600 | 0 |
| Z01101 | 36 | 36 | 0 |
| **Total** | **801** | **795** | **6** |

### PPETPL Kala Ghoda
| Shelf | Total | Available (ATP) | Blocked |
|-------|-------|-----------------|---------|
| DEFAULT | 12 | 10 | 2 |

### Art Lounge Bhiwandi
Nothing.

### Total Physical: 813 (801 + 12 + 0)

## Ledger-Derived Stock: 816

Using the hybrid formula (BHW PICKLIST for demand, KG Shipping Packages for demand):

### Bhiwandi (ppetpl) — 804 net (vs UC physical 801, diff +3)
| Entity | Net | Notes |
|--------|-----|-------|
| INVENTORY_ADJUSTMENT (ADD) | +1,304 | Initial stock load + corrections |
| INVENTORY_ADJUSTMENT (REMOVE/REPLACE) | -7 | Stock corrections |
| GRN | +21 | 1 purchase receipt |
| OUTBOUND_GATEPASS | -12 | 2 transfers to Kala Ghoda |
| PICKLIST | -522 | Physical picks (demand at BHW) |
| PUTAWAY_CANCELLED_ITEM | +12 | Cancelled picks returned to shelf |
| PUTAWAY_CIR | +1 | 1 customer return |
| PUTAWAY_PICKLIST_ITEM | +7 | Pick correction returns |
| **Net** | **804** | |

### Kala Ghoda — 12 net (vs UC physical 12, **EXACT MATCH**)
| Entity | Net | Notes |
|--------|-----|-------|
| INBOUND_GATEPASS | +12 | Transfers from BHW |
| INVENTORY_ADJUSTMENT | +7 | Stock adjustments |
| KG Shipping Packages dispatched | -7 | 7 counter sales |
| **Net** | **12** | |

### Ali Bhiwandi — 0 net (**EXACT MATCH**)

## The 3-Unit Gap at Bhiwandi

### What We Found

The last PICKLIST entry for 1414644 at Bhiwandi is **PK3375 on March 21, 2026**.

However, **two shipping packages were dispatched AFTER March 21** with no corresponding PICKLIST entries in the Transaction Ledger:

| Package | Qty | Dispatch Date | PICKLIST Entry? |
|---------|-----|---------------|-----------------|
| PPET09614 | 3 | March 23, 2026 11:48 UTC | **NONE** |
| PPET09615 | 3 | March 24, 2026 11:38 UTC | **NONE** |

These 6 items were physically picked, packed, and dispatched to customers, but the Transaction Ledger has **no PICKLIST record** for them.

### The Math

If we add these 6 missing dispatches to our formula:
- 804 (current net) - 6 (missing demand) = **798**
- But UC physical is **801**
- Corrected diff: **798 - 801 = -3** (now we're 3 SHORT)

This means approximately **3 units also arrived** between March 21-28 (via GRN or adjustment) that the Transaction Ledger also didn't capture. UC shows `putawayPending=1` at Bhiwandi, suggesting at least 1 item was recently received.

### Net Gap Breakdown
| Factor | Units | Direction |
|--------|-------|-----------|
| Dispatched without PICKLIST (PPET09614 + PPET09615) | 6 | Should REDUCE our stock |
| Unreported arrival (estimated) | ~3 | Should INCREASE our stock |
| **Net unexplained** | **3** | Our stock is 3 too high |

## Questions for the Operations Team

1. **PPET09614 and PPET09615** — These packages were dispatched on March 23-24 for SKU 1414644. Can you check:
   - Were these orders processed through the normal pick-pack-ship flow?
   - Was there a picklist created for these? If so, which picklist number?
   - Is it possible these were packed directly from receiving (bypassing the normal picklist process)?

2. **Recent GRN** — The ledger shows GRN G0681 on March 6 was the last purchase receipt. But `putawayPending=1` suggests something was received recently. Was there a GRN between March 21-28 that might not have hit the Transaction Ledger yet?

3. **Process question** — Is there ever a scenario where items are dispatched without going through the standard PICKLIST process in Unicommerce? For example:
   - Direct packing from a gatepass receipt
   - Manual dispatch override
   - Consolidation of multiple small orders into one package

4. **Shelf Z01101** — This shelf has 36 units. Is this a receiving/staging shelf? Could these be items recently received that haven't been formally put away?

## Impact on Reorder System

- **Velocity accuracy:** The 6 missing PICKLIST entries mean we undercount demand by ~1.1% for this SKU (6 out of 528 total picks). This slightly underestimates velocity.
- **Stock accuracy:** Using UC snapshot for current stock (813 physical, 805 sellable) is exact. The 3-unit gap only exists in our reconstructed position history, not in the current stock number.
- **Reorder decision:** For a 90-day lead time with velocity ~2/day, the reorder point is ~180 units. Current stock is 805. Days to stockout = ~402. The 3-unit error changes this by ~1.5 days — negligible.

## Recommendation

1. Investigate why PPET09614/PPET09615 have no PICKLIST entries — this may indicate a process gap in Unicommerce or a warehouse workflow that bypasses the standard flow.
2. If this is a known workflow (e.g., direct packing), document it so the system can supplement PICKLIST data with Shipping Package dispatches for affected SKUs.
3. The current 3-unit gap (0.37%) does not materially affect reorder decisions but should be monitored at scale (50+ SKU validation) to ensure it's not systematic.
