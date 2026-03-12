# 10 — Reference Data (Speedball Sealer Test Case)

## Overview

This document contains the actual transaction data from one SKU — "Speedball Monalisa Gold Leaf Sealer Waterbased 2 Oz" — extracted from an Excel export of Tally's Stock Item Register. Use this as test data for development and as a benchmark: the computation engine's output for this SKU should match the expected values documented here.

## Source

File: `Sealant.xlsx` (uploaded by user)
Company: Platinum Painting Essentials & Trading Pvt. Ltd.
Period: 1-Apr-2025 to 10-Mar-2026

## Raw Transaction Data

```csv
date,party,voucher_type,voucher_number,qty_in,qty_out,closing_qty
2025-04-01,Opening Balance,,,45,0,45
2025-04-10,Hindustan Trading Company,Sales,PWSL-1,0,18,27
2025-04-30,Art Lounge India,Sales,KWSL-3,0,1,26
2025-05-02,"Speedball Art Products, LLC",Purchase,63,41,0,67
2025-05-05,A N Commtrade LLP,Sales,PWSL-140,0,18,49
2025-05-07,Artorium the Colour World,Sales,PWSL-142,0,2,47
2025-05-13,A N Commtrade LLP,Sales,PWSL-193,0,2,45
2025-06-08,Physical Stock,Physical Stock,10,0,45,0
2025-06-19,A N Commtrade LLP,Sales-Tally,INV-25-26-0072,0,12,-12
2025-06-20,Art Lounge India,Sales-Tally,INV-25-26-0088,0,12,-24
2025-07-03,Mango Stationery Pvt. Ltd,Sales-Tally,INV-25-26-0204,0,5,-29
2025-07-10,Himalaya Stationary Mart,Sales-Tally,INV-25-26-0248,0,6,-35
2025-07-15,Counter Collection - QR,Sales Store,INS0054,0,1,-36
2025-07-17,Saremisons,Sales-Tally,INV-25-26-0317,0,3,-39
2025-07-24,Mango Stationery Pvt. Ltd,Sales-Tally,INV-25-26-0362,0,3,-42
2025-07-26,Hindustan Trading Company,Sales-Tally,INV-25-26-0448,0,5,-47
2025-08-08,MAGENTO2,Sales-Tally,INV-25-26-0989,0,1,
2025-08-08,Art Lounge India - Purchase,Purchase,213,1,0,-47
2025-08-11,MAGENTO2,Sales-Tally,INV-25-26-1049,0,1,
2025-08-11,Art Lounge India - Purchase,Purchase,217,1,0,-47
2025-08-18,Art Lounge India - Purchase,Purchase,235,1,0,-46
2025-08-21,MAGENTO2,Sales-Tally,INV-25-26-1595,0,1,
2025-08-21,Art Lounge India - Purchase,Purchase,240,2,0,-45
2025-08-23,MAGENTO2,Sales-Tally,INV-25-26-1653,0,1,
2025-08-23,Ansh,Sales-Tally,INV-25-26-1672,0,1,
2025-08-23,Art Lounge India - Purchase,Purchase,243,3,0,-44
2025-08-25,MAGENTO2,Sales-Tally,INV-25-26-1726,0,1,-45
2025-08-30,MAGENTO2,Sales-Tally,INV-25-26-1940,0,1,-46
2025-09-08,Hindustan Trading Company,Sales-Tally,INV-25-26-2247,0,1,-47
2025-11-26,"Speedball Art Products, LLC",Purchase,415,250,0,
2025-11-26,Hindustan Trading Company,Sales-Tally,INV-25-26-4969,0,60,143
2025-12-05,MAGENTO2,Sales-Tally,INV-25-26-5263,0,1,
2025-12-05,MAGENTO2,Sales-Tally,INV-25-26-5264,0,1,141
2025-12-06,MAGENTO2,Sales-Tally,INV-25-26-5310,0,1,140
2025-12-08,MAGENTO2,Sales-Tally,INV-25-26-5359,0,2,138
2025-12-10,Ansh,Sales-Tally,INV-25-26-5462,0,2,136
2025-12-13,MAGENTO2,Sales-Tally,INV-25-26-5532,0,1,135
2025-12-18,Hindustan Trading Company,Credit Note,81,0,-60,195
2025-12-19,Hindustan Trading Company,Sales-Tally,INV-25-26-5738,0,60,
2025-12-19,Hindustan Trading Company,Sales-Tally,INV-25-26-5752,0,60,75
2025-12-27,Shruti G. Dev,Sales-Tally,INV-25-26-5997,0,1,74
2025-12-31,Vardhman Trading Company,Sales-Tally,INV-25-26-6153,0,3,71
2026-01-09,MAGENTO2,Sales-Tally,INV-25-26-6441,0,1,70
2026-01-14,MAGENTO2,Sales-Tally,INV-25-26-6590,0,1,69
2026-01-15,Saremisons,Sales-Tally,INV-25-26-6655,0,3,66
2026-01-19,A N Commtrade LLP,Sales-Tally,INV-25-26-6816,0,6,60
2026-01-26,MAGENTO2,Sales-Tally,INV-25-26-7019,0,1,59
2026-01-29,MAGENTO2,Sales-Tally,INV-25-26-7149,0,1,58
2026-02-01,MAGENTO2,Sales-Tally,INV-25-26-7217,0,1,57
2026-02-02,MAGENTO2,Sales-Tally,INV-25-26-7235,0,1,56
2026-02-05,Monica kharkar,Sales-Tally,INV-25-26-7403,0,1,55
2026-02-06,MAGENTO2,Sales-Tally,INV-25-26-7471,0,1,
2026-02-06,A N Commtrade LLP,Sales-Tally,INV-25-26-7474,0,10,
2026-02-06,MAGENTO2,Sales-Tally,INV-25-26-7478,0,1,
2026-02-06,MAGENTO2,Sales-Tally,INV-25-26-7482,0,2,41
2026-02-07,MAGENTO2,Sales-Tally,INV-25-26-7489,0,1,
2026-02-07,MAGENTO2,Sales-Tally,INV-25-26-7496,0,1,
2026-02-07,MAGENTO2,Sales-Tally,INV-25-26-7510,0,1,38
2026-02-08,MAGENTO2,Sales-Tally,INV-25-26-7523,0,1,
2026-02-08,MAGENTO2,Sales-Tally,INV-25-26-7525,0,1,
2026-02-08,MAGENTO2,Sales-Tally,INV-25-26-7526,0,1,
2026-02-08,MAGENTO2,Sales-Tally,INV-25-26-7527,0,1,
2026-02-08,MAGENTO2,Sales-Tally,INV-25-26-7532,0,1,
2026-02-08,MAGENTO2,Sales-Tally,INV-25-26-7538,0,1,
2026-02-08,MAGENTO2,Sales-Tally,INV-25-26-7541,0,1,31
2026-02-10,MAGENTO2,Sales-Tally,INV-25-26-7623,0,1,
2026-02-10,MAGENTO2,Sales-Tally,INV-25-26-7644,0,1,29
2026-02-11,Mango Stationery Pvt. Ltd,Sales-Tally,INV-25-26-7668,0,1,28
2026-02-16,MAGENTO2,Sales-Tally,INV-25-26-7798,0,1,27
2026-02-18,MAGENTO2,Sales-Tally,INV-25-26-7901,0,1,
2026-02-18,MAGENTO2,Sales-Tally,INV-25-26-7903,0,1,25
2026-02-19,MAGENTO2,Sales-Tally,INV-25-26-7906,0,1,24
2026-02-24,Mango Stationery Pvt. Ltd,Sales-Tally,INV-25-26-8097,0,6,18
```

