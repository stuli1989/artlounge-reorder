# TASKS — Progress Tracker

## How to Use

Update the Status column as work progresses. Reference BUILD-ORDER.md for the full sequence and spec docs for details.

## Task List

| Task | Description | Doc | Status | Notes |
|---|---|---|---|---|
| **Phase 1: Infrastructure** | | | | |
| T01 | Branch + database + config | 01-INFRASTRUCTURE | Pending | |
| T02 | UC database schema | 04-DB-SCHEMA | Pending | |
| **Phase 2: API Client** | | | | |
| T03 | UC REST client (OAuth, retry, pagination) | 02-UC-API-CLIENT | Pending | |
| T04 | Catalog/SKU ingestion | 03-DATA-INGESTION §1 | Pending | |
| **Phase 3: Data Ingestion** | | | | |
| T05 | Inventory snapshot ingestion | 03-DATA-INGESTION §2 | Pending | |
| T06 | Dispatch ingestion (shipping packages) | 03-DATA-INGESTION §3 | Pending | |
| T07 | Returns ingestion (CIR + RTO) | 03-DATA-INGESTION §4 | Pending | |
| T08 | GRN/PO ingestion | 03-DATA-INGESTION §5 | Pending | |
| **Phase 4: Computation Engine** | | | | |
| T09 | Stock position (forward from snapshots) | 05-COMPUTATION-ENGINE | Pending | |
| T10 | Velocity (all variants + guards) | 05-COMPUTATION-ENGINE | Pending | |
| T11 | Reorder (buffer fix, new statuses) | 05-COMPUTATION-ENGINE | Pending | |
| T12 | Classification (XYZ calendar weeks, buffer multiplier) | 05-COMPUTATION-ENGINE | Pending | |
| T13 | Pipeline + aggregation updates | 05-COMPUTATION-ENGINE | Pending | |
| **Phase 5: Sync Orchestrator** | | | | |
| T14 | Nightly incremental sync | 06-INCREMENTAL-SYNC | Pending | |
| T15 | Backfill module (transactions + positions) | 07-BACKFILL | Pending | |
| **Phase 6: API & Frontend** | | | | |
| T16 | API route updates | 08-API-FRONTEND | Pending | |
| T17 | Frontend label + UI updates | 08-API-FRONTEND | Pending | |
| **Phase 7: Testing** | | | | |
| T18 | Write and run all tests | 09-TESTING | Pending | |
| T19 | Comparison validation (UC vs Tally) | 09-TESTING | Pending | |
| **Phase 8: Deployment** | | | | |
| T20 | Railway deployment + cutover | 10-DEPLOYMENT | Pending | |

## Milestones

| Milestone | After Task | What It Means |
|---|---|---|
| **Data Flowing** | T08 | All UC data types pulling into DB correctly |
| **Engine Working** | T13 | Computation pipeline produces valid metrics |
| **Sync Running** | T14 | Nightly incremental sync works end-to-end |
| **Backfill Done** | T15 | Full FY historical data loaded |
| **Feature Complete** | T17 | Dashboard shows UC-sourced data correctly |
| **Validated** | T19 | Compared with Tally, team-approved |
| **Live** | T20 | Running on Railway in production |

## Blocked Items

| Item | Blocked On | Impact |
|---|---|---|
| Backfill Option A (accurate historical positions) | UC providing Transaction Ledger report | Can use Option B (approximate) until then |
| ALIBHIWANDI facility understanding | Team clarification | Not blocking — included in dynamic facility discovery |
