# BUILD-ORDER — Step-by-Step Development Sequence

## How to Use This Document

This is the master checklist. Follow these steps in order. Each step references the relevant detailed document. Do not skip ahead — each step validates assumptions that the next step depends on.

---

## Phase 1: Setup & Data Validation (Days 1-2)

### Step 1.1: Local Tally Setup ✓ DONE
**Doc:** `01-LOCAL-DEV-SETUP.md`
- [x] Buy ₹750 Tally Prime license
- [x] Copy production database from AWS Windows box
- [x] Install Tally locally, load company data
- [x] Enable HTTP server on port 9000
- [x] Verify with curl test (confirmed available at localhost:9000)

### Step 1.2: Dev Environment
**Doc:** `01-LOCAL-DEV-SETUP.md`
- [ ] Create project folder structure
- [ ] Set up Python venv with dependencies
- [ ] Install and configure PostgreSQL locally
- [ ] Create the database

### Step 1.3: First Data Pull (THE CRITICAL STEP)
**Doc:** `02-TALLY-XML-EXTRACTION.md`
- [ ] Build the TallyClient class
- [ ] Run test_extraction.py
- [ ] Inspect saved XML responses — understand the actual structure
- [ ] Adjust XML request templates if responses differ from expected
- [ ] Confirm: stock categories = brands ✓
- [ ] Confirm: stock items have category field ✓
- [ ] Confirm: voucher data includes party, stock item, quantity ✓
- [ ] Count: how many brands, how many SKUs, how many transactions
- [ ] Save sample responses in data/sample_responses/ for offline development

**STOP HERE if the data doesn't look right. Debug XML requests before proceeding.**

---

## Phase 2: Database & Party Classification (Days 2-3)

### Step 2.1: Create Database Schema
**Doc:** `03-DATABASE-SCHEMA.md`
- [ ] Run schema.sql to create all tables
- [ ] Verify tables created correctly

### Step 2.2: Build XML Parsers
**Doc:** `02-TALLY-XML-EXTRACTION.md`
- [ ] Build parser for stock categories response
- [ ] Build parser for stock items response
- [ ] Build parser for ledger list response
- [ ] Build parser for voucher/transaction response (this is the hardest one)
- [ ] Test each parser against saved XML samples

### Step 2.3: Load Master Data
- [ ] Parse and load stock categories into database
- [ ] Parse and load stock items into database
- [ ] Parse and load ledger list into parties table (all as 'unclassified')

### Step 2.4: Party Classification
**Doc:** `04-PARTY-CLASSIFICATION.md`
- [ ] Export parties to CSV
- [ ] Run pre-classification rules (MAGENTO2, Physical Stock, etc.)
- [ ] **USER ACTION: Manually classify all parties** (30-60 min)
- [ ] Load classified parties back into database
- [ ] Verify: no 'unclassified' parties remain

### Step 2.5: Load Transaction Data
- [ ] Pull full year of voucher data (batch by month if needed)
- [ ] Parse all vouchers
- [ ] Enrich with channel from parties table
- [ ] Load into transactions table
- [ ] Verify: row counts make sense, no obvious parsing errors
- [ ] Spot-check: find the Speedball Sealer transactions, compare against reference data (doc 10)

---

## Phase 3: Computation Engine (Days 3-5)

### Step 3.1: Stock Position Reconstruction
**Doc:** `05-COMPUTATION-ENGINE.md`
- [ ] Implement reconstruct_daily_positions()
- [ ] Test against Speedball Sealer reference data
- [ ] Verify: in-stock days match expected (68 + 91 = 159)
- [ ] Verify: out-of-stock period Jun 8 - Nov 25 detected correctly
- [ ] Verify: Physical Stock adjustment applied to balance, not counted as demand
- [ ] Verify: Art Lounge India - Purchase transactions excluded

### Step 3.2: Velocity Calculation
**Doc:** `05-COMPUTATION-ENGINE.md`
- [ ] Implement calculate_velocity()
- [ ] Test against Speedball Sealer
- [ ] Verify: wholesale and online velocities calculated separately
- [ ] Verify: only in-stock days used in denominator
- [ ] Verify: credit notes excluded from velocity

### Step 3.3: Days to Stockout
- [ ] Implement calculate_days_to_stockout()
- [ ] Test: Speedball Sealer should show ~10-13 days

### Step 3.4: Import History
- [ ] Implement detect_import_history()
- [ ] Test: should find 2 imports (May 2 and Nov 26) from Speedball Art Products LLC

### Step 3.5: Reorder Status
- [ ] Implement determine_reorder_status()
- [ ] Configure supplier lead times (start with Speedball = 180 days)
- [ ] Test: Speedball Sealer should be CRITICAL

### Step 3.6: Full Pipeline
- [ ] Implement run_computation_pipeline()
- [ ] Run against all SKUs
- [ ] Verify: sku_metrics table populated
- [ ] Verify: brand_metrics table populated
- [ ] Spot-check a few brands — do the numbers make sense?

---

## Phase 4: Nightly Sync (Days 5-6)

