# Art Lounge — Stock Reorder Intelligence System

## Project Summary

Art Lounge (operated by Platinum Painting Essentials & Trading Pvt. Ltd.) is an importer and retailer of art supplies. The company imports products from international brands (Speedball, Winsor & Newton, Arteza, etc.) in bulk shipments every 3-6 months, sells wholesale to retailers across India, and also sells retail through one physical store (Kala Ghoda, Mumbai) and an online store (Magento 2 / artlounge.in).

The core business problem: when you import 250 units and sell through both wholesale and online channels, you lose visibility into when you'll actually run out of stock for wholesale customers. Online sales (1-2 units/day) create noise that makes stock movement reports misleading. By the time you realize you need to reorder, it's too late — the next shipment is months away.

This system pulls inventory transaction data from Tally Prime nightly, separates wholesale from online demand, computes per-SKU velocity and days-to-stockout, and presents a dashboard that tells you exactly which SKUs need reordering and when. It also generates purchase orders.

## Business Context

### The Company Structure

- **Legal entity:** Platinum Painting Essentials & Trading Pvt. Ltd. (PPETPL)
- **Warehouse:** Gala No 112-114, Building No 40, Arihant Commercial Complex, Purna, Bhiwandi
- **Retail store:** PPETPL Kala Ghoda (Mumbai)
- **Online store:** artlounge.in (Magento 2)
- **Tally instance:** Running on AWS Windows EC2 (35.154.1.129), Tally Prime 7.0 Gold

### The Import Cycle Problem

1. Company places order with international brand (e.g., Speedball Art Products LLC)
2. Shipment arrives months later (3-6 months depending on brand, shipping method)
3. Entire shipment goes to warehouse (Main Location in Tally)
4. Wholesale customers order in batches (10-60 units at a time, irregular timing)
5. Online store sells 1-2 units at a time (steady, daily)
6. Retail store transfers small quantities from warehouse
7. Stock runs out — but because online sales trickle in steadily, the movement reports look "active" even when wholesale stock has been depleted for months
8. By the time someone notices, it's too late to order — next shipment is months away

### The Data Problem (illustrated with real example)

**Speedball Monalisa Gold Leaf Sealer Waterbased 2 Oz:**

| Period | What happened | Stock level |
|--------|--------------|-------------|
| Apr 1, 2025 | Opening balance | 45 units |
| Apr-May | Wholesale sales + import arrival (+41) | Fluctuating, reached 67 |
| Jun 8 | Physical stock adjustment — zeroed out | 0 units |
| Jun-Nov | **171 days at zero or negative** — but sales kept being booked (backorders, internal shuffles) | Negative (-47 at worst) |
| Nov 26 | New import shipment arrives (+250) | 143 (after immediate wholesale sale) |
| Nov-Feb | Normal selling resumes | Declining toward 18 |
| Feb 24 | Current state | **18 units, ~7 days of stock left** |

During the 171-day out-of-stock period, the system recorded 36 wholesale units and 6 online units sold — all against negative inventory. This makes it impossible to read stock movement reports and know "when did we actually run out?"

### Channels and How They Appear in Tally

| Channel | Party Name Examples | Voucher Types | Voucher Prefixes |
|---------|-------------------|---------------|-----------------|
| **Supplier (import)** | Speedball Art Products LLC | Purchase | Numeric only |
| **Wholesale** | Hindustan Trading Company, A N Commtrade LLP, Mango Stationery Pvt. Ltd, Saremisons, Artorium the Colour World, Himalaya Stationary Mart, Vardhman Trading Company, Ansh, Shruti G. Dev, Monica kharkar | Sales, Sales-Tally | PWSL-xxx, INV-xxx |
| **Online (e-commerce)** | MAGENTO2 | Sales-Tally | INV-xxx |
| **Store transfer** | Art Lounge India | Sales | KWSL-xxx |
| **Store POS** | Counter Collection - QR | Sales Store | INS-xxx |
| **Internal (retail→warehouse)** | Art Lounge India - Purchase | Purchase | Numeric only |
| **Adjustment** | Physical Stock | Physical Stock | Numeric only |

**Critical note:** MAGENTO2 and wholesale both use voucher type "Sales-Tally" with "INV-" prefixed voucher numbers. You CANNOT distinguish them by voucher type alone. Party name is the only reliable signal.

### Tally Setup Details

- **Godowns:** Two godowns exist ("Main Location" and "PPETPL Kala Ghoda") but ALL transactions are booked against Main Location. Godown data is not useful for channel separation.
- **Stock Categories:** Used to represent brands (Speedball, Winsor & Newton, etc.)
- **Stock Groups:** Sub-classification within brands (product types)
- **Scale:** Estimated 5,000-15,000 SKUs across all brands, potentially hundreds of thousands of transactions per financial year

## System Architecture

```
AWS Windows box (already exists, no cost change)
├── Tally Prime (port 9000, localhost only — never exposed to internet)
└── Sync Agent (Python, Windows Task Scheduler, nightly 2 AM)
    ├── Reads from Tally at localhost:9000
    ├── Parses XML, computes velocities, stockout predictions, reorder flags
    └── Writes results to Railway Postgres over SSL ──► HTTPS

Railway ($5-10/month, fully managed)
├── PostgreSQL database (managed, auto-backups, SSL)
├── FastAPI service (serves API + static React build)
│   ├── /api/* → data endpoints
│   └── /* → React dashboard
└── Custom domain: wholesaleorders.artlounge.in (SSL automatic)

You → Chrome → wholesaleorders.artlounge.in → dashboard

Development Environment (your local machine):
├── Local Tally Prime  ← Copy of production database
│   HTTP Server :9000  ← For testing XML requests
├── Local PostgreSQL   ← For dev/testing
├── Python backend     ← FastAPI on port 8000
└── React dev server   ← On port 3000
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Source system | Tally Prime 7.0 | Accounting & inventory data |
| Data extraction | Python + requests library | XML HTTP requests to Tally |
| Database | PostgreSQL (Railway managed) | Persistent storage, computed views |
| Backend API | FastAPI (Python, hosted on Railway) | Serves dashboard data, PO generation |
| Frontend | React + Tailwind CSS (served by FastAPI) | Browser-based dashboard |
| Hosting | Railway | Managed Postgres + web service, auto-deploy from Git |
| Scheduling | Windows Task Scheduler | Nightly sync on AWS box |
| PO export | openpyxl (Python) | Excel file generation for purchase orders |

## Document Index

| Document | Purpose |
|----------|---------|
| `00-PROJECT-OVERVIEW.md` | This file — business context, architecture, tech stack |
| `01-LOCAL-DEV-SETUP.md` | Setting up local Tally + dev environment |
| `02-TALLY-XML-EXTRACTION.md` | XML requests, response parsing, data extraction scripts |
| `03-DATABASE-SCHEMA.md` | PostgreSQL schema, tables, indexes, computed views |
| `04-PARTY-CLASSIFICATION.md` | How to classify parties, the mapping table, rules |
| `05-COMPUTATION-ENGINE.md` | Velocity calculation, stockout prediction, reorder logic |
| `06-NIGHTLY-SYNC.md` | The automated sync job — scheduling, delta detection, error handling |
| `07-DASHBOARD-SPEC.md` | All three dashboard views — wireframes, data requirements, interactions |
| `08-PO-BUILDER-SPEC.md` | Purchase order generation logic and export format |
| `09-DEPLOYMENT.md` | Production deployment on Railway — setup, custom domain, sync agent |
| `10-REFERENCE-DATA.md` | Sample transaction data from Speedball Sealer SKU for testing |