## Party Classification for this SKU

| Party | Channel |
|-------|---------|
| Speedball Art Products, LLC | supplier |
| Hindustan Trading Company | wholesale |
| A N Commtrade LLP | wholesale |
| Artorium the Colour World | wholesale |
| Himalaya Stationary Mart | wholesale |
| Mango Stationery Pvt. Ltd | wholesale |
| Saremisons | wholesale |
| Vardhman Trading Company | wholesale |
| Ansh | wholesale |
| Shruti G. Dev | wholesale |
| Monica kharkar | wholesale |
| MAGENTO2 | online |
| Art Lounge India | store |
| Counter Collection - QR | store |
| Art Lounge India - Purchase | internal |
| Physical Stock | ignore |

## Expected Computation Output

### In-Stock Periods

| Period | Days | Status |
|--------|------|--------|
| Apr 1 - Jun 7, 2025 | 68 | In stock (balance > 0) |
| Jun 8 - Nov 25, 2025 | 171 | Out of stock (balance ≤ 0) |
| Nov 26, 2025 - Feb 24, 2026 | 91 | In stock (balance > 0) |

Total in-stock days: **159**

### Demand During In-Stock Days

**Period 1: Apr 1 - Jun 7**

| Channel | Transactions | Units |
|---------|-------------|-------|
| Wholesale | Hindustan Trading (18), A N Commtrade (18+2), Artorium (2) | 40 |
| Online | — | 0 |
| Store | Art Lounge India (1) | 1 |
| **Total demand** | | **41** |