### Step 4.1: Sync Script
**Doc:** `06-NIGHTLY-SYNC.md`
- [ ] Implement nightly_sync.py with full and delta modes
- [ ] Implement monthly batching for transaction pull
- [ ] Implement new party detection
- [ ] Implement email notifications (success/failure via SMTP)
- [ ] Test: run --full, verify all data loads
- [ ] Test: run again (delta), verify only new data pulled, no duplicates
- [ ] Test: verify email sent on completion (configure SMTP settings first)

### Step 4.2: Scheduling (local for now)
- [ ] Set up Windows Task Scheduler to run nightly
- [ ] Verify it runs unattended
- [ ] Check sync_log table for success/failure tracking

---

## Phase 5: Dashboard (Days 6-10)

### Step 5.1: Backend API
**Doc:** `07-DASHBOARD-SPEC.md`
- [ ] Set up FastAPI app skeleton
- [ ] Implement GET /api/brands (brand overview)
- [ ] Implement GET /api/brands/{name}/skus (SKU detail)
- [ ] Implement GET /api/brands/{name}/skus/{item}/positions (chart data)
- [ ] Implement GET /api/brands/{name}/skus/{item}/transactions (history)
- [ ] Implement GET /api/sync/status (freshness indicator)
- [ ] Implement GET /api/parties/unclassified
- [ ] Implement POST /api/parties/classify
- [ ] Test all endpoints with curl or Postman

### Step 5.2: Frontend — Brand Overview
**Doc:** `07-DASHBOARD-SPEC.md`
- [ ] Set up React app with Tailwind CSS
- [ ] Build Brand Overview page with sortable table
- [ ] Add summary stat cards
- [ ] Add search and status filters
- [ ] Color coding for status

### Step 5.3: Frontend — SKU Detail
- [ ] Build SKU Detail page
- [ ] Sortable table with all columns
- [ ] Status badges (red/amber/green)
- [ ] Row expansion with stock timeline chart (Recharts)
- [ ] Transaction history panel

### Step 5.4: Frontend — PO Builder
**Doc:** `08-PO-BUILDER-SPEC.md`
- [ ] Build PO Builder page
- [ ] Settings bar (lead time, buffer, toggles)
- [ ] Editable table (checkboxes, editable qty, notes)
- [ ] Real-time recalculation when settings change
- [ ] Implement POST /api/export/po (backend)
- [ ] Excel export with openpyxl
- [ ] Download button

### Step 5.5: Global Elements + Management Pages
- [ ] Header with sync status
- [ ] Warning banner for unclassified parties
- [ ] Navigation between views
- [ ] Party classification page (simple form)
- [ ] Supplier management page (CRUD — add/edit/delete suppliers with lead times)

---

## Phase 6: Production Deployment (Days 10-12)

### Step 6.1: Railway Setup
**Doc:** `09-DEPLOYMENT.md`
- [ ] Create Railway account and project
- [ ] Provision Postgres database in Railway
- [ ] Copy `DATABASE_URL` connection string
- [ ] Run schema.sql against Railway Postgres (via psql or Railway's Data tab)

### Step 6.2: Deploy Web App
- [ ] Add `Procfile` and `requirements.txt` to project root
- [ ] Build React frontend (`npm run build`)
- [ ] Connect GitHub repo to Railway (or deploy via CLI)
- [ ] Set environment variables: `DATABASE_URL`, SMTP settings (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFY_EMAIL`)
- [ ] Verify the app starts and serves the dashboard (no auth — publicly accessible for V1)

### Step 6.3: Custom Domain
- [ ] Add `wholesaleorders.artlounge.in` in Railway service settings
- [ ] Add CNAME record in Cloudflare DNS pointing to Railway
- [ ] Wait for SSL provisioning (automatic, few minutes)
- [ ] Verify `https://wholesaleorders.artlounge.in` loads

### Step 6.4: Sync Agent on AWS Windows Box
- [ ] Install Python on AWS Windows machine (if not present)
- [ ] Set up sync agent folder with extraction, engine, and sync code
- [ ] Configure settings.py with `DATABASE_URL` pointing to Railway Postgres
- [ ] Run `nightly_sync.py --full` manually — verify data appears in Railway Postgres
- [ ] Set up Windows Task Scheduler for nightly 2 AM runs

### Step 6.5: Verify End-to-End
- [ ] Open `https://wholesaleorders.artlounge.in` from your browser
- [ ] Confirm all three views work with real data
- [ ] Export a test PO
- [ ] Let sync run unattended for 3+ nights
- [ ] Check sync_log table for success entries

---

## Post-Launch

- Sync failure emails will notify automatically — check inbox
- Classify new parties as they appear (dashboard warning banner)
- Manage suppliers and lead times via the Supplier Management page
- After 1-2 weeks of stable operation, consider enhancements:
  - Authentication (single-user password gate, then multi-user)
  - Historical PO tracking
  - Weighted/seasonal velocity adjustments
  - Multi-financial-year support
  - Mobile-responsive dashboard
