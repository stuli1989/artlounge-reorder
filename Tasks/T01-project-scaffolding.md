# T01: Project Scaffolding & Config

## Prerequisites
None

## Objective
Create the project folder structure, Python virtual environment config, requirements files, and settings module.

## Files to Create

### 1. `requirements.txt` (project root)
```
requests
lxml
psycopg2-binary
fastapi
uvicorn[standard]
openpyxl
pandas
python-dotenv
```

### 2. `config/settings.py`
```python
"""
Application settings. Uses environment variables with local dev fallbacks.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Tally connection (only used by sync agent, not the web app)
TALLY_HOST = os.environ.get("TALLY_HOST", "localhost")
TALLY_PORT = int(os.environ.get("TALLY_PORT", "9000"))

# Database
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://reorder_app:password@localhost:5432/artlounge_reorder"
)

# Email notifications (for sync failure alerts)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")

# Financial year
FY_START = "20250401"  # Apr 1, 2025
FY_END = "20260331"    # Mar 31, 2026

# Company name in Tally
COMPANY_NAME = "Platinum Painting Essentials & Trading Pvt. Ltd."
```

### 3. `config/__init__.py`
Empty file.

### 4. `.env.example`
```
TALLY_HOST=localhost
TALLY_PORT=9000
DATABASE_URL=postgresql://reorder_app:password@localhost:5432/artlounge_reorder
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFY_EMAIL=alerts@artlounge.in
```

### 5. `.gitignore`
```
venv/
__pycache__/
*.pyc
.env
data/sample_responses/
dashboard/node_modules/
dashboard/build/
*.egg-info/
```

## Folder Structure to Create

All application code lives inside `src/` within the project root:

```
ReOrderingProject/
├── Tasks/                  (task specs — already exists)
├── Project Files/          (spec docs — already exists)
└── src/                    (all code goes here)
    ├── extraction/
    │   └── __init__.py
    ├── sync/
    │   └── __init__.py
    ├── engine/
    │   └── __init__.py
    ├── api/
    │   ├── __init__.py
    │   └── routes/
    │       └── __init__.py
    ├── db/
    ├── config/
    │   ├── __init__.py
    │   └── settings.py
    ├── data/
    │   └── sample_responses/
    ├── tests/
    │   └── __init__.py
    ├── dashboard/          (React app — created in T17)
    ├── requirements.txt
    ├── .env.example
    └── .gitignore
```

## Acceptance Criteria
- [ ] All folders exist with `__init__.py` files where needed
- [ ] `config/settings.py` loads env vars with sensible defaults
- [ ] `requirements.txt` lists all Python dependencies
- [ ] `.gitignore` excludes venv, __pycache__, .env, sample data, node_modules
- [ ] `.env.example` documents all env vars
