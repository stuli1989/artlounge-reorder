# T03: Test Extraction Script

## Prerequisites
- T02 completed (TallyClient and XML requests exist)
- **Manual:** Tally Prime running locally with HTTP server on port 9000

## Objective
Create a script that validates Tally connectivity and pulls sample data for all 4 extraction types, saving raw XML responses to disk for inspection.

## File to Create

### `extraction/test_extraction.py`

A standalone script (run with `python extraction/test_extraction.py` from project root).

Steps it should execute:
1. **Test connection** — call `client.test_connection()`, exit if fails
2. **Pull stock categories** — save raw XML to `data/sample_responses/stock_categories.xml`, count and print first 10 category names
3. **Pull stock items** — save to `data/sample_responses/stock_items.xml`, count total items, print count by category (brand) for top 15 brands
4. **Pull ledger list** — save to `data/sample_responses/ledgers.xml`, count total ledgers, group and print by parent (Sundry Debtors, Sundry Creditors, etc.)
5. **Pull vouchers (current month only as test)** — save to `data/sample_responses/vouchers_{from}_{to}.xml`, print file size and date range

Each step should:
- Print a clear header with step number
- Handle errors gracefully (print error, continue to next step)
- Save raw bytes to file
- Print summary statistics
- Use timeout=600 for stock items and vouchers (large responses)

End with a summary message telling the user to inspect the saved XML files before proceeding.

The script should create the output directory (`data/sample_responses/`) if it doesn't exist.

## Important Notes
- This script is for **manual testing only** — not part of the nightly sync
- The XML responses saved here become the basis for building parsers (T05)
- If voucher response is too large, suggest monthly batching in the output message
- Stock items may timeout for very large catalogs — catch and suggest per-brand pulling

## Acceptance Criteria
- [ ] Script runs from project root: `python extraction/test_extraction.py`
- [ ] Creates `data/sample_responses/` directory automatically
- [ ] Saves 4 XML files (categories, items, ledgers, vouchers)
- [ ] Prints counts and summaries for each extraction
- [ ] Handles connection errors, timeouts, and XML parse errors gracefully
- [ ] Does not crash if one step fails — continues to next
