# Stock Position & Velocity Verification Report

**Generated:** 2026-03-18
**Data source:** Tally Prime (Platinum Painting Essentials & Trading Pvt. Ltd.)
**FY period:** 1-Apr-2025 to 17-Mar-2026 (351 days)
**Brand:** JACQUARD (10 sample SKUs)

---

## How Velocity Is Calculated

Velocity measures how fast an item sells *when it is available*. It drives
reorder decisions -- a higher velocity means we need to reorder sooner and in
larger quantities.

### The Formula

```
Velocity (units/day) = Total Demand / In-Stock Days
Velocity (units/month) = Velocity (units/day) x 30
```

Where:

- **Total Demand** = units sold through wholesale + online + store channels.
  Excludes: Physical Stock adjustments, internal transfers, credit/debit notes.

- **In-Stock Days** = number of days the item had stock > 0 (i.e., was available
  to sell). Days where stock was zero or negative are excluded because the item
  *couldn't* sell -- including those days would make velocity artificially low.

### Why In-Stock Days Matter

Consider an item that sold 3 units this year:

| Scenario | In-Stock Days | Velocity |
|----------|--------------|----------|
| Was in stock all year (351 days) | 351 | 3/351 = **0.26/month** (slow mover) |
| Was in stock only 10 days | 10 | 3/10 = **9.0/month** (fast mover!) |
| Bug: only sale days counted | 3 | 3/3 = **30/month** (wildly wrong) |

The same 3 sales give completely different velocities depending on how many
in-stock days we count. Getting this number right is critical.

### How We Reconstruct Daily Stock Levels

We start from Tally's **opening balance** (1-Apr) and walk forward through every
transaction, updating the running stock level:

```
Starting stock = Tally Opening Balance

For each day in the FY:
  For each transaction on that day:
    If it's a sale (wholesale/online/store):  stock -= quantity
    If it's a purchase (supplier/internal):   stock += quantity
    If it's a Physical Stock adjustment:
      If BATCHPHYSDIFF is available:          stock += adjustment
      Otherwise:                              stock = physical count (SET-TO)

  If stock > 0 at end of day -> count as in-stock day
  If a sale happened that day  -> also count as in-stock day
```

The final stock at the end should equal Tally's **closing balance**. If it does,
we know every intermediate day's stock level is correct too.

### What About Physical Stock Vouchers?

Physical Stock vouchers record a physical count. In Tally's data:

- **ACTUALQTY** = the number of units physically found on the shelf
- **BATCHPHYSDIFF** = the adjustment Tally computed (physical count minus book balance)

Example: Book says 29 units. Physical count finds 24. BATCHPHYSDIFF = -5.

Our previous system was treating ACTUALQTY (24) as stock being *added*,
recording +24 instead of -5. The proposed fix uses BATCHPHYSDIFF when available.

---

## The Two Bugs

### Bug 1: Physical Stock Misinterpretation

| | Old (broken) | New (proposed) |
|---|---|---|
| What we read | ACTUALQTY (physical count) | BATCHPHYSDIFF (adjustment) |
| How we use it | Add to stock (+24) | Adjust stock (-5) |
| Effect | Stock inflated, appears in-stock longer | Correct stock levels |
| Velocity impact | **Understated** (sales spread over too many days) | Accurate |

### Bug 2: Internal Purchases Ignored

| | Old (broken) | New (proposed) |
|---|---|---|
| Purchases from "Art Lounge India - Purchase" | Completely skipped | Included in stock |
| Effect | Item shows out-of-stock even when it has inventory | Correct stock levels |
| Velocity impact | **Massively overstated** (sales / few days) | Accurate |

---

## SKU-by-SKU Calculation Walkthrough

---

### F-JAC1830 -- JACQUARD DNF 2.25 OZ #830 WHITE2.25 OZ

**Step 1: Starting Point**

- Tally Opening Balance (1-Apr-2025): **111 units**
- Tally Closing Balance (17-Mar-2026): **19 units**

**Step 2: Walk Through Every Transaction**

Starting from the opening balance, apply each transaction to get the running stock:

