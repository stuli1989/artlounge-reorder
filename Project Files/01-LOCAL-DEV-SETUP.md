# 01 — Local Development Setup

## Overview

Before building anything on AWS, we develop and test everything locally. This requires:
1. A local Tally Prime installation with a copy of production data
2. Python environment for extraction scripts and backend
3. PostgreSQL for the database
4. Node.js for the React dashboard

## Step 1: Copy Tally Production Data

### On the AWS Windows machine (35.154.1.129):

1. RDP into the AWS Windows machine
2. Find the Tally data directory. Common locations:
   - `C:\Users\[username]\TallyPrime\Data\`
   - `C:\TallyPrime\Data\`
   - Check in Tally: F1 (Help) → Settings → Data Configuration shows the path
3. The company folder is typically named with a number (e.g., `10001`, `10002`)
4. The company name is "Platinum Painting Essentials & Trading Pvt. Ltd."
5. Zip the entire company folder
6. Download it (Google Drive, WeTransfer, or direct download)

### Expected folder structure:
```
Data/
  10001/        (or whatever your company number is)
    *.900       (Tally data files)
    *.tsf       (Tally data files)
    ...
```

## Step 2: Install Local Tally Prime

1. Download Tally Prime from https://tallysolutions.com/download/
2. Install with default settings
3. Activate with the ₹750 rental license
4. On first launch, go to F1 (Help) → Settings → Data Configuration
5. Set the data path to point to the folder where you placed the copied data
6. Open the company — verify you can see "Platinum Painting Essentials & Trading Pvt. Ltd."
7. Spot-check: go to Stock Summary, check a few items, make sure data looks right

## Step 3: Enable Tally HTTP Server

1. In Tally, press Alt+Z (Exchange) → Configure
2. Under Data Synchronisation, select "Client/Server configuration" and press Enter
3. Set these values:
   - **Tally Prime act as:** Both
   - **Enable ODBC:** Yes
   - **Port:** 9000
4. Press Enter to save
5. Tally will ask to restart — press Yes
6. After restart, verify: go to F1 (Help) → About → look for "Client/Server with ODBC Services"

### Verify HTTP server is working:

Open Command Prompt (or PowerShell) and run:
```bash
curl http://localhost:9000
```

You should get an XML response (might be an error message, but it proves Tally is listening).

For a more meaningful test, save this as `test_request.xml`:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>List of Companies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
```

Then run:
```bash
curl -X POST http://localhost:9000 -d @test_request.xml
```

You should see your company name in the response.

## Step 4: Python Environment Setup

### Install Python 3.11+ (if not already installed)
Download from https://python.org. During installation, check "Add Python to PATH".

### Create project directory and virtual environment
```bash
mkdir C:\Projects\artlounge-reorder
cd C:\Projects\artlounge-reorder

python -m venv venv
venv\Scripts\activate

pip install requests lxml psycopg2-binary fastapi uvicorn openpyxl pandas
```

### Project folder structure
```
artlounge-reorder/
├── extraction/
│   ├── tally_client.py        # HTTP client for Tally XML requests
│   ├── xml_requests.py        # XML request templates
│   ├── xml_parser.py          # Parse Tally XML responses
│   └── test_extraction.py     # Manual test script (run first!)
├── sync/
│   ├── nightly_sync.py        # Main sync job
│   ├── delta_detection.py     # Track what's changed since last sync
│   └── scheduler_config.py    # Cron/Task Scheduler setup
├── engine/
│   ├── stock_position.py      # Reconstruct daily stock positions
│   ├── velocity.py            # Calculate demand velocities
│   ├── reorder.py             # Stockout prediction and reorder flags
│   └── aggregation.py         # Roll up SKU → Brand summaries
├── api/
│   ├── main.py                # FastAPI app
│   ├── routes/
│   │   ├── brands.py          # Brand overview endpoint
│   │   ├── skus.py            # SKU detail endpoint
│   │   └── po.py              # PO builder endpoint
│   └── models.py              # Pydantic response models
├── dashboard/
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── BrandOverview.jsx
│   │   │   ├── SkuDetail.jsx
│   │   │   └── PoBuilder.jsx
│   │   └── components/
│   │       ├── StatusBadge.jsx
│   │       ├── VelocityChart.jsx
│   │       └── ReorderAlert.jsx
│   └── ...
├── db/
│   ├── schema.sql             # Database creation script
│   ├── seed_parties.sql       # Party classification data
│   └── migrations/            # Future schema changes
├── config/
│   ├── settings.py            # Configuration (Tally host, DB credentials, etc.)
│   └── suppliers.json         # Supplier lead times
├── data/
│   ├── party_classification.csv  # Your manual party mapping
│   └── sample_responses/         # Saved XML responses for offline dev
├── tests/
│   └── ...
└── README.md
```

## Step 5: PostgreSQL Setup

### Install PostgreSQL
Download from https://www.postgresql.org/download/windows/
Use default port 5432. Set a password for the `postgres` user.

### Create the database
```bash
psql -U postgres
```

```sql
CREATE DATABASE artlounge_reorder;
CREATE USER reorder_app WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE artlounge_reorder TO reorder_app;
\c artlounge_reorder
GRANT ALL ON SCHEMA public TO reorder_app;
```

## Step 6: Node.js Setup (for dashboard)

### Install Node.js 18+
Download from https://nodejs.org

### Initialize the React dashboard
```bash
cd C:\Projects\artlounge-reorder\dashboard
npx create-react-app . --template typescript
npm install axios recharts tailwindcss @headlessui/react lucide-react
```

## Verification Checklist

Before proceeding to data extraction (document 02), confirm:

- [ ] Local Tally is running with production data copy
- [ ] Company "Platinum Painting Essentials & Trading Pvt. Ltd." opens correctly
- [ ] HTTP server enabled on port 9000
- [ ] `curl http://localhost:9000` returns an XML response
- [ ] Python venv created with all packages installed
- [ ] PostgreSQL running, `artlounge_reorder` database created
- [ ] Node.js installed
- [ ] Project folder structure created

## Troubleshooting

### "curl is not recognized"
Install curl for Windows, or use PowerShell's `Invoke-WebRequest`:
```powershell
Invoke-WebRequest -Uri "http://localhost:9000" -Method POST -Body (Get-Content test_request.xml -Raw)
```

### Tally HTTP server not responding
- Make sure Tally is running as Administrator
- Check the port isn't blocked by Windows Firewall
- Verify in Tally About screen that ODBC services are shown
- Try port 9001 if 9000 is in use

### Company data not loading
- Ensure the full company folder was copied (not just individual files)
- Check the data path in Tally settings points to the parent `Data` folder, not the company subfolder
- The financial year might need to match — check current period in Tally
