# Project Instructions

## Environment Commands

- **Python:** Use `py` (not `python` or `python3`)
- **PostgreSQL:** Binaries are at `"/c/Program Files/PostgreSQL/17/bin/"` — not in PATH
  - psql: `"/c/Program Files/PostgreSQL/17/bin/psql"`
  - createdb: `"/c/Program Files/PostgreSQL/17/bin/createdb"`
  - pg_dump: `"/c/Program Files/PostgreSQL/17/bin/pg_dump"`
  - Always use full path when invoking any pg tool

## Local Database

- **Superuser:** postgres / admin
- **App user:** reorder_app / password
- **Database:** artlounge_reorder
- **Connection string:** `postgresql://reorder_app:password@localhost:5432/artlounge_reorder`
- **Quick connect:** `PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder`

## Project Paths

- **Source code:** `src/` (all code lives here)
- **Venv:** `src/venv/` — activate with `src/venv/Scripts/python` or `src/venv/Scripts/pip`
- **Run Python in project:** `cd src && ./venv/Scripts/python`

## Tally API Rules (IMPORTANT)

- **Do NOT use Day Book report** — `<TYPE>Data</TYPE><ID>Day Book</ID>` returns only 1 voucher. Broken for our use case.
- **Use TDL Collections for vouchers** — `<TYPE>Collection</TYPE>` with custom `<COLLECTION>` definition works correctly.
- **TDL Collections ignore SVFROMDATE/SVTODATE** — All FY vouchers are always returned. Date filtering must be done in Python after parsing.
- **Use FETCH for sub-objects, not NATIVEMETHOD** — `<NATIVEMETHOD>AllInventoryEntries</NATIVEMETHOD>` causes Tally to timeout. Use `<FETCH>AllInventoryEntries.StockItemName</FETCH>` (one FETCH per field).
- **XML sanitization** — Tally emits invalid XML character references like `&#4;`. The `TallyClient._sanitize_xml()` method strips these. Always use `send_request()` (not raw parsing) for safe XML.
- **Full FY voucher pull** — ~190 MB, ~110 seconds. Acceptable for nightly sync. Tally may hang if you send a new request while it's still processing; restart Tally if it gets stuck.

## Tally Data Shape

- **168 brands** (stock categories), **22,538 SKUs** (stock items), **1,276 ledgers**
- **~17,300 vouchers/FY**, **~92,000 inventory line items/FY**
- Voucher types with inventory: Sales-Tally, Sales Store, Sales, Sales-Flipkart, Sales-Amazon, Sales-ALKG, Purchase, Credit Note, Physical Stock, Debit Note
- Voucher types without inventory: Journal, Receipt, Payment, Contra, Sales-Freight
- Inventory entry fields: `STOCKITEMNAME`, `ACTUALQTY`, `RATE`, `AMOUNT` (inside `ALLINVENTORYENTRIES.LIST`)
- Party name is the ONLY way to distinguish sales channels (wholesale vs online vs store)