| # | Date | Transaction | Change | Stock After | Demand? |
|---|------|-------------|--------|------------|---------|
| | 01-Apr-25 | Opening Balance | | **111** | |
| 1 | 21-Apr-25 | -12 (Sales to Shankhesh Sales and Marketing) [wholesale] | | **99** | Yes |
| 2 | 28-Apr-25 | -3 (Sales to Mendwell Agencies) [wholesale] | | **96** | Yes |
| 3 | 30-Apr-25 | -12 (Sales to Art Lounge India) [online] | | **82** | Yes |
| 4 | 30-Apr-25 | -2 (Sales to Art Lounge India) [online] | | **82** | Yes |
| 5 | 12-May-25 | -6 (Sales to Shankhesh Sales and Marketing) [wholesale] | | **76** | Yes |
| 6 | 23-May-25 | -3 (Sales to Art Lounge India) [online] | | **73** | Yes |
| 7 | 27-May-25 | -12 (Sales to Hindustan Trading Company) [wholesale] | | **61** | Yes |
| 8 | 31-May-25 | -1 (Sales to Art Lounge India) [online] | | **60** | Yes |
| 9 | 08-Jun-25 | SET TO 0 (Phys Stock #8: counted 0, no diff data) | | **0** |  |
| 10 | 09-Jun-25 | +63 (Phys Stock #14: counted 63, adjusted +63) | | **63** |  |
| 11 | 10-Jun-25 | +2 (Phys Stock #28: counted 65, adjusted +2) | | **65** |  |
| 12 | 14-Jun-25 | -3 (Sales-Tally to Art Lounge India) [online] | | **56** | Yes |
| 13 | 14-Jun-25 | -6 (Sales-Tally to Mendwell Agencies) [wholesale] | | **56** | Yes |
| 14 | 26-Jun-25 | -18 (Sales-Tally to Mendwell Agencies) [wholesale] | | **38** | Yes |
| 15 | 01-Jul-25 | -2 (Sales-Tally to Vardhman Trading Company) [wholesale] | | **36** | Yes |
| 16 | 02-Jul-25 | -3 (Sales-Tally to Art Lounge India) [online] | | **30** | Yes |
| 17 | 02-Jul-25 | -3 (Sales-Tally to Art Lounge India) [online] | | **30** | Yes |
| 18 | 16-Jul-25 | -1 (Sales-Tally to Art Lounge India) [online] | | **29** | Yes |
| 19 | 29-Jul-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **28** | Yes |
| 20 | 13-Aug-25 | -1 (Sales-Tally to Ayushi gaur) [wholesale] | | **27** | Yes |
| 21 | 20-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **26** | Yes |
| 22 | 26-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **25** | Yes |
| 23 | 27-Sep-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **24** | Yes |
| 24 | 04-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **23** | Yes |
| 25 | 30-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **22** | Yes |
| 26 | 15-Nov-25 | +1 (Purchase from Art Lounge India - Purchase) [internal] | | **23** |  |
| 27 | 24-Nov-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **21** | Yes |
| 28 | 24-Nov-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **21** | Yes |
| 29 | 09-Feb-26 | -1 (Sales-Tally to MAGENTO2) [online] | | **20** | Yes |
| 30 | 24-Feb-26 | -1 (Sales-Tally to MAGENTO2) [online] | | **19** | Yes |

**Closing check:** Reconstructed = **19**, Tally says **19** --> MATCH

**Step 3: Count Total Demand**

Only count outward sales through demand channels (wholesale, online, store).
Exclude: Physical Stock adjustments, internal transfers, credit/debit notes.

- Wholesale: 60 + Online: 38 = **98 units total demand**

**Step 4: Count In-Stock Days**

A day counts as 'in-stock' if stock > 0 at end of day, or if a sale occurred that day.

In-stock periods:

- 01-Apr-2025 to 07-Jun-2025 = **68 days**
- 09-Jun-2025 to 17-Mar-2026 = **282 days**

Item went out of stock on **08-Jun-2025**.

**Total in-stock days = 350**

**Step 5: Calculate Velocity**

```
Velocity = Total Demand / In-Stock Days
         = 98 / 350
         = 0.2800 units/day
         = 0.2800 x 30
         = 8.4 units/month
```

**Step 6: Compare With Current System**

| | In-Stock Days | Calculation | Velocity/month |
|---|---|---|---|
| Current System | 351 | 98 / 351 x 30 | **8.4** |
| Proposed Fix | 350 | 98 / 350 x 30 | **8.4** |

**Verdict: Similar.** This item was in stock most of the year, so both methods
give approximately the same velocity.


---

### F-JAC1715 -- JACQUARD GRN LABEL 60ML #715 MAGENTA

**Step 1: Starting Point**

- Tally Opening Balance (1-Apr-2025): **41 units**
- Tally Closing Balance (17-Mar-2026): **0 units**

**Step 2: Walk Through Every Transaction**

Starting from the opening balance, apply each transaction to get the running stock:

| # | Date | Transaction | Change | Stock After | Demand? |
|---|------|-------------|--------|------------|---------|
| | 01-Apr-25 | Opening Balance | | **41** | |
| 1 | 18-Apr-25 | -6 (Sales to Art Lounge India) [online] | | **35** | Yes |
| 2 | 21-Apr-25 | -6 (Sales to Shankhesh Sales and Marketing) [wholesale] | | **29** | Yes |
| 3 | 28-Apr-25 | -2 (Sales to Mendwell Agencies) [wholesale] | | **27** | Yes |
| 4 | 27-May-25 | -12 (Sales to Hindustan Trading Company) [wholesale] | | **15** | Yes |
| 5 | 08-Jun-25 | SET TO 0 (Phys Stock #8: counted 0, no diff data) | | **0** |  |
| 6 | 09-Jun-25 | +15 (Phys Stock #14: counted 15, adjusted +15) | | **15** |  |
| 7 | 09-Jun-25 | -11 (Phys Stock #15: counted 4, adjusted -11) | | **15** |  |
| 8 | 09-Jun-25 | +11 (Phys Stock #16: counted 15, adjusted +11) | | **15** |  |
| 9 | 26-Jun-25 | -4 (Sales-Tally to Art Lounge India) [online] | | **11** | Yes |
| 10 | 14-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **10** | Yes |
| 11 | 20-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **9** | Yes |
| 12 | 22-Aug-25 | -1 (Sales-Tally to Minni) [wholesale] | | **8** | Yes |
| 13 | 26-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **7** | Yes |
| 14 | 01-Sep-25 | -3 (Phys Stock #36: counted 4, adjusted -3) | | **4** |  |
| 15 | 03-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **3** | Yes |
| 16 | 04-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **2** | Yes |
| 17 | 27-Oct-25 | -1 (Sales-Tally to P. Ramesh) [wholesale] | | **1** | Yes |
| 18 | 11-Nov-25 | -3 (Sales-Tally to Anjali International) [wholesale] | | **-2** | Yes |
| 19 | 14-Nov-25 | -1 (Sales Store to Counter Collection - Cash) [store] | | **-3** | Yes |
| 20 | 15-Nov-25 | +1 (Purchase from Art Lounge India - Purchase) [internal] | | **-2** |  |
| 21 | 29-Nov-25 | -2 (Sales-Tally to sweta Priyadarshan) [wholesale] | | **-4** | Yes |
| 22 | 05-Dec-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **-5** | Yes |
| 23 | 29-Dec-25 | -1 (Sales-Tally to sweta Priyadarshan) [wholesale] | | **-6** | Yes |
| 24 | 22-Jan-26 | -1 (Sales Store to Counter Collection - Cash) [store] | | **-7** | Yes |
| 25 | 10-Mar-26 | +7 (Phys Stock #37: counted 2, adjusted +7) | | **0** |  |

**Closing check:** Reconstructed = **0**, Tally says **0** --> MATCH

**Step 3: Count Total Demand**

Only count outward sales through demand channels (wholesale, online, store).
Exclude: Physical Stock adjustments, internal transfers, credit/debit notes.

- Wholesale: 28 + Online: 16 + Store: 2 = **46 units total demand**

**Step 4: Count In-Stock Days**

A day counts as 'in-stock' if stock > 0 at end of day, or if a sale occurred that day.

In-stock periods:

- 01-Apr-2025 to 07-Jun-2025 = **68 days**
- 09-Jun-2025 to 11-Nov-2025 = **156 days**
- 14-Nov-2025 to 14-Nov-2025 = **1 days**
- 29-Nov-2025 to 29-Nov-2025 = **1 days**
- 05-Dec-2025 to 05-Dec-2025 = **1 days**
- 29-Dec-2025 to 29-Dec-2025 = **1 days**
- 22-Jan-2026 to 22-Jan-2026 = **1 days**

Item went out of stock on **08-Jun-2025**.

**Total in-stock days = 229**

**Step 5: Calculate Velocity**

```
Velocity = Total Demand / In-Stock Days
         = 46 / 229
         = 0.2009 units/day
         = 0.2009 x 30
         = 6.0 units/month
```

**Step 6: Compare With Current System**

| | In-Stock Days | Calculation | Velocity/month |
|---|---|---|---|
| Current System | 351 | 46 / 351 x 30 | **3.9** |
| Proposed Fix | 229 | 46 / 229 x 30 | **6.0** |

**Verdict: Current velocity is understated (3.9 vs 6.0).**

The current system counts 351 in-stock days, but the item actually had
stock for only 229 days. The extra 122 days dilute velocity
because the same 46 sales are spread over more days.


---

### F-JAC1818 -- JACQUARD DNF 2.25 OZ #818 CHARTREUSE2.25 OZ

**Step 1: Starting Point**

- Tally Opening Balance (1-Apr-2025): **34 units**
- Tally Closing Balance (17-Mar-2026): **0 units**

**Step 2: Walk Through Every Transaction**

Starting from the opening balance, apply each transaction to get the running stock:

| # | Date | Transaction | Change | Stock After | Demand? |
|---|------|-------------|--------|------------|---------|
| | 01-Apr-25 | Opening Balance | | **34** | |
| 1 | 18-Apr-25 | -3 (Sales to Mendwell Agencies) [wholesale] | | **31** | Yes |
| 2 | 08-May-25 | -3 (Sales to Art Lounge India) [online] | | **28** | Yes |
| 3 | 12-May-25 | -6 (Sales to Shankhesh Sales and Marketing) [wholesale] | | **22** | Yes |
| 4 | 15-May-25 | -4 (Sales to Art Lounge India) [online] | | **18** | Yes |
| 5 | 27-May-25 | -3 (Sales to Hindustan Trading Company) [wholesale] | | **13** | Yes |
| 6 | 27-May-25 | -2 (Sales to Art Lounge India) [online] | | **13** | Yes |
| 7 | 05-Jun-25 | -2 (Sales to Art Lounge India) [online] | | **11** | Yes |
| 8 | 08-Jun-25 | SET TO 0 (Phys Stock #8: counted 0, no diff data) | | **0** |  |
| 9 | 09-Jun-25 | +13 (Phys Stock #14: counted 13, adjusted +13) | | **11** |  |
| 10 | 09-Jun-25 | SET TO 0 (Phys Stock #15: counted 0, no diff data) | | **11** |  |
| 11 | 09-Jun-25 | +11 (Phys Stock #16: counted 11, adjusted +11) | | **11** |  |
| 12 | 01-Jul-25 | -2 (Sales-Tally to Vardhman Trading Company) [wholesale] | | **9** | Yes |
| 13 | 30-Jul-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **8** | Yes |
| 14 | 08-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **7** | Yes |
| 15 | 19-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **6** | Yes |
| 16 | 22-Aug-25 | -1 (Sales-Tally to Monica) [wholesale] | | **4** | Yes |
| 17 | 22-Aug-25 | -1 (Sales-Tally to Minni) [wholesale] | | **4** | Yes |
| 18 | 26-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **3** | Yes |
| 19 | 27-Sep-25 | -2 (Sales-Tally to MAGENTO2) [online] | | **1** | Yes |
| 20 | 04-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **0** | Yes |
| 21 | 24-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **-1** | Yes |
| 22 | 15-Nov-25 | +2 (Purchase from Art Lounge India - Purchase) [internal] | | **1** |  |
| 23 | 01-Dec-25 | +1 (Credit Note from Monica) [wholesale] | | **2** |  |
| 24 | 05-Dec-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **1** | Yes |
| 25 | 02-Feb-26 | -1 (Sales-Tally to MAGENTO2) [online] | | **0** | Yes |

**Closing check:** Reconstructed = **0**, Tally says **0** --> MATCH

**Step 3: Count Total Demand**

Only count outward sales through demand channels (wholesale, online, store).
Exclude: Physical Stock adjustments, internal transfers, credit/debit notes.

- Wholesale: 16 + Online: 21 = **37 units total demand**

**Step 4: Count In-Stock Days**

A day counts as 'in-stock' if stock > 0 at end of day, or if a sale occurred that day.

In-stock periods:

- 01-Apr-2025 to 07-Jun-2025 = **68 days**
- 09-Jun-2025 to 04-Oct-2025 = **118 days**
- 24-Oct-2025 to 24-Oct-2025 = **1 days**
- 15-Nov-2025 to 02-Feb-2026 = **80 days**

Item went out of stock on **08-Jun-2025**.

**Total in-stock days = 267**

**Step 5: Calculate Velocity**

```
Velocity = Total Demand / In-Stock Days
         = 37 / 267
         = 0.1386 units/day
         = 0.1386 x 30
         = 4.2 units/month
```

**Step 6: Compare With Current System**

| | In-Stock Days | Calculation | Velocity/month |
|---|---|---|---|
| Current System | 351 | 37 / 351 x 30 | **3.1** |
| Proposed Fix | 267 | 37 / 267 x 30 | **4.2** |

**Verdict: Current velocity is understated (3.1 vs 4.2).**

The current system counts 351 in-stock days, but the item actually had
stock for only 267 days. The extra 84 days dilute velocity
because the same 37 sales are spread over more days.


---

### F-JAC1714 -- JACQUARD GRN LABEL 60ML #714 CARMINE RED

**Step 1: Starting Point**

- Tally Opening Balance (1-Apr-2025): **42 units**
- Tally Closing Balance (17-Mar-2026): **15 units**

**Step 2: Walk Through Every Transaction**

Starting from the opening balance, apply each transaction to get the running stock:

| # | Date | Transaction | Change | Stock After | Demand? |
|---|------|-------------|--------|------------|---------|
| | 01-Apr-25 | Opening Balance | | **42** | |
| 1 | 28-Apr-25 | -2 (Sales to Mendwell Agencies) [wholesale] | | **40** | Yes |
| 2 | 27-May-25 | -6 (Sales to Hindustan Trading Company) [wholesale] | | **34** | Yes |
| 3 | 08-Jun-25 | SET TO 0 (Phys Stock #8: counted 0, no diff data) | | **0** |  |
| 4 | 09-Jun-25 | +34 (Phys Stock #14: counted 34, adjusted +34) | | **15** |  |
| 5 | 09-Jun-25 | -19 (Phys Stock #15: counted 15, adjusted -19) | | **15** |  |
| 6 | 10-Jun-25 | +16 (Phys Stock #28: counted 31, adjusted +16) | | **31** |  |
| 7 | 10-Jun-25 | +0 (Phys Stock #29: counted 50, adjusted +0) | | **31** |  |
| 8 | 27-Jun-25 | -2 (Sales-Tally to Art Lounge India) [online] | | **29** | Yes |
| 9 | 14-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **28** | Yes |
| 10 | 20-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **27** | Yes |
| 11 | 22-Aug-25 | -1 (Sales-Tally to Minni) [wholesale] | | **26** | Yes |
| 12 | 26-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **25** | Yes |
| 13 | 02-Sep-25 | -3 (Sales-Tally to Mendwell Agencies) [wholesale] | | **22** | Yes |
| 14 | 03-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **21** | Yes |
| 15 | 24-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **20** | Yes |
| 16 | 25-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **19** | Yes |
| 17 | 08-Nov-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **18** | Yes |
| 18 | 11-Nov-25 | -3 (Sales-Tally to Anjali International) [wholesale] | | **15** | Yes |
| 19 | 14-Nov-25 | -1 (Sales Store to Counter Collection - Cash) [store] | | **14** | Yes |
| 20 | 15-Nov-25 | +6 (Purchase from Art Lounge India - Purchase) [internal] | | **20** |  |
| 21 | 29-Nov-25 | -1 (Sales-Tally to sweta Priyadarshan) [wholesale] | | **19** | Yes |
| 22 | 29-Dec-25 | -1 (Sales-Tally to sweta Priyadarshan) [wholesale] | | **18** | Yes |
| 23 | 03-Feb-26 | -2 (Sales-Tally to sweta Priyadarshan) [wholesale] | | **16** | Yes |
| 24 | 11-Feb-26 | -1 (Sales-Tally to Savita Hanagi) [wholesale] | | **15** | Yes |

**Closing check:** Reconstructed = **15**, Tally says **15** --> MATCH

**Step 3: Count Total Demand**

Only count outward sales through demand channels (wholesale, online, store).
Exclude: Physical Stock adjustments, internal transfers, credit/debit notes.

- Wholesale: 20 + Online: 9 + Store: 1 = **30 units total demand**

**Step 4: Count In-Stock Days**

A day counts as 'in-stock' if stock > 0 at end of day, or if a sale occurred that day.

In-stock periods:

- 01-Apr-2025 to 07-Jun-2025 = **68 days**
- 09-Jun-2025 to 17-Mar-2026 = **282 days**

Item went out of stock on **08-Jun-2025**.

**Total in-stock days = 350**

**Step 5: Calculate Velocity**

```
Velocity = Total Demand / In-Stock Days
         = 30 / 350
         = 0.0857 units/day
         = 0.0857 x 30
         = 2.6 units/month
```

**Step 6: Compare With Current System**

| | In-Stock Days | Calculation | Velocity/month |
|---|---|---|---|
| Current System | 351 | 30 / 351 x 30 | **2.6** |
| Proposed Fix | 350 | 30 / 350 x 30 | **2.6** |

**Verdict: Similar.** This item was in stock most of the year, so both methods
give approximately the same velocity.


---

### F-VDW0001 -- JACQUARD DORLANDSWAXMEDIUM4OZ

**Step 1: Starting Point**

- Tally Opening Balance (1-Apr-2025): **30 units**
- Tally Closing Balance (17-Mar-2026): **0 units**

**Step 2: Walk Through Every Transaction**

Starting from the opening balance, apply each transaction to get the running stock:

| # | Date | Transaction | Change | Stock After | Demand? |
|---|------|-------------|--------|------------|---------|
| | 01-Apr-25 | Opening Balance | | **30** | |
| 1 | 18-Apr-25 | -9 (Sales to Art Lounge India) [online] | | **21** | Yes |
| 2 | 28-Apr-25 | -2 (Sales to Mendwell Agencies) [wholesale] | | **19** | Yes |
| 3 | 08-May-25 | -3 (Sales to Art Lounge India) [online] | | **16** | Yes |
| 4 | 31-May-25 | -1 (Sales to Art Lounge India) [online] | | **15** | Yes |
| 5 | 08-Jun-25 | SET TO 0 (Phys Stock #8: counted 0, no diff data) | | **0** |  |
| 6 | 09-Jun-25 | +16 (Phys Stock #14: counted 16, adjusted +16) | | **16** |  |
| 7 | 09-Jun-25 | -13 (Phys Stock #15: counted 3, adjusted -13) | | **16** |  |
| 8 | 09-Jun-25 | +13 (Phys Stock #16: counted 16, adjusted +13) | | **16** |  |
| 9 | 16-Jul-25 | -3 (Sales-Tally to Art Lounge India) [online] | | **13** | Yes |
| 10 | 26-Jul-25 | -1 (Sales Store to Counter Collection - Cash) [store] | | **12** | Yes |
| 11 | 12-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **11** | Yes |
| 12 | 14-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **10** | Yes |
| 13 | 16-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **9** | Yes |
| 14 | 18-Aug-25 | -2 (Sales-Tally to Shankhesh Sales and Marketing) [wholesale] | | **7** | Yes |
| 15 | 20-Aug-25 | -1 (Sales Store to Counter Collection - QR) [store] | | **6** | Yes |
| 16 | 21-Aug-25 | -2 (Sales-Tally to Vardhman Trading Company) [wholesale] | | **4** | Yes |
| 17 | 25-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **3** | Yes |
| 18 | 30-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **2** | Yes |
| 19 | 01-Sep-25 | -1 (Phys Stock #36: counted 3, adjusted -1) | | **1** |  |
| 20 | 25-Sep-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **0** | Yes |
| 21 | 07-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **-1** | Yes |
| 22 | 15-Oct-25 | -3 (Sales-Tally to Art Lounge India) [online] | | **-4** | Yes |
| 23 | 10-Mar-26 | +4 (Phys Stock #37: counted 2, adjusted +4) | | **0** |  |

**Closing check:** Reconstructed = **0**, Tally says **0** --> MATCH

**Step 3: Count Total Demand**

Only count outward sales through demand channels (wholesale, online, store).
Exclude: Physical Stock adjustments, internal transfers, credit/debit notes.

- Wholesale: 6 + Online: 26 + Store: 2 = **34 units total demand**

**Step 4: Count In-Stock Days**

A day counts as 'in-stock' if stock > 0 at end of day, or if a sale occurred that day.

In-stock periods:

- 01-Apr-2025 to 07-Jun-2025 = **68 days**
- 09-Jun-2025 to 25-Sep-2025 = **109 days**
- 07-Oct-2025 to 07-Oct-2025 = **1 days**
- 15-Oct-2025 to 15-Oct-2025 = **1 days**

Item went out of stock on **08-Jun-2025**.

**Total in-stock days = 179**

**Step 5: Calculate Velocity**

```
Velocity = Total Demand / In-Stock Days
         = 34 / 179
         = 0.1899 units/day
         = 0.1899 x 30
         = 5.7 units/month
```

**Step 6: Compare With Current System**

| | In-Stock Days | Calculation | Velocity/month |
|---|---|---|---|
| Current System | 351 | 34 / 351 x 30 | **2.9** |
| Proposed Fix | 179 | 34 / 179 x 30 | **5.7** |

**Verdict: Current velocity is understated (2.9 vs 5.7).**

The current system counts 351 in-stock days, but the item actually had
stock for only 179 days. The extra 172 days dilute velocity
because the same 34 sales are spread over more days.


---

### F-JAC1824 -- JACQUARD DNF 2.25 OZ #824 OCHRE2.25 OZ

**Step 1: Starting Point**

- Tally Opening Balance (1-Apr-2025): **28 units**
- Tally Closing Balance (17-Mar-2026): **0 units**

**Step 2: Walk Through Every Transaction**

Starting from the opening balance, apply each transaction to get the running stock:

| # | Date | Transaction | Change | Stock After | Demand? |
|---|------|-------------|--------|------------|---------|
| | 01-Apr-25 | Opening Balance | | **28** | |
| 1 | 28-Apr-25 | -3 (Sales to Mendwell Agencies) [wholesale] | | **25** | Yes |
| 2 | 12-May-25 | -6 (Sales to Shankhesh Sales and Marketing) [wholesale] | | **19** | Yes |
| 3 | 17-May-25 | -3 (Sales to Art Lounge India) [online] | | **13** | Yes |
| 4 | 17-May-25 | -3 (Sales to Art Lounge India) [online] | | **13** | Yes |
| 5 | 27-May-25 | -6 (Sales to Hindustan Trading Company) [wholesale] | | **7** | Yes |
| 6 | 08-Jun-25 | SET TO 0 (Phys Stock #8: counted 0, no diff data) | | **0** |  |
| 7 | 09-Jun-25 | +7 (Phys Stock #14: counted 7, adjusted +7) | | **7** |  |
| 8 | 09-Jun-25 | -5 (Phys Stock #15: counted 2, adjusted -5) | | **7** |  |
| 9 | 09-Jun-25 | +5 (Phys Stock #16: counted 7, adjusted +5) | | **7** |  |
| 10 | 26-Jun-25 | -6 (Sales-Tally to Mendwell Agencies) [wholesale] | | **1** | Yes |
| 11 | 19-Jul-25 | -1 (Sales-Tally to Art Lounge India) [online] | | **0** | Yes |
| 12 | 30-Jul-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **-1** | Yes |
| 13 | 31-Jul-25 | -1 (Sales Store to Counter Collection - Cash) [store] | | **-2** | Yes |
| 14 | 01-Sep-25 | +3 (Phys Stock #36: counted 2, adjusted +3) | | **1** |  |
| 15 | 10-Mar-26 | -1 (Phys Stock #37: counted 1, adjusted -1) | | **0** |  |

**Closing check:** Reconstructed = **0**, Tally says **0** --> MATCH

**Step 3: Count Total Demand**

Only count outward sales through demand channels (wholesale, online, store).
Exclude: Physical Stock adjustments, internal transfers, credit/debit notes.

- Wholesale: 21 + Online: 8 + Store: 1 = **30 units total demand**

**Step 4: Count In-Stock Days**

A day counts as 'in-stock' if stock > 0 at end of day, or if a sale occurred that day.

In-stock periods:

- 01-Apr-2025 to 07-Jun-2025 = **68 days**
- 09-Jun-2025 to 19-Jul-2025 = **41 days**
- 30-Jul-2025 to 31-Jul-2025 = **2 days**
- 01-Sep-2025 to 09-Mar-2026 = **190 days**

Item went out of stock on **08-Jun-2025**.

**Total in-stock days = 301**

**Step 5: Calculate Velocity**

```
Velocity = Total Demand / In-Stock Days
         = 30 / 301
         = 0.0997 units/day
         = 0.0997 x 30
         = 3.0 units/month
```

**Step 6: Compare With Current System**

| | In-Stock Days | Calculation | Velocity/month |
|---|---|---|---|
| Current System | 351 | 30 / 351 x 30 | **2.6** |
| Proposed Fix | 301 | 30 / 301 x 30 | **3.0** |

**Verdict: Similar.** This item was in stock most of the year, so both methods
give approximately the same velocity.


---

### F-JPX1673 -- JACQUARD PEARL EX .5 OZ #673 INTER VIOLET

**Step 1: Starting Point**

- Tally Opening Balance (1-Apr-2025): **1 units**
- Tally Closing Balance (17-Mar-2026): **0 units**

**Step 2: Walk Through Every Transaction**

Starting from the opening balance, apply each transaction to get the running stock:

| # | Date | Transaction | Change | Stock After | Demand? |
|---|------|-------------|--------|------------|---------|
| | 01-Apr-25 | Opening Balance | | **1** | |
| 1 | 08-Jun-25 | SET TO 0 (Phys Stock #8: counted 0, no diff data) | | **0** |  |
| 2 | 09-Jun-25 | +1 (Phys Stock #14: counted 1, adjusted +1) | | **1** |  |
| 3 | 09-Jun-25 | +1 (Phys Stock #15: counted 2, adjusted +1) | | **1** |  |
| 4 | 09-Jun-25 | -1 (Phys Stock #16: counted 1, adjusted -1) | | **1** |  |
| 5 | 11-Jul-25 | -1 (Sales Store to Counter Collection - QR) [store] | | **0** | Yes |
| 6 | 01-Sep-25 | +1 (Phys Stock #36: counted 2, adjusted +1) | | **1** |  |
| 7 | 03-Dec-25 | -1 (Sales-Tally to Art Lounge India) [online] | | **0** | Yes |
| 8 | 30-Dec-25 | -1 (Sales Store to Counter Collection - CC) [store] | | **-1** | Yes |
| 9 | 10-Mar-26 | +1 (Phys Stock #37: counted 2, adjusted +1) | | **0** |  |

**Closing check:** Reconstructed = **0**, Tally says **0** --> MATCH

**Step 3: Count Total Demand**

Only count outward sales through demand channels (wholesale, online, store).
Exclude: Physical Stock adjustments, internal transfers, credit/debit notes.

- Online: 1 + Store: 2 = **3 units total demand**

**Step 4: Count In-Stock Days**

A day counts as 'in-stock' if stock > 0 at end of day, or if a sale occurred that day.

In-stock periods:

- 01-Apr-2025 to 07-Jun-2025 = **68 days**
- 09-Jun-2025 to 11-Jul-2025 = **33 days**
- 01-Sep-2025 to 03-Dec-2025 = **94 days**
- 30-Dec-2025 to 30-Dec-2025 = **1 days**

Item went out of stock on **08-Jun-2025**.

**Total in-stock days = 196**

**Step 5: Calculate Velocity**

```
Velocity = Total Demand / In-Stock Days
         = 3 / 196
         = 0.0153 units/day
         = 0.0153 x 30
         = 0.5 units/month
```

**Step 6: Compare With Current System**

| | In-Stock Days | Calculation | Velocity/month |
|---|---|---|---|
| Current System | 351 | 3 / 351 x 30 | **0.3** |
| Proposed Fix | 196 | 3 / 196 x 30 | **0.5** |

**Verdict: Current velocity is understated (0.3 vs 0.5).**

The current system counts 351 in-stock days, but the item actually had
stock for only 196 days. The extra 155 days dilute velocity
because the same 3 sales are spread over more days.


---

### F-JFC1009 -- JACQUARD PINATA 4 OZ #009 CHILI PEPPER14.79 ML

**Step 1: Starting Point**

- Tally Opening Balance (1-Apr-2025): **0 units**
- Tally Closing Balance (17-Mar-2026): **0 units**

**Step 2: Walk Through Every Transaction**

Starting from the opening balance, apply each transaction to get the running stock:

| # | Date | Transaction | Change | Stock After | Demand? |
|---|------|-------------|--------|------------|---------|
| | 01-Apr-25 | Opening Balance | | **0** | |
| 1 | 19-Aug-25 | -1 (Sales Store to Counter Collection - QR) [store] | | **-1** | Yes |
| 2 | 15-Nov-25 | +7 (Purchase from Art Lounge India - Purchase) [internal] | | **6** |  |
| 3 | 08-Dec-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **5** | Yes |
| 4 | 31-Jan-26 | -1 (Sales Store to VASTU CULTURE) [store] | | **4** | Yes |
| 5 | 24-Feb-26 | -4 (Sales-Tally to MAGENTO2) [online] | | **0** | Yes |

**Closing check:** Reconstructed = **0**, Tally says **0** --> MATCH

**Step 3: Count Total Demand**

Only count outward sales through demand channels (wholesale, online, store).
Exclude: Physical Stock adjustments, internal transfers, credit/debit notes.

- Online: 5 + Store: 2 = **7 units total demand**

**Step 4: Count In-Stock Days**

A day counts as 'in-stock' if stock > 0 at end of day, or if a sale occurred that day.

In-stock periods:

- 19-Aug-2025 to 19-Aug-2025 = **1 days**
- 15-Nov-2025 to 24-Feb-2026 = **102 days**

**Total in-stock days = 103**

**Step 5: Calculate Velocity**

```
Velocity = Total Demand / In-Stock Days
         = 7 / 103
         = 0.0680 units/day
         = 0.0680 x 30
         = 2.0 units/month
```

**Step 6: Compare With Current System**

| | In-Stock Days | Calculation | Velocity/month |
|---|---|---|---|
| Current System | 4 | 7 / 4 x 30 | **52.5** |
| Proposed Fix | 103 | 7 / 103 x 30 | **2.0** |

**Verdict: Current velocity is 26x too high.**

The current system only counts 4 in-stock days because internal
purchases (which added stock) were ignored. The item actually had stock
for 103 days. With the correct in-stock days, velocity drops
from 52.5 to 2.0 units/month.


---

### F-JAC1812 -- JACQUARD DNF 2.25 OZ #812 PERIWINKLE2.25 OZ

**Step 1: Starting Point**

- Tally Opening Balance (1-Apr-2025): **0 units**
- Tally Closing Balance (17-Mar-2026): **2 units**

**Step 2: Walk Through Every Transaction**

Starting from the opening balance, apply each transaction to get the running stock:

| # | Date | Transaction | Change | Stock After | Demand? |
|---|------|-------------|--------|------------|---------|
| | 01-Apr-25 | Opening Balance | | **0** | |
| 1 | 26-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **-1** | Yes |
| 2 | 01-Oct-25 | +2 (Purchase from Art Lounge India - Purchase) [internal] | | **1** |  |
| 3 | 04-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **0** | Yes |
| 4 | 24-Oct-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **-1** | Yes |
| 5 | 15-Nov-25 | +3 (Purchase from Art Lounge India - Purchase) [internal] | | **2** |  |

**Closing check:** Reconstructed = **2**, Tally says **2** --> MATCH

**Step 3: Count Total Demand**

Only count outward sales through demand channels (wholesale, online, store).
Exclude: Physical Stock adjustments, internal transfers, credit/debit notes.

- Online: 3 = **3 units total demand**

**Step 4: Count In-Stock Days**

A day counts as 'in-stock' if stock > 0 at end of day, or if a sale occurred that day.

In-stock periods:

- 26-Aug-2025 to 26-Aug-2025 = **1 days**
- 01-Oct-2025 to 04-Oct-2025 = **4 days**
- 24-Oct-2025 to 24-Oct-2025 = **1 days**
- 15-Nov-2025 to 17-Mar-2026 = **123 days**

**Total in-stock days = 129**

**Step 5: Calculate Velocity**

```
Velocity = Total Demand / In-Stock Days
         = 3 / 129
         = 0.0233 units/day
         = 0.0233 x 30
         = 0.7 units/month
```

**Step 6: Compare With Current System**

| | In-Stock Days | Calculation | Velocity/month |
|---|---|---|---|
| Current System | 3 | 3 / 3 x 30 | **30.0** |
| Proposed Fix | 129 | 3 / 129 x 30 | **0.7** |

**Verdict: Current velocity is 43x too high.**

The current system only counts 3 in-stock days because internal
purchases (which added stock) were ignored. The item actually had stock
for 129 days. With the correct in-stock days, velocity drops
from 30.0 to 0.7 units/month.


---

### F-JAC1547 -- JACQUARD LUMIERE2.25OZ 547INDIGO

**Step 1: Starting Point**

- Tally Opening Balance (1-Apr-2025): **0 units**
- Tally Closing Balance (17-Mar-2026): **0 units**

**Step 2: Walk Through Every Transaction**

Starting from the opening balance, apply each transaction to get the running stock:

| # | Date | Transaction | Change | Stock After | Demand? |
|---|------|-------------|--------|------------|---------|
| | 01-Apr-25 | Opening Balance | | **0** | |
| 1 | 22-Aug-25 | +1 (Purchase from Art Lounge India - Purchase) [internal] | | **1** |  |
| 2 | 30-Aug-25 | -1 (Sales-Tally to MAGENTO2) [online] | | **0** | Yes |
| 3 | 30-Sep-25 | -1 (Sales Store to VEERA FASHION LLP) [store] | | **-1** | Yes |
| 4 | 15-Nov-25 | +1 (Purchase from Art Lounge India - Purchase) [internal] | | **0** |  |

**Closing check:** Reconstructed = **0**, Tally says **0** --> MATCH

**Step 3: Count Total Demand**

Only count outward sales through demand channels (wholesale, online, store).
Exclude: Physical Stock adjustments, internal transfers, credit/debit notes.

- Online: 1 + Store: 1 = **2 units total demand**

**Step 4: Count In-Stock Days**

A day counts as 'in-stock' if stock > 0 at end of day, or if a sale occurred that day.

In-stock periods:

- 22-Aug-2025 to 30-Aug-2025 = **9 days**
- 30-Sep-2025 to 30-Sep-2025 = **1 days**

**Total in-stock days = 10**

**Step 5: Calculate Velocity**

```
Velocity = Total Demand / In-Stock Days
         = 2 / 10
         = 0.2000 units/day
         = 0.2000 x 30
         = 6.0 units/month
```

**Step 6: Compare With Current System**

| | In-Stock Days | Calculation | Velocity/month |
|---|---|---|---|
| Current System | 2 | 2 / 2 x 30 | **30.0** |
| Proposed Fix | 10 | 2 / 10 x 30 | **6.0** |

**Verdict: Current velocity is 5x too high.**

The current system only counts 2 in-stock days because internal
purchases (which added stock) were ignored. The item actually had stock
for 10 days. With the correct in-stock days, velocity drops
from 30.0 to 6.0 units/month.


---

## Summary

| Part No | Item | Sales | Current Days | Current Vel/mo | Proposed Days | Proposed Vel/mo | Issue |
|---------|------|-------|-------------|---------------|--------------|----------------|-------|
| F-JAC1830 | JACQUARD DNF 2.25 OZ #830 WHITE2.25 | 98 | 351 | 8.4 | 350 | 8.4 | OK |
| F-JAC1715 | JACQUARD GRN LABEL 60ML #715 MAGENT | 46 | 351 | 3.9 | 229 | 6.0 | Understated 1.5x |
| F-JAC1818 | JACQUARD DNF 2.25 OZ #818 CHARTREUS | 37 | 351 | 3.1 | 267 | 4.2 | Understated 1.4x |
| F-JAC1714 | JACQUARD GRN LABEL 60ML #714 CARMIN | 30 | 351 | 2.6 | 350 | 2.6 | OK |
| F-VDW0001 | JACQUARD DORLANDSWAXMEDIUM4OZ | 34 | 351 | 2.9 | 179 | 5.7 | Understated 2.0x |
| F-JAC1824 | JACQUARD DNF 2.25 OZ #824 OCHRE2.25 | 30 | 351 | 2.6 | 301 | 3.0 | OK |
| F-JPX1673 | JACQUARD PEARL EX .5 OZ #673 INTER  | 3 | 351 | 0.3 | 196 | 0.5 | Understated 1.8x |
| F-JFC1009 | JACQUARD PINATA 4 OZ #009 CHILI PEP | 7 | 4 | 52.5 | 103 | 2.0 | OVERSTATED 26x |
| F-JAC1812 | JACQUARD DNF 2.25 OZ #812 PERIWINKL | 3 | 3 | 30.0 | 129 | 0.7 | OVERSTATED 43x |
| F-JAC1547 | JACQUARD LUMIERE2.25OZ 547INDIGO | 2 | 2 | 30.0 | 10 | 6.0 | OVERSTATED 5x |

---

## Next Steps

1. **Please verify** each SKU's transaction trace against Tally's Stock Item Vouchers report.
2. **Check the closing balance** for each item -- does our reconstructed closing match Tally?
3. **Check the velocity** -- does the proposed velocity feel right given how much the item sells?
4. If everything checks out, we will implement the fix across all brands and re-run the pipeline.
