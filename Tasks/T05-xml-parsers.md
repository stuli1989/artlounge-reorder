# T05: XML Response Parsers

## Prerequisites
- T02 completed (TallyClient exists)
- Ideally: T03 has been run and sample XML files exist in `data/sample_responses/`

## Objective
Build parsers that convert Tally XML responses into Python dicts ready for database insertion.

## File to Create

### `extraction/xml_parser.py`

Four parser functions plus a utility:

#### Utility: `parse_tally_quantity(qty_str: str) -> float`
Tally returns quantities with units attached like "45 pcs", "-12 nos", "0.5 kg".
- Strip everything except digits, minus sign, decimal point
- Use regex: `r'^\s*([-]?\d+\.?\d*)'`
- Return 0.0 for empty/None input

#### 1. `parse_stock_categories(xml_bytes: bytes) -> list[dict]`
```python
# Expected response structure:
# <ENVELOPE>
#   <STOCKCATEGORY NAME="Speedball">
#     <PARENT>Primary</PARENT>
#     <MASTERID>123</MASTERID>
#   </STOCKCATEGORY>
#   ...
# </ENVELOPE>

# Return list of:
{
    'name': str,       # Category/brand name
    'parent': str,     # Usually "Primary"
}
```
- Name might be in NAME attribute OR NAME child element — check both
- Use `root.iter('STOCKCATEGORY')` to find all regardless of nesting

#### 2. `parse_stock_items(xml_bytes: bytes) -> list[dict]`
```python
# Return list of:
{
    'name': str,            # SKU name
    'stock_group': str,     # Parent (product sub-type)
    'category': str,        # Stock category = BRAND
    'base_unit': str,       # "pcs", "nos"
    'closing_balance': float,  # Parsed from quantity string
    'closing_value': float,
    'opening_balance': float,
}
```
- Use `root.iter('STOCKITEM')`
- Parse closing_balance and opening_balance using `parse_tally_quantity()`
- Category field maps to brand — this is critical

#### 3. `parse_ledgers(xml_bytes: bytes) -> list[dict]`
```python
# Return list of:
{
    'name': str,      # Ledger/party name
    'parent': str,    # Group (Sundry Debtors, Sundry Creditors, etc.)
}
```
- Use `root.iter('LEDGER')`
- Parent group is useful for pre-classification (Sundry Creditors = likely supplier)

#### 4. `parse_vouchers(xml_bytes: bytes) -> list[dict]`
This is the most complex parser. Each voucher contains nested inventory entries.

```python
# Return list of:
{
    'date': str,            # YYYYMMDD or YYYY-MM-DD (from Tally)
    'party': str,           # Party/ledger name
    'voucher_type': str,    # "Sales", "Sales-Tally", "Purchase", etc.
    'voucher_number': str,
    'stock_item': str,      # SKU name
    'quantity': float,      # Absolute value (always positive)
    'is_inward': bool,      # True if purchase/inward, False if sale/outward
    'rate': float,
    'amount': float,
    'tally_master_id': str,
    'tally_alter_id': str,
}
```

Key parsing logic:
- Iterate `root.iter('VOUCHER')` for each voucher
- Within each voucher, iterate `INVENTORYENTRIES.LIST` for inventory line items
- Date might be in `VOUCHER` attribute `DATE` or child element `DATE`
- Tally dates are in YYYYMMDD format (e.g., "20250410")
- Party is in `PARTYLEDGERNAME` element
- Quantity: Tally uses negative for outward. Parse with `parse_tally_quantity()`, then:
  - If negative → `is_inward = False`, quantity = abs(value)
  - If positive → `is_inward = True`, quantity = value
- The ACTUALQTY or BILLEDQTY element contains the quantity
- Rate is in RATE element, amount in AMOUNT element

**Important:** The exact XML structure may vary from what's documented. The parser should be defensive — use `.findtext()` with defaults, don't crash on missing elements. After running T03 and inspecting actual XML, this parser may need adjustment.

## Acceptance Criteria
- [ ] All 4 parsers accept `bytes` input and return `list[dict]`
- [ ] `parse_tally_quantity()` handles: "45 pcs" → 45.0, "-12 nos" → -12.0, "" → 0.0, None → 0.0
- [ ] `parse_vouchers()` correctly determines is_inward from quantity sign
- [ ] Parsers don't crash on missing/unexpected elements — use safe defaults
- [ ] Each parser can work with XML loaded from file: `parse_xxx(open(path, 'rb').read())`
