# 09 — Deployment Guide

## Overview

Production runs on Railway (managed platform). The sync agent runs on the AWS Windows box alongside Tally and pushes data to Railway's Postgres over the internet.

Development happens locally on your machine with local Tally.

## Architecture

```
AWS Windows box (already exists, no cost change)
├── Tally Prime (port 9000, localhost only — never exposed to internet)
└── Sync Agent (Python, Windows Task Scheduler, nightly 2 AM)
    ├── Reads from Tally at localhost:9000
    ├── Parses XML, computes velocities, stockout predictions, reorder flags
    └── Writes results to Railway Postgres over SSL ──► HTTPS

Railway ($5-10/month)
├── PostgreSQL database (managed, auto-backups, SSL)
├── FastAPI service (serves API + static React build)
│   ├── /api/* → data endpoints
│   └── /* → React dashboard
└── Custom domain: wholesaleorders.artlounge.in (SSL automatic)

You → Chrome → wholesaleorders.artlounge.in → dashboard
```

Key design decision: **Tally's port 9000 is never exposed to the internet.** The sync agent runs locally on the same machine as Tally, reads data at localhost, does all the heavy computation locally, and only pushes processed results outward to Railway over a standard HTTPS/SSL database connection.

## Development Environment

Everything runs on your local Windows machine during development:

```
Your Machine
├── Tally Prime (local copy, port 9000)
├── PostgreSQL (local, port 5432)  ← for dev/testing
├── Python backend (local, port 8000)
└── React dev server (local, port 3000)
```

You develop and test locally, then deploy to Railway when ready.

## Step 1: Create Railway Account and Project

1. Go to https://railway.com and sign up
2. Create a new project (call it "artlounge-reorder" or similar)

### Set up Postgres database:

3. In the project, click "New" → "Database" → "PostgreSQL"
4. Railway provisions a Postgres instance automatically
5. Click the Postgres service → "Variables" tab
6. Copy the `DATABASE_URL` — it looks like:
   ```
   postgresql://postgres:XXXX@containers-us-west-XXX.railway.app:5432/railway
   ```
7. Save this URL. The sync agent and the FastAPI app both need it.

### Set up the web service:

8. In the same project, click "New" → "GitHub Repo" (connect your repo)
   - Or "New" → "Empty Service" if deploying manually
9. Railway auto-detects Python and builds from your repo
10. Set environment variables for the service (Settings → Variables):
    ```
    DATABASE_URL=postgresql://postgres:XXXX@...  (from step 6)
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=your-email@gmail.com
    SMTP_PASSWORD=your-app-password
    NOTIFY_EMAIL=alerts@artlounge.in
    ```

### Configure the custom domain:

11. In the web service settings, go to "Settings" → "Networking" → "Custom Domain"
12. Add `wholesaleorders.artlounge.in`
13. Railway gives you a CNAME target (e.g., `xxxx.up.railway.app`)
14. In your DNS provider (Cloudflare), add a CNAME record:
    - Name: `wholesaleorders`
    - Target: `xxxx.up.railway.app`
15. Railway provisions SSL automatically. Within a few minutes, `https://wholesaleorders.artlounge.in` is live.

## Step 2: Project Structure for Railway

Railway needs to know how to build and run your app. The key files:

### `requirements.txt` (in project root)
```
fastapi
uvicorn[standard]
psycopg2-binary
openpyxl
pandas
lxml
requests
```

### `Procfile` (in project root)
```
web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Railway sets the `$PORT` environment variable automatically.

### `api/main.py` — FastAPI app setup
```python
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# API routes
from api.routes import brands, skus, po, parties, sync_status, suppliers
app.include_router(brands.router, prefix="/api")
app.include_router(skus.router, prefix="/api")
app.include_router(po.router, prefix="/api")
app.include_router(parties.router, prefix="/api")
app.include_router(sync_status.router, prefix="/api")
app.include_router(suppliers.router, prefix="/api")

# Serve React static files (after building: npm run build)
# The build output goes into dashboard/dist/
build_dir = os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'dist')
if os.path.exists(build_dir):
    app.mount("/", StaticFiles(directory=build_dir, html=True), name="static")
```

### Database connection
```python
# config/settings.py
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

# For local development, fall back to local Postgres
if not DATABASE_URL:
    DATABASE_URL = "postgresql://reorder_app:password@localhost:5432/artlounge_reorder"
