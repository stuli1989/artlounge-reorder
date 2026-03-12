# T08: Transaction Data Loader

## Prerequisites
- T05 completed (XML parsers exist, especially `parse_vouchers`)
- T07 completed (party classification exists in database)

## Objective
Build the module that pulls inventory vouchers from Tally, enriches them with channel classification, and loads into the transactions table.

## File to Create

### `extraction/transaction_loader.py`

#### 1. `lookup_party_channel(db_conn, party_name: str) -> str`
- Look up the party's channel from the `parties` table
- Return the channel string, or 'unclassified' if not found
- Cache results in a dict to avoid repeated queries (parties don't change during a sync)

#### 2. `load_transactions(db_conn, parsed_vouchers: list[dict]) -> int`
- Insert parsed voucher records into `transactions` table
- Map fields:
  - `date` → `txn_date` (parse YYYYMMDD to date)
  - `party` → `party_name`
  - `voucher_type` → `voucher_type`
  - `voucher_number` → `voucher_number`
  - `stock_item` → `stock_item_name`
  - `quantity` → `quantity` (always positive)
  - `is_inward` → `is_inward`
  - `rate` → `rate`
  - `amount` → `amount`
  - `channel` → looked up from parties table
  - `tally_master_id`, `tally_alter_id`
- Use `ON CONFLICT DO NOTHING` on the UNIQUE constraint (prevents duplicate imports)
- Return count of newly inserted rows

#### 3. `generate_monthly_ranges(from_date: str, to_date: str) -> list[tuple]`
Generate (start, end) tuples for each calendar month in the range.
- Input dates in YYYYMMDD format
- Output tuples of (YYYYMMDD, YYYYMMDD)
- Example: `("20250401", "20250615")` → `[("20250401","20250430"), ("20250501","20250531"), ("20250601","20250615")]`

#### 4. `sync_transactions(tally_client, db_conn, from_date: str, to_date: str) -> int`
Full sync orchestrator:
```python
def sync_transactions(tally_client, db_conn, from_date, to_date):
    """Pull vouchers from Tally in monthly batches and load into database."""
    total_synced = 0

    # Build party channel cache
    channel_cache = build_party_channel_cache(db_conn)

    for month_start, month_end in generate_monthly_ranges(from_date, to_date):
        print(f"  Pulling {month_start} to {month_end}...")
        try:
            xml_request = inventory_vouchers_request(month_start, month_end)
            raw = tally_client.send_request_raw(xml_request, timeout=600)
            vouchers = parse_vouchers(raw)

            # Enrich with channel
            for v in vouchers:
                v['channel'] = channel_cache.get(v['party'], 'unclassified')

            inserted = load_transactions(db_conn, vouchers)
            total_synced += inserted
            print(f"  -> {len(vouchers)} parsed, {inserted} new")
        except Exception as e:
            print(f"  -> ERROR for {month_start}-{month_end}: {e}")
            continue  # Don't fail entire sync for one month

    return total_synced
```

#### 5. `build_party_channel_cache(db_conn) -> dict`
- Query all parties and their channels
- Return dict: `{party_name: channel}`

## Date Format Note
Tally uses YYYYMMDD format (e.g., "20250410"). PostgreSQL DATE columns accept this format directly. When converting for display, use `datetime.strptime(date_str, "%Y%m%d").date()`.

## Important Notes
- Monthly batching prevents Tally timeouts — the full year Day Book can be enormous
- `ON CONFLICT DO NOTHING` handles re-pulling overlapping date ranges safely
- If a month fails, continue with the next — partial sync is better than no sync
- The party channel cache avoids N+1 queries during enrichment

## Acceptance Criteria
- [ ] Monthly batching correctly splits date ranges across calendar months
- [ ] Party channel lookup is cached (no per-voucher queries)
- [ ] `ON CONFLICT DO NOTHING` prevents duplicates when re-syncing overlapping dates
- [ ] Individual month failures don't crash the full sync
- [ ] Dates correctly parsed from YYYYMMDD strings
- [ ] Returns count of newly inserted transactions