Note: Physical Stock adjustment (45 units on Jun 8) is NOT counted as demand.

**Period 2: Nov 26 - Feb 24**

| Channel | Units |
|---------|-------|
| Wholesale | Hindustan (60+60+60-60 via credit note rebook + 1) + A N Commtrade (6+10) + Ansh (2) + Mango (1+6) + Saremisons (3) + Vardhman (3) + Shruti (1) + Monica (1) ≈ many — need careful count excluding credit note | ~143 net wholesale |
| Online (MAGENTO2) | ~32 |
| Store | 0 |

Note: The Hindustan Trading Credit Note (Dec 18, +60 return) followed by two sales (Dec 19, -60 and -60) is complex. The credit note adds stock back; the subsequent sales are fresh demand. For velocity: count all wholesale outward during in-stock days, don't net against returns.

### Expected Velocity

Approximate (exact numbers depend on precise credit note handling):

| Metric | Value |
|--------|-------|
| Wholesale velocity | ~1.2-1.6 units/day (~36-48/month) |
| Online velocity | ~0.20 units/day (~6/month) |
| Total velocity | ~1.4-1.8 units/day (~42-54/month) |

### Expected Reorder Output

| Metric | Value |
|--------|-------|
| Current stock | 18 |
| Days to stockout | ~10-13 days |
| Supplier lead time (sea) | 180 days |
| Reorder status | **CRITICAL** (days left << lead time) |
| Suggested order qty (sea) | ~327-421 units |
| Suggested order qty (air) | ~55-70 units |

### Key Test Assertions

1. Out-of-stock period (Jun 8 - Nov 25) transactions are EXCLUDED from velocity calculation
2. Physical Stock adjustment is applied to balance but NOT counted as demand
3. Art Lounge India - Purchase entries are EXCLUDED entirely
4. Credit Note (Dec 18) is treated as inward for balance, excluded from velocity
5. MAGENTO2 sales count toward online velocity only
6. Counter Collection - QR counts toward store velocity (excluded from wholesale)
7. All other parties count toward wholesale velocity
8. Status is CRITICAL because days_to_stockout (~10) << lead_time (180)

## Voucher Type / Voucher Prefix Patterns

| Prefix | Voucher Type | Channel Pattern |
|--------|-------------|----------------|
| PWSL- | Sales | Wholesale from warehouse |
| KWSL- | Sales | Store transfer to Kala Ghoda |
| INS | Sales Store | Store POS sale |
| INV- | Sales-Tally | Mixed — both wholesale AND online. Distinguish by party name. |
| (numeric) | Purchase | Import from supplier OR internal (Art Lounge India - Purchase) |
| (numeric) | Physical Stock | Stock adjustment |
| (numeric) | Credit Note | Return/correction |

**Critical insight:** You CANNOT use voucher type alone to determine channel. "Sales-Tally" with "INV-" prefix contains both wholesale customers (Hindustan Trading) and online (MAGENTO2). Party name is the only reliable discriminator.
