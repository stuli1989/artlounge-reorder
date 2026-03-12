# Tally Data Analysis Findings
## Art Lounge Reorder System -- Pre-Pipeline Validation

**Date:** March 11, 2026
**Data:** FY 2025-26 (April 10, 2025 -- March 11, 2026)
**Source:** 4 XML exports from Tally Prime via TDL Collections

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Finding 1: Stock Balance Reconstruction is Broken (CRITICAL)](#2-finding-1-stock-balance-reconstruction-is-broken)
3. [Finding 2: Physical Stock Vouchers Have Hidden Data](#3-finding-2-physical-stock-vouchers-have-hidden-data)
4. [Finding 3: Sales-Tally is NOT Just Wholesale](#4-finding-3-sales-tally-is-not-just-wholesale)
5. [Finding 4: Duplicate Line Items Need Rate-Aware Handling](#5-finding-4-duplicate-line-items-need-rate-aware-handling)
6. [Finding 5: Channel Classification Ruleset](#6-finding-5-channel-classification-ruleset)
7. [Finding 6: Credit Notes & Debit Notes](#7-finding-6-credit-notes--debit-notes)
8. [Data Summary Tables](#8-data-summary-tables)
9. [Decisions Required](#9-decisions-required)

---

## 1. Executive Summary

We parsed all 4 Tally XML exports (167 brands, 22,537 SKUs, 1,275 ledgers, 92,106 inventory line items across 10,283 vouchers) and ran 10 analysis areas. Three findings require team decisions before we can proceed with the data pipeline.

**The three critical findings:**

| # | Finding | Impact | Decision Needed |
|---|---------|--------|-----------------|
| 1 | Opening + Inward - Outward != Closing for 95% of active items | Cannot reconstruct daily stock positions using the forward formula | Choose reconstruction approach |
| 2 | Physical Stock vouchers have a hidden field (BATCHPHYSDIFF) we're not extracting | Missing stock adjustment data | Update TDL extraction request |
| 3 | "Sales-Tally" voucher type includes 42% online (MAGENTO2) and 8% internal (Art Lounge India) | Voucher type alone cannot classify channels | Confirm party-based classification rules |

**What's clean and working as expected:**
- All 715 voucher parties exist in the ledger master (no orphans)
- Direction logic (inward/outward) is perfectly consistent per voucher type -- no mixed directions
- All items have categories assigned
- Date coverage is complete (11 business-day gaps, mostly holidays)
- Units are almost entirely "PCS" (22,455 of 22,537)

---

## 2. Finding 1: Stock Balance Reconstruction is Broken

### The Problem

The spec assumes we can reconstruct daily stock positions using:
```
closing_balance = opening_balance + sum(inward) - sum(outward)
```

**This formula fails for 94.8% of items that have both an opening balance and transactions.**

| Test Group | Count | Matches | Mismatches |
|-----------|-------|---------|------------|
| Items with opening balance + transactions | 7,178 | 370 (5.2%) | 6,808 (94.8%) |
| Items with zero opening + transactions | 8,077 | 5,530 (68.5%) | 2,547 (31.5%) |
| All items (including dead SKUs) | 22,537 | 15,214 (67.5%) | 7,323 (32.5%) |

### Root Cause: SKU Renames in Tally

Items are renamed in Tally during the financial year. When a SKU is renamed:
- The **old name** retains its opening balance but gets no new transactions
- The **new name** starts with zero opening balance but receives all transactions
- Tally internally knows they're the same item, but our XML export treats them as separate items

**Worked Example -- "Toned Grey" Paper:**

```
OLD NAME: "ART ESSENTIALS TONED GREY 120 G/M2 50.8X63.5"
  Category:        FAVINI S.R.L (old supplier name)
  Opening balance: 55,640
  Transactions:    1 (Physical Stock with qty=0)
  Computed closing: 55,640
  ACTUAL closing:  0          <-- Tally moved this stock to the new name
  Discrepancy:     +55,640

NEW NAME: "AE TONED GREY50.8 CM X 63.5 CM25 SHEET"
  Category:        ART ESSENTIALS (new brand name)
  Opening balance: 0
  Outward:         1,150 (sales)
  Computed closing: -1,150
  ACTUAL closing:  -1,150     <-- Matches because there's no old opening to account for
```

Note: The rename also changed the category from "FAVINI S.R.L" to "ART ESSENTIALS", making fuzzy matching harder.

**Another Worked Example -- Koh-i-noor Eraser:**

```
ITEM: "Koh-i-noor Soft Eraser In Pencil - FSC 100%"
  Opening:   0
  Inward:    8,747 (purchases)
  Outward:   15,363 (sales)
  Computed:  -6,616
  ACTUAL:    -3,510
  Diff:      -3,106

This item has a -3,510 closing balance. It was sold 15,363 units but only
received 8,747 purchases. The 3,106-unit gap represents stock that existed
under a different name at FY start and was renamed TO this item.
```

### Scale of the Problem

| Metric | Count |
|--------|-------|
| Items with opening > 0, closing = 0 (likely renamed FROM) | 1,746 |
| Items with opening = 0, closing < 0 (likely renamed TO) | 2,429 |
| Items with negative closing balance overall | 5,574 (25% of all items!) |
| Top 15 most negative items | Range: -774 to -5,032 units |

**Most-affected brands by magnitude:**

| Brand | Sum of Discrepancy | Items Affected | Total Items |
|-------|-------------------|----------------|-------------|
| FAVINI S.R.L | 169,143 | 8 of 10 | Supplier renamed to ART ESSENTIALS |
| WINSOR & NEWTON | 48,513 | 1,441 of 2,257 | Name abbreviation changes |
| LANA | 44,851 | 90 of 289 | Product descriptions changed |
| KOH-I-NOOR | 43,342 | 649 of 1,944 | Widespread renames |
| SNOWMAN | 26,030 | 86 of 137 | Majority affected |
| ART ESSENTIALS | 23,984 | 200 of 289 | Received items from FAVINI |

### Three Options for Daily Stock Position Reconstruction

#### Option A: Work Backwards from Closing Balance (Recommended)

**How it works:** Use Tally's closing balance (which IS correct -- Tally handles renames internally) as the anchor point. Replay transactions backwards to reconstruct historical positions.

```
For each day, working backwards from today:
  stock[day] = stock[day+1] + outward_on_day - inward_on_day
```

**Worked Example -- "WN OMV 75ML LIQUIN V1" (Winsor & Newton Liquin):**

```
Tally's closing balance: -1,479  (oversold due to rename, but Tally says this is correct)

Working backwards from closing:
  2026-02-27:  -1,479  (closing)
  2026-02-24:  -1,469  (before 10 units sold)
  2026-02-21:  -1,467  (before 2 units sold, after 18 and 132 to Art Lounge)
  ...continuing backwards through 225 transactions...
  2025-04-11:    388   (before 44 units sold)

  IMPLIED opening: 432
  XML opening:     2,322
  Gap:             1,890 (stock that was on the old name at FY start)
```

**Pros:**
- Tally's closing balance is authoritative (accounts for renames)
- No need to understand or match rename pairs
- Works for ALL items, not just "clean" ones
- Negative closing balances are handled naturally (item is truly oversold)

**Cons:**
- Implied opening balance may be negative (means item was oversold even at start)
- We lose visibility into how much stock existed before renames

#### Option B: Only Process Clean Items

**How it works:** Only compute velocity and stockout predictions for items where `opening + inward - outward = closing` (within tolerance).

```
Clean items:    15,214 (67.5%) -- these match perfectly
Active + clean: ~8,000         -- with actual transactions

Skip the 7,323 mismatched items entirely.
```

**Pros:**
- Simple, no special handling needed
- Guaranteed correct for items we DO process

**Cons:**
- Skips 32.5% of items, including many high-volume ones
- Koh-i-noor Eraser (218 transactions, top seller) would be skipped
- Many important SKUs have renames and would be excluded

#### Option C: Forward from Opening, Clamp Negatives to Zero

**How it works:** Use the original formula. When computed stock goes negative, clamp to 0. Accept that positions won't be perfectly accurate for renamed items.

```
stock = opening_balance
for each day:
  stock += inward - outward
  if stock < 0: stock = 0  # clamp
```

**Pros:**
- Simple implementation
- Velocity calculations still work for recent periods (if item was recently restocked)

**Cons:**
- Stock positions will be wrong for renamed items
- "In-stock days" calculation will be inaccurate (shows out-of-stock when item actually had stock under old name)
- Velocity denominators will be too small, inflating velocity estimates

### Recommendation

**Option A (Backward from Closing)** is the most robust. It:
- Handles all 22,537 items
- Uses Tally's authoritative closing balance
- Produces correct velocity calculations
- Doesn't require matching rename pairs

The only behavioral change: items with negative implied opening balance will show as "out of stock" at FY start even if they actually had stock under a different name. This is acceptable because the velocity calculation only needs to know recent in-stock/out-of-stock status, not the full history.

---

## 3. Finding 2: Physical Stock Vouchers Have Hidden Data

### The Problem

There are **9,381 Physical Stock line items** across 6 vouchers (all on June 7-8, 2025). Our parser extracted them all with **qty=0, rate=0, amount=0**. This looked like they were meaningless, but investigation revealed hidden data.

### Root Cause

Physical Stock vouchers in Tally store the **count adjustment** (difference between physical count and book balance) in a nested field called `BATCHPHYSDIFF`, located at:

```
VOUCHER > ALLINVENTORYENTRIES.LIST > BATCHALLOCATIONS.LIST > BATCHPHYSDIFF
```

Our TDL extraction request only fetches:
```xml
<FETCH>AllInventoryEntries.StockItemName</FETCH>
<FETCH>AllInventoryEntries.ActualQty</FETCH>
<FETCH>AllInventoryEntries.Rate</FETCH>
<FETCH>AllInventoryEntries.Amount</FETCH>
```

It does NOT fetch `AllInventoryEntries.BatchAllocations.BatchPhysDiff`. Without this FETCH line, Tally returns the `BATCHALLOCATIONS.LIST` as empty.

### What BATCHPHYSDIFF Contains

We confirmed by live-querying Tally that the field contains actual adjustment values:

```
BATCHPHYSDIFF examples:
  " 1 PCS"    -- surplus of 1 (physical count > books)
  "-20 PCS"   -- shortage of 20 (physical count < books)
  "-395 PCS"  -- major shortage
  " 0 PCS"    -- count matches books exactly
```

**Meaning:** `BATCHPHYSDIFF = physical_count - book_balance`
- Positive = surplus (more stock found than books show)
- Negative = shortage (less stock found than books show)
- Zero = count matches

### Additional Fields Available

| Field | Location | Purpose |
|-------|----------|---------|
| BATCHPHYSDIFF | BatchAllocations.LIST | Count adjustment quantity |
| GODOWNNAME | BatchAllocations.LIST | Warehouse location (e.g., "Main Location", "PPETPL Kala Ghoda") |
| BATCHDIFFVAL | BatchAllocations.LIST | Monetary value of adjustment |

### Fix Required

Add these FETCH lines to the TDL voucher extraction request:
```xml
<FETCH>AllInventoryEntries.BatchAllocations.BatchPhysDiff</FETCH>
<FETCH>AllInventoryEntries.BatchAllocations.GodownName</FETCH>
```

Then update the parser to extract BATCHPHYSDIFF and use it as the adjustment quantity for Physical Stock vouchers.

### Impact on Stock Position Calculation

Physical Stock adjustments are **absolute corrections** to the book balance. They should be modeled as:
- If BATCHPHYSDIFF > 0: inward adjustment (stock increased)
- If BATCHPHYSDIFF < 0: outward adjustment (stock decreased)
- If BATCHPHYSDIFF = 0: no adjustment needed

**Note:** If using Option A (backward reconstruction), Physical Stock adjustments are already reflected in Tally's closing balance. They still need to be processed as transactions for the day-by-day reconstruction to be accurate.

### Impact on Data Re-extraction

After updating the TDL request, we will need to re-extract the vouchers XML from Tally to get the BATCHPHYSDIFF data. The current cached file (`vouchers_full_fy.xml`) does not contain this field.

---

## 4. Finding 3: Sales-Tally is NOT Just Wholesale

### The Problem

The spec assumed "Sales-Tally" was primarily wholesale, with online sales going through "Sales-Flipkart", "Sales-Amazon", etc. In reality, **Sales-Tally is the catch-all voucher type** used for most transactions.

### Sales-Tally Breakdown

| Party | Line Items | % of Sales-Tally | Actual Channel |
|-------|-----------|-------------------|----------------|
| MAGENTO2 | 17,092 | 41.5% | Online (website) |
| Art Lounge India | 3,352 | 8.1% | Internal transfer |
| 615 other parties | 20,740 | 50.4% | Wholesale |

**Sales-Tally is 42% online, 8% internal, and only 50% wholesale.** Classifying all Sales-Tally as wholesale would massively overcount wholesale velocity and undercount online velocity.

### All Voucher Type Breakdowns

**Sales (11,660 line items):**
| Party | Items | Channel |
|-------|-------|---------|
| Art Lounge India | 6,804 (58%) | Internal |
| 72 other parties | 4,856 (42%) | Wholesale |

**Purchase (16,143 line items):**
| Party | Items | Channel |
|-------|-------|---------|
| Art Lounge India - Purchase | 7,830 (49%) | Internal |
| 41 other parties | 8,313 (51%) | Supplier |

**Sales Store (12,961 line items):**
| Party | Items | Channel |
|-------|-------|---------|
| Counter Collection - QR | 5,799 (45%) | Store (walk-in) |
| Counter Collection - CC | 3,284 (25%) | Store (walk-in) |
| Counter Collection - Cash | 3,227 (25%) | Store (walk-in) |
| 56 other named parties | 651 (5%) | Store (named customers) |

**Sales-Flipkart (289 items):** 100% FLIPKART -- online
**Sales-Amazon (5 items):** 100% AMAZON_IN_API -- online
**Sales-ALKG (5 items):** 3 parties (Metalotus, Viji murugan, GWAMBO STUDIOS) -- likely online/wholesale

### Key Insight

**Voucher type alone is insufficient for channel classification.** Every voucher type except Sales-Flipkart and Sales-Amazon has mixed channels. Classification MUST be party-based.

### Internal Transfers are Large

Art Lounge India appears in:
- Sales: 6,804 outward line items
- Sales-Tally: 3,352 outward line items
- Credit Note: 19 inward line items
- Sales Store: 8 outward line items

Art Lounge India - Purchase appears in:
- Purchase: 7,830 inward line items

**Total internal: 18,013 line items (19.6% of all transactions).** These must be excluded from velocity calculations.

---

## 5. Finding 4: Duplicate Line Items Need Rate-Aware Handling

### The Problem

The current database UNIQUE constraint is:
```sql
UNIQUE(txn_date, voucher_number, stock_item_name, quantity, is_inward)
```

This produces 59 "duplicate" groups (71 extra rows). But investigation reveals only **10 are truly identical** -- the other **49 are legitimate line items with different rates/amounts**.

### Why Tally Creates Same-Item-Same-Qty Lines

Tally sometimes splits a single item across multiple rate tiers within one voucher. This happens for:
- **Tax component differences** (e.g., IGST vs CGST+SGST)
- **Batch pricing** (same item at different costs)
- **Rounding splits** (e.g., rate 9.72 vs 9.73)

### Worked Example -- Manuscript Nib Storage Tin

```
Voucher: INV-25-26-5929 (Dec 25, 2025)
Party:   MAGENTO2
Item:    Manuscript Leonardt Nib Storage Tin
All 3 rows: qty=1, inward=False (outward)

  Row 1: rate=20.59, amount=20.59
  Row 2: rate=19.31, amount=19.31
  Row 3: rate=21.07, amount=21.07

These are 3 separate units sold at 3 different rates in the same order.
Dropping "duplicates" would lose 2 of the 3 units from our stock count!
```

### Worked Example -- Lana Colour Pastel Paper (PUMPKIN order)

```
Voucher: INS0365 (Oct 31, 2025)
Party:   PUMPKIN
18 different Lana Colour Pastel Paper items, each appearing TWICE:

  Row 1: qty=5, rate=9.72, amount=48.59
  Row 2: qty=5, rate=9.73, amount=48.64

The 1-paisa rate difference is a tax split. Each row represents 5 real units.
Total for each item should be 10 units, not 5.
```

### The 10 True Duplicates

These are rows where ALL fields (party, rate, amount, master_id) are identical:

| Voucher | Item | Qty | Count |
|---------|------|-----|-------|
| vnum=634, Feb 16, 2026 | FINETEC Pearlescent Patina | 2 | 6 (5 dupes) |
| vnum=635, Feb 6, 2026 | FINETEC Premium Pink Orange | 1 | 4 (3 dupes) |
| vnum=451, Dec 8, 2025 | Camel Acrylics Naphthol Red | 3 | 4 (3 dupes) |
| vnum=451, Dec 8, 2025 | Camel Acrylics Raw Umber | 3 | 4 (3 dupes) |
| vnum=451, Dec 8, 2025 | Camel Acrylics Olive Green | 3 | 3 (2 dupes) |
| 5 more groups | ... | ... | 2 each |

**Total true duplicate rows: ~15** (safe to drop via ON CONFLICT DO NOTHING)

### Recommendation

Change the UNIQUE constraint to include rate:
```sql
UNIQUE(txn_date, voucher_number, stock_item_name, quantity, is_inward, rate)
```

This preserves the 49 legitimate multi-rate rows while still deduplicating the 10 truly identical groups. The ~15 true duplicates can be handled with `ON CONFLICT DO NOTHING` on insert.

**Alternatively**, if rate precision issues cause problems (9.72 vs 9.720001), we could:
1. Add a `line_number` field from the XML (position within the voucher) -- but Tally doesn't provide this
2. Remove the UNIQUE constraint entirely and deduplicate by `tally_master_id` at the voucher level (only insert if we haven't already seen that voucher) -- this is simpler and may be better

---

## 6. Finding 5: Channel Classification Ruleset

### Proposed 5-Priority Ruleset

This ruleset classifies **100% of the 715 parties** (0 unclassified):

```
PRIORITY 1 -- Voucher Type Auto-Classification:
  Sales-Flipkart    -> online
  Sales-Amazon      -> online
  Sales-ALKG        -> online
  Sales Store       -> store
  Physical Stock    -> ignore (balance adjustment, no velocity)

PRIORITY 2 -- Party Name Exact Match:
  MAGENTO2                    -> online
  AMAZON_IN_API               -> online
  FLIPKART                    -> online
  Art Lounge India            -> internal
  Art Lounge India - Purchase -> internal

PRIORITY 3 -- Party Name Pattern Match:
  *Counter Collection*        -> store

PRIORITY 4 -- Ledger Parent + Voucher Type:
  Sundry Creditors (Purchase/Debit Note) -> supplier
  Sundry Debtors (Sales-Tally/Sales/Credit Note) -> wholesale

PRIORITY 5 -- Fallback:
  Everything else             -> unclassified (flag for manual review)
```

### Classification Result

| Channel | Parties | Line Items | % of Total |
|---------|---------|------------|------------|
| wholesale | 624 | 26,520 | 28.8% |
| internal | 2 | 18,005 | 19.5% |
| online | 3 | 17,391 | 18.9% |
| store | 52 | 12,961 | 14.1% |
| ignore | 0* | 9,381 | 10.2% |
| supplier | 34 | 7,837 | 8.5% |
| unclassified | 0 | 11 | 0.0% |

*Physical Stock has no named party -- classified by voucher type

### Velocity & Balance Rules

| Channel | Affects Balance? | Affects Velocity? | Rationale |
|---------|-----------------|-------------------|-----------|
| wholesale | Yes (outward) | Yes | Real demand signal |
| online | Yes (outward) | Yes | Real demand signal |
| store | Yes (outward) | Yes | Real demand signal |
| supplier | Yes (inward) | No | Purchases, not demand |
| internal | Yes (both ways) | No | Inter-company transfers |
| ignore | Yes (adjustment) | No | Physical stock corrections |
| Credit Note | Yes (inward) | No | Returns, not demand |
| Debit Note | Yes (outward) | No | Supplier adjustments, not demand |

### Edge Cases to Note

1. **AMAZON_IN_API appears in Sales-Tally** (1 line item, not just Sales-Amazon). The exact-match rule (Priority 2) catches this.

2. **109 parties appear in multiple voucher types** (e.g., New Bombay Stationery Stores has Purchase, Sales Store, Credit Note, Sales-Tally, Sales). Classification is at the party level, so the channel is consistent regardless of voucher type.

3. **11 Sales-Tally line items have empty party names.** These will fall to "unclassified" and should be reviewed manually.

4. **Sales-ALKG** has only 5 line items across 3 parties. It appears to be a minor sales channel. Classified as "online" but could also be "wholesale" -- low impact either way.

---

## 7. Finding 6: Credit Notes & Debit Notes

### Credit Notes (476 line items, 77 vouchers, 54 parties)

- **Direction:** ALL inward (100%). These represent goods returned by customers.
- **Effect on balance:** Increase stock (returned goods come back to warehouse).
- **Effect on velocity:** EXCLUDED. Returns are one-off events, not demand signals.

**Top Credit Note parties (likely problematic customers or order cancellations):**

| Party | Line Items | Channel |
|-------|-----------|---------|
| Opel Marketing Agencies | 115 | Wholesale |
| FLINOX ENTERPRISES LLP | 39 | Wholesale |
| Nanumals Booktique | 32 | Wholesale |
| Ajanta Universal Fabrics | 31 | Wholesale |
| Rietu | 29 | Wholesale |
| Art Lounge India | 19 | Internal |
| ART SHARK LLP | 17 | Wholesale |

### Debit Notes (2 line items, 2 vouchers, 2 parties)

- **Direction:** ALL outward (100%). These represent returns TO suppliers.
- **Negligible volume** -- only 2 line items in the entire FY.

---

## 8. Data Summary Tables

### Overall Data Shape

| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| Stock categories (brands) | 168 | 167 | Minor (-1) |
| Stock items (SKUs) | 22,538 | 22,537 | Minor (-1) |
| Ledgers | 1,276 | 1,275 | Minor (-1) |
| Voucher line items | ~92,000 | 92,106 | Match |
| Items with category | All | 22,537 (100%) | Clean |
| Items in vouchers not in master | 0 | 0 | Clean |
| Parties in vouchers not in ledgers | 0 | 0 | Clean |
| Distinct units | Mostly PCS | 22,455 PCS + 82 N/A | Clean |
| Direction logic consistency | Consistent | 100% consistent | Clean |

### Stock Position Summary

| Closing Balance | Count | % |
|----------------|-------|---|
| Positive (in stock) | 6,498 | 28.8% |
| Zero (out of stock) | 10,465 | 46.4% |
| Negative (oversold/rename artifact) | 5,574 | 24.7% |
| **Total** | **22,537** | **100%** |

### Transaction Volume by Month

| Month | Line Items | Vouchers | Notes |
|-------|-----------|----------|-------|
| 2025-04 | 4,034 | 156 | Partial month (starts Apr 10) |
| 2025-05 | 7,661 | 233 | |
| 2025-06 | 13,039 | 237 | Includes 9,381 Physical Stock items |
| 2025-07 | 7,154 | 673 | Voucher count jumps (smaller orders?) |
| 2025-08 | 10,109 | 1,463 | |
| 2025-09 | 9,048 | 1,253 | |
| 2025-10 | 7,487 | 1,233 | |
| 2025-11 | 8,261 | 1,196 | |
| 2025-12 | 10,081 | 1,327 | |
| 2026-01 | 7,632 | 1,316 | |
| 2026-02 | 7,564 | 1,192 | |
| 2026-03 | 36 | 4 | Partial (data extracted today) |

**Excluding Physical Stock (June):** Monthly volume is fairly stable at 7,000--10,000 line items.
**No seasonal pattern visible** in this first year of data.
**11 business days with no transactions:** May 1 (holiday), June 6/11/12 (near Physical Stock), Aug 9 (Sat), Sep 6 (Sat), Mar 2/3/6/9/10 (recent/no data yet).

### Voucher Types with Inventory

| Voucher Type | Line Items | Direction | Top Use |
|-------------|-----------|-----------|---------|
| Sales-Tally | 41,184 | Outward | 42% online, 50% wholesale, 8% internal |
| Purchase | 16,143 | Inward | 49% internal, 51% supplier |
| Sales Store | 12,961 | Outward | Walk-in retail (Counter Collection) |
| Sales | 11,660 | Outward | 58% internal, 42% wholesale |
| Physical Stock | 9,381 | Inward* | Stock count verification (*qty=0 in current extract) |
| Credit Note | 476 | Inward | Customer returns |
| Sales-Flipkart | 289 | Outward | 100% FLIPKART |
| Sales-ALKG | 5 | Outward | 3 parties, minor channel |
| Sales-Amazon | 5 | Outward | 100% AMAZON_IN_API |
| Debit Note | 2 | Outward | Supplier returns |

### Voucher Types WITHOUT Inventory (not in our data)

These exist in Tally but have no ALLINVENTORYENTRIES -- correctly excluded:
- Journal (3,096 vouchers), Receipt (2,106), Payment (1,024), Sales-Freight (701), Contra (48)

---

## 9. Decisions Required

### Decision 1: Stock Position Reconstruction Approach

| Option | Description | Coverage | Accuracy | Complexity |
|--------|-------------|----------|----------|------------|
| **A (Recommended)** | Work backwards from Tally's closing balance | 100% of items | High -- uses authoritative closing balance | Medium |
| B | Only process items where formula matches | ~67% of items | Perfect for processed items | Low |
| C | Forward from opening, clamp negatives | 100% of items | Poor for renamed items | Low |

**Recommendation:** Option A. It covers all items and uses Tally's ground truth.

### Decision 2: Physical Stock Data Re-extraction

We need to add `BATCHPHYSDIFF` to the TDL request and re-extract vouchers from Tally. This will:
- Require Tally to be running on the EC2 server
- Take ~2 minutes for the full FY extraction
- Give us the actual stock count adjustments (currently missing)

**Question for team:** Is this a blocker, or can we proceed with the pipeline and re-extract later? The 6 Physical Stock vouchers (June 7-8, 2025) likely only affect a few hundred items. If using Option A (backward reconstruction), the adjustments are already reflected in Tally's closing balance.

### Decision 3: Channel Classification Rules

The proposed ruleset (Section 6) classifies 100% of parties with 0 unclassified. Please review:

1. **Is Sales-ALKG online or wholesale?** (Only 5 line items, low impact)
2. **Are all Sundry Debtor parties really wholesale?** Some look like individual consumers (e.g., "Dr. Pannaga", "Pragati Agrawal") -- should these be "store" instead?
3. **Should internal transfers affect balance at all?** Currently they do (Art Lounge India buys from itself). If the "Purchase" and "Sales" sides always cancel out, we could skip both.

### Decision 4: Dedup Strategy

| Option | Description | Rows Affected |
|--------|-------------|---------------|
| **A** | Add `rate` to UNIQUE key | Preserves 49 multi-rate groups, deduplicates 10 truly identical |
| B | Deduplicate at voucher level (by tally_master_id) | Only insert each voucher once, skip if already seen |
| C | Remove UNIQUE constraint, rely on sync logic | No constraint, upsert by some other key |

**Recommendation:** Option A (add rate to UNIQUE key) is simplest. The 10 truly identical duplicates will be handled by `ON CONFLICT DO NOTHING`.

---

## Appendix: Files Generated

| File | Description |
|------|-------------|
| `src/data/analysis_report.txt` | Full 28,000-line analysis output |
| `src/data/rename_investigation_output.txt` | SKU rename patterns and backward reconstruction examples |
| `src/data/dedup_channels_report.txt` | Dedup groups and channel classification detail |
| `src/data/analyze_tally_data.py` | Main analysis script |
| `src/data/investigate_renames.py` | Rename investigation script |
| `src/data/investigate_dedup_channels.py` | Dedup and channel investigation script |
