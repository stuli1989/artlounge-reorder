# Art Lounge Reorder System — Task Index & Tracker

## Project Root
`C:\Users\Kshitij Shah\OneDrive\Documents\Art Lounge\ReOrderingProject`

The source code will be built inside a `src/` subfolder within this project root. All task files, context docs, and project specs live alongside the code.

## How to Use

Each task is self-contained with inline specs. Execute in order — each task lists its prerequisites. Tasks are designed to be completed by an AI coding assistant (Sonnet) in a single session.

**Design System:** shadcn/ui (Radix UI + Tailwind CSS) for the React frontend.

---

## Progress Tracker

| Task | Title | Status | Files Created |
|------|-------|--------|---------------|
| T01 | Project Scaffolding & Config | `DONE` | src/ folder structure, config/settings.py, requirements.txt, .env.example, .gitignore, venv |
| T02 | Tally HTTP Client + XML Requests | `DONE` | extraction/tally_client.py, extraction/xml_requests.py |
| T03 | Test Extraction Script | `DONE` | extraction/test_extraction.py, data/sample_responses/*.xml |
| T04 | Database Schema | `DONE` | db/schema.sql, config/suppliers.json |
| T05 | XML Response Parsers | `DONE` | extraction/xml_parser.py |
| T06 | Master Data Loader | `DONE` | extraction/data_loader.py |
| T07 | Party Classification System | `DONE` | extraction/party_classifier.py |
| T08 | Transaction Data Loader | `DONE` | extraction/transaction_loader.py |
| T09 | Daily Stock Position Reconstruction | `DONE` | engine/stock_position.py |
| T10 | Velocity Calculation | `DONE` | engine/velocity.py |
| T11 | Stockout + Import History + Reorder | `DONE` | engine/reorder.py |
| T12 | Computation Pipeline + Brand Rollup | `DONE` | engine/aggregation.py, engine/pipeline.py |
| T13 | Nightly Sync Script | `DONE` | sync/nightly_sync.py, sync/sync_helpers.py, sync/email_notifier.py |
| T14 | FastAPI Skeleton + DB Connection | `DONE` | api/main.py, api/database.py, Procfile |
| T15 | Brand + SKU API Endpoints | `DONE` | api/routes/brands.py, api/routes/skus.py |
| T16 | Party + Sync + PO APIs | `DONE` | api/routes/parties.py, api/routes/sync_status.py, api/routes/po.py, api/routes/suppliers.py |
| T17 | React App Scaffolding (shadcn/ui) | `DONE` | dashboard/src/main.tsx, App.tsx, lib/api.ts, lib/types.ts, components/Layout.tsx |
| T18 | Brand Overview Page | `DONE` | dashboard/src/pages/BrandOverview.tsx, components/StatusBadge.tsx |
| T19 | SKU Detail Page | `DONE` | dashboard/src/pages/SkuDetail.tsx, components/StockTimelineChart.tsx, components/TransactionHistory.tsx |
| T20 | PO Builder + Party Classification Pages | `DONE` | dashboard/src/pages/PoBuilder.tsx, PartyClassification.tsx, SupplierManagement.tsx |
| T21 | Deployment Prep (no auth in V1) | `NOT STARTED` | |

**Status values:** `NOT STARTED` → `IN PROGRESS` → `DONE` → `VERIFIED`

---

## Task Dependencies (Execution Order)

```
Phase 1: Setup & Extraction
  T01 ──┬── T02 ── T03
        └── T04

Phase 2: Database & Loading
  T02+T04 ── T05 ──┬── T06 ── T07 ── T08
                    └───────────────────┘

Phase 3: Computation Engine
  T08 ── T09 ── T10 ── T11 ── T12

Phase 4: Nightly Sync
  T06+T08+T12 ── T13

Phase 5: Backend API
  T04 ── T14 ──┬── T15
               └── T16

Phase 6: Frontend
  T14 ── T17 ──┬── T18
               ├── T19
               └── T20

Phase 7: Deployment
  T14+T20 ── T21
```

**Parallel tracks:** After T01+T04, the backend (T05-T13) and API (T14-T16) can proceed in parallel. Frontend (T17-T20) requires T14+T15 minimum.

---

## Manual Steps (Not Code Tasks)

These require human action, not AI coding. Track them here:

| Step | Description | Status |
|------|-------------|--------|
| M01 | Buy Tally Prime license (Rs.750), install locally | `DONE` |
| M02 | Copy production Tally DB from AWS EC2 (35.154.1.129) | `DONE` |
| M03 | Enable Tally HTTP server on port 9000 | `DONE` |
| M04 | Install PostgreSQL, create database `artlounge_reorder` | `DONE` |
| M05 | Run T03 test extraction, inspect XML responses | `DONE` |
| M06 | Manually classify parties in CSV (30-60 min) | `NOT STARTED` |
| M07 | Create Railway account, provision Postgres + web service | `NOT STARTED` |
| M08 | Set up Windows Task Scheduler on AWS box (nightly 2 AM) | `NOT STARTED` |
| M09 | Configure DNS CNAME for wholesaleorders.artlounge.in | `NOT STARTED` |

---

## File Inventory

After all tasks complete, the project should contain:

```
ReOrderingProject/
├── Tasks/                          # This folder — task specs & tracker
├── Project Files/                  # Original spec documents (00-10)
├── src/                            # All application code lives here
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── tally_client.py         # T02
│   │   ├── xml_requests.py         # T02
│   │   ├── xml_parser.py           # T05
│   │   ├── data_loader.py          # T06
│   │   ├── party_classifier.py     # T07
│   │   ├── transaction_loader.py   # T08
│   │   └── test_extraction.py      # T03
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── stock_position.py       # T09
│   │   ├── velocity.py             # T10
│   │   ├── reorder.py              # T11
│   │   ├── aggregation.py          # T12
│   │   └── pipeline.py             # T12
│   ├── sync/
│   │   ├── __init__.py
│   │   ├── nightly_sync.py         # T13
│   │   ├── sync_helpers.py         # T13
│   │   └── email_notifier.py       # T13
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                 # T14
│   │   ├── database.py             # T14
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── brands.py           # T15
│   │       ├── skus.py             # T15
│   │       ├── po.py               # T16
│   │       ├── parties.py          # T16
│   │       ├── sync_status.py      # T16
│   │       ├── suppliers.py        # T16
│   │       └── health.py           # T21
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py             # T01
│   │   └── suppliers.json          # T04
│   ├── db/
│   │   └── schema.sql              # T04
│   ├── data/
│   │   ├── party_classification.csv
│   │   └── sample_responses/
│   ├── dashboard/                  # React frontend (Vite + shadcn/ui)
│   │   ├── src/
│   │   │   ├── main.tsx            # T17
│   │   │   ├── App.tsx             # T17
│   │   │   ├── lib/
│   │   │   │   ├── api.ts          # T17
│   │   │   │   └── types.ts        # T17
│   │   │   ├── components/
│   │   │   │   ├── Layout.tsx      # T17, T20
│   │   │   │   ├── StatusBadge.tsx # T18
│   │   │   │   ├── StockTimelineChart.tsx # T19
│   │   │   │   └── TransactionHistory.tsx # T19
│   │   │   └── pages/
│   │   │       ├── BrandOverview.tsx       # T18
│   │   │       ├── SkuDetail.tsx           # T19
│   │   │       ├── PoBuilder.tsx           # T20
│   │   │       ├── PartyClassification.tsx # T20
│   │   │       └── SupplierManagement.tsx  # T20
│   │   └── ...
│   ├── tests/                      # Full test suite
│   ├── requirements.txt            # T01
│   ├── Procfile                    # T14
│   ├── .env.example                # T01
│   └── .gitignore                  # T01
```