```

## Step 3: Initialize the Database

### Option A: From your local machine (during development)
Use the Railway Postgres connection string to run the schema directly:

```bash
psql "postgresql://postgres:XXXX@containers-us-west-XXX.railway.app:5432/railway" -f db/schema.sql
```

### Option B: From Railway's built-in query tool
Railway has a "Data" tab in the Postgres service where you can run SQL directly in the browser. Paste the contents of `schema.sql` there.

## Step 4: Configure the Sync Agent on AWS Windows Box

The sync agent is a Python script that runs on the AWS Windows machine. It does NOT run on Railway — it runs alongside Tally.

### Install Python on the AWS Windows box
If not already installed, download Python 3.11+ from python.org.

### Set up the sync agent
```bash
# On the AWS Windows box
mkdir C:\artlounge-sync
cd C:\artlounge-sync

python -m venv venv
venv\Scripts\activate

pip install requests lxml psycopg2-binary openpyxl pandas
```

### Copy the extraction and engine code
Copy these folders from your project to the AWS box:
```
C:\artlounge-sync\
├── extraction\       # tally_client.py, xml_requests.py, xml_parser.py
├── engine\           # stock_position.py, velocity.py, reorder.py, aggregation.py
├── sync\             # nightly_sync.py
└── config\
    └── settings.py   # Contains Railway DATABASE_URL
```

### Configure settings
```python
# config/settings.py on the AWS box
TALLY_HOST = "localhost"
TALLY_PORT = 9000

# Railway Postgres connection string
DATABASE_URL = "postgresql://postgres:XXXX@containers-us-west-XXX.railway.app:5432/railway"
```

### Test the sync agent
```bash
cd C:\artlounge-sync
venv\Scripts\activate
python sync\nightly_sync.py --full
```

This should:
1. Connect to Tally at localhost:9000
2. Pull all data
3. Compute metrics
4. Write to Railway Postgres
5. Take 30-60 minutes on first run

### Schedule nightly runs
1. Open Windows Task Scheduler
2. Create Basic Task → "Art Lounge Nightly Sync"
3. Trigger: Daily at 2:00 AM
4. Action: Start a Program
   - Program: `C:\artlounge-sync\venv\Scripts\python.exe`
   - Arguments: `sync\nightly_sync.py`
   - Start in: `C:\artlounge-sync`
5. Under Conditions: uncheck "Start only if computer is on AC power"
6. Under Settings: check "Run task as soon as possible after a scheduled start is missed"

## Step 5: Deploy the Dashboard

### Build the React frontend locally
```bash
cd dashboard
npm install
npm run build
```

This creates a `dashboard/dist/` folder with static files.

### Deploy to Railway

If using GitHub integration (recommended):
1. Push your code to GitHub
2. Railway auto-detects changes and deploys
3. Every `git push` triggers a new deployment

If deploying manually:
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Deploy
railway up
```

## Step 6: Verify Production Setup

**Note:** No authentication in V1. The dashboard is publicly accessible. Auth will be added in a future version.

- [ ] `https://wholesaleorders.artlounge.in` loads the dashboard
- [ ] Brand Overview shows real data
- [ ] SKU Detail shows correct metrics for known items (check Speedball Sealer)
- [ ] PO Builder generates and downloads Excel
- [ ] Sync log shows last successful sync time
- [ ] Let it run for 3 nights unattended, verify sync_log in Railway Postgres

## Ongoing Maintenance

| Task | How | Frequency |
|------|-----|-----------|
| Classify new parties | Dashboard UI or direct database update | As needed (when sync flags unknowns) |
| Update supplier lead times | Dashboard settings or database update | When lead times change |
| Check sync is running | Dashboard shows "last sync" timestamp | Glance daily |
| Code updates | `git push` → Railway auto-deploys | As needed |
| Database backups | Automatic (Railway) | Daily (managed by Railway) |
| Server maintenance | None — Railway handles it | Never |
| SSL renewal | Automatic (Railway) | Never |

## Cost Summary

| Item | Monthly Cost |
|------|-------------|
| Railway Hobby plan | $5 (includes $5 usage credit) |
| Possible usage overage | $0-5 depending on month |
| AWS Windows EC2 | No change (already running Tally) |
| **Total additional cost** | **$5-10/month (~₹400-800)** |

## Rollback / Migration

If Railway ever becomes a problem, the entire stack is portable:

1. Export the database: `pg_dump` from Railway
2. Import into any Postgres instance (Hetzner VPS, AWS RDS, local, etc.)
3. Change the `DATABASE_URL` in the sync agent and redeploy the web app
4. Update DNS to point to new host

Nothing in the codebase is Railway-specific. It's a standard Python app with a standard Postgres database.
