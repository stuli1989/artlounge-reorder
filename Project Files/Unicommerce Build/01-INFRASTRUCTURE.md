# 01 — Infrastructure Setup

## Git Branch

```bash
git checkout -b feature/unicommerce
```

All UC work stays on this branch. Main stays Tally-based. Periodically rebase main into feature branch to stay current with any Tally-side fixes.

## Database

Create a separate local database. Zero risk to production Tally data.

```bash
PGPASSWORD=admin "/c/Program Files/PostgreSQL/17/bin/psql" -U postgres -c "CREATE DATABASE artlounge_reorder_uc OWNER reorder_app"
```

Connection string: `postgresql://reorder_app:password@localhost:5432/artlounge_reorder_uc`

Quick connect:
```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder_uc
```

## Config Changes

`src/config/settings.py` — remove Tally-specific, add UC settings:

```python
# Remove:
TALLY_HOST = ...
TALLY_PORT = ...
COMPANY_NAME = ...

# Add:
UC_TENANT = os.getenv("UC_TENANT", "ppetpl")
UC_BASE_URL = f"https://{UC_TENANT}.unicommerce.com"
UC_USERNAME = os.getenv("UC_USERNAME")       # kshitij@artlounge.in
UC_PASSWORD = os.getenv("UC_PASSWORD")       # stored in env, never in code
UC_TOKEN_EXPIRY_BUFFER = 300                 # refresh token 5 min before expiry

# Keep:
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://reorder_app:password@localhost:5432/artlounge_reorder_uc")
FY_START_DATE = ...
FY_END_DATE = ...
# ... all other existing settings
```

## Environment Variables

For local development, create `.env` file (already in `.gitignore`):

```
UC_TENANT=ppetpl
UC_USERNAME=kshitij@artlounge.in
UC_PASSWORD=<password>
DATABASE_URL=postgresql://reorder_app:password@localhost:5432/artlounge_reorder_uc
```

## Project Structure

New `src/unicommerce/` module alongside existing `src/extraction/`:

```
src/
├── unicommerce/           # NEW — UC API integration
│   ├── __init__.py
│   ├── client.py          # OAuth + REST client
│   ├── catalog.py         # SKU/product data
│   ├── inventory.py       # Inventory snapshots
│   ├── orders.py          # Sale orders + shipping packages
│   ├── returns.py         # CIR + RTO returns
│   ├── inbound.py         # POs + GRNs
│   └── sync.py            # Nightly sync orchestrator
├── engine/                # MODIFIED — new formulae
│   ├── stock_position.py  # Rewritten for forward-compute
│   ├── velocity.py        # Updated formulae
│   ├── reorder.py         # Updated formulae
│   ├── classification.py  # Updated (calendar weeks for XYZ)
│   ├── pipeline.py        # Modified orchestration
│   ├── aggregation.py     # Minor updates
│   └── ...                # effective_values, override_drift etc (unchanged)
├── extraction/            # KEEP for reference, not imported
├── api/                   # UNCHANGED (minor label tweaks)
├── dashboard/             # UNCHANGED (minor label tweaks)
├── db/                    # Schema updates
├── config/                # Settings updates
├── sync/                  # sync_helpers, email_notifier (unchanged)
└── tests/                 # New UC-specific tests
```

## Dependencies

New pip packages needed:

```
requests          # HTTP client for UC API (already likely installed)
python-dotenv     # .env file loading (if not already present)
```

No new heavy dependencies. UC API is standard REST/JSON — `requests` + `json` is sufficient.
