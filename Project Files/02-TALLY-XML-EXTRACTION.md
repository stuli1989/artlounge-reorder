# 02 — Tally XML Data Extraction

## Overview

Tally Prime exposes an HTTP server that accepts XML POST requests and returns XML responses. This is the primary integration method — more powerful and reliable than ODBC for our use case.

The server listens on `http://localhost:9000` (or whatever port you configured). You send an XML request body via HTTP POST, and Tally returns an XML response with the requested data.

## How Tally XML Requests Work

Every request follows this structure:

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>  <!-- Export = read data, Import = write data -->
    <TYPE>...</TYPE>                      <!-- Data, Collection, or Object -->
    <ID>...</ID>                          <!-- Report name or collection name -->
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <!-- Report settings: period, format, company, etc. -->
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <!-- Optional: custom collection definitions -->
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

Key concepts:
- **TYPE=Collection**: Returns a list of objects (like a SQL SELECT)
- **TYPE=Data**: Returns a formatted report (like Stock Summary, Day Book)
- **TYPE=Object**: Returns a single object's full details
- **STATICVARIABLES**: Control report parameters like date range, company name, export format
- **TDL block**: Lets you define custom collections with specific fields (like writing a custom SQL query)

## The Python HTTP Client

Build this first. All extraction scripts use it.

```python
# extraction/tally_client.py

import requests
from lxml import etree

class TallyClient:
    """HTTP client for Tally Prime XML interface."""
    
    def __init__(self, host="localhost", port=9000):
        self.base_url = f"http://{host}:{port}"
    
    def send_request(self, xml_request: str, timeout=300) -> etree._Element:
        """
        Send XML request to Tally and return parsed XML response.
        
        Args:
            xml_request: XML string to send
            timeout: Request timeout in seconds (large responses can be slow)
            
        Returns:
            lxml Element tree of the response
            
        Raises:
            ConnectionError: If Tally is not reachable
            ValueError: If response is not valid XML
        """
        try:
            response = requests.post(
                self.base_url,
                data=xml_request.encode('utf-8'),
                headers={'Content-Type': 'application/xml'},
                timeout=timeout
            )
            response.raise_for_status()
            
            # Parse XML response
            root = etree.fromstring(response.content)
            return root
            
        except requests.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Tally at {self.base_url}. "
                "Is Tally running with HTTP server enabled on this port?"
            )
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Tally returned invalid XML: {e}")
    
    def send_request_raw(self, xml_request: str, timeout=300) -> bytes:
        """Send XML request and return raw bytes (for saving to file)."""
        response = requests.post(
            self.base_url,
            data=xml_request.encode('utf-8'),
            headers={'Content-Type': 'application/xml'},
            timeout=timeout
        )
        response.raise_for_status()
        return response.content
    
    def test_connection(self) -> bool:
        """Test if Tally is reachable and responding."""
        test_xml = """
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
        """
        try:
            root = self.send_request(test_xml)
            companies = root.findall('.//COMPANY')
            if companies:
                print(f"Connected. Found {len(companies)} company(ies):")
                for c in companies:
                    name = c.find('NAME')
                    if name is not None:
                        print(f"  - {name.text}")
                return True
            else:
                print("Connected but no companies found in response.")
                return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
```

## Required Data Extractions

We need four extractions. Run them in order.

### Extraction 1: Stock Categories (Brands)

This gives us the brand list.

```python
# extraction/xml_requests.py — STOCK CATEGORIES

STOCK_CATEGORIES_REQUEST = """
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>StockCategoryList</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="StockCategoryList" ISINITIALIZE="Yes">
            <TYPE>StockCategory</TYPE>
            <NATIVEMETHOD>Name</NATIVEMETHOD>
            <NATIVEMETHOD>Parent</NATIVEMETHOD>
            <NATIVEMETHOD>MasterId</NATIVEMETHOD>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
"""
```

**Expected response structure:**
```xml
<ENVELOPE>
  <STOCKCATEGORY NAME="Speedball">
    <PARENT>Primary</PARENT>
    <MASTERID>123</MASTERID>
  </STOCKCATEGORY>
  <STOCKCATEGORY NAME="Winsor &amp; Newton">
    <PARENT>Primary</PARENT>
    <MASTERID>124</MASTERID>
  </STOCKCATEGORY>
  ...
</ENVELOPE>
```

### Extraction 2: Stock Items (SKUs) with Category and Group

This is the full SKU master list with brand mapping.

```python
STOCK_ITEMS_REQUEST = """
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>StockItemList</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="StockItemList" ISINITIALIZE="Yes">
            <TYPE>Stock Item</TYPE>
            <NATIVEMETHOD>Name</NATIVEMETHOD>
            <NATIVEMETHOD>Parent</NATIVEMETHOD>
            <NATIVEMETHOD>Category</NATIVEMETHOD>
            <NATIVEMETHOD>BaseUnits</NATIVEMETHOD>
            <NATIVEMETHOD>OpeningBalance</NATIVEMETHOD>
            <NATIVEMETHOD>OpeningValue</NATIVEMETHOD>
            <NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>
            <NATIVEMETHOD>ClosingValue</NATIVEMETHOD>
            <NATIVEMETHOD>MasterId</NATIVEMETHOD>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
"""
```

**Key fields:**
- `Name` = SKU name (e.g., "Speedball Monalisa Gold Leaf Sealer Waterbased 2 Oz")
- `Parent` = Stock Group (e.g., "Sealers & Varnishes")
- `Category` = Stock Category = BRAND (e.g., "Speedball")
- `BaseUnits` = Unit of measurement (e.g., "pcs", "nos")
- `ClosingBalance` = Current stock quantity

**Note:** This may be a large response (5,000-15,000 items). If it times out or Tally becomes unresponsive, we may need to pull by stock category (brand) in separate requests.

### Extraction 3: Ledger List (for party classification)

This gives us all party names for the one-time classification exercise.

```python
LEDGER_LIST_REQUEST = """
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>LedgerList</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="LedgerList" ISINITIALIZE="Yes">
            <TYPE>Ledger</TYPE>
            <NATIVEMETHOD>Name</NATIVEMETHOD>
            <NATIVEMETHOD>Parent</NATIVEMETHOD>
            <NATIVEMETHOD>MasterId</NATIVEMETHOD>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
"""
```

**Why we need the Parent field:** Ledgers are organized under groups like "Sundry Debtors" (customers), "Sundry Creditors" (suppliers), etc. This gives us a first pass at classification — anything under Sundry Creditors is likely a supplier, anything under Sundry Debtors is likely a customer. But final classification is manual.

### Extraction 4: Inventory Vouchers (Transaction Data)

This is the big one — all inventory-affecting transactions for the financial year.

```python
def inventory_vouchers_request(from_date: str, to_date: str) -> str:
    """
    Request all inventory vouchers for a date range.
    
    Args:
        from_date: Start date in YYYYMMDD format (e.g., "20250401")
        to_date: End date in YYYYMMDD format (e.g., "20260331")
    
    Note: Dates are for financial year. Indian FY runs Apr 1 to Mar 31.
    Current FY: 20250401 to 20260331
    """
    return f"""
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Day Book</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <EXPLODEFLAG>Yes</EXPLODEFLAG>
        <SVFROMDATE>{from_date}</SVFROMDATE>
        <SVTODATE>{to_date}</SVTODATE>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
"""
```

**IMPORTANT CONSIDERATIONS:**

1. **This will be a VERY large response.** The entire Day Book for a year could be hundreds of thousands of vouchers. It may take minutes to respond or may time out.

2. **Batching strategy:** If the full year fails, break it into monthly requests:
   ```python
   # Pull month by month
   for month_start, month_end in monthly_ranges("20250401", "20260310"):
       response = client.send_request(
           inventory_vouchers_request(month_start, month_end),
           timeout=600  # 10 minutes per month
       )
       save_to_file(response, f"vouchers_{month_start}_{month_end}.xml")
   ```

3. **Alternative approach — use Stock Item Register per item:** Instead of the Day Book (which includes ALL vouchers), we can pull the Stock Item register which gives us only inventory-affecting transactions with inward/outward quantities. However, this requires one request per stock item, which is slow for thousands of SKUs.

4. **Best approach — custom collection for inventory entries:**
   ```python
   INVENTORY_ENTRIES_REQUEST = """
   <ENVELOPE>
     <HEADER>
       <VERSION>1</VERSION>
       <TALLYREQUEST>Export</TALLYREQUEST>
       <TYPE>Collection</TYPE>
       <ID>InventoryEntries</ID>
     </HEADER>
     <BODY>
       <DESC>
         <STATICVARIABLES>
           <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
           <SVFROMDATE>20250401</SVFROMDATE>
           <SVTODATE>20260331</SVTODATE>
         </STATICVARIABLES>
         <TDL>
           <TDLMESSAGE>
             <COLLECTION NAME="InventoryEntries" ISINITIALIZE="Yes">
               <TYPE>Voucher</TYPE>
               <NATIVEMETHOD>Date</NATIVEMETHOD>
               <NATIVEMETHOD>VoucherTypeName</NATIVEMETHOD>
               <NATIVEMETHOD>VoucherNumber</NATIVEMETHOD>
               <NATIVEMETHOD>PartyLedgerName</NATIVEMETHOD>
               <NATIVEMETHOD>InventoryEntries</NATIVEMETHOD>
               <NATIVEMETHOD>MasterId</NATIVEMETHOD>
               <NATIVEMETHOD>AlterId</NATIVEMETHOD>
               <FILTER>HasInventory</FILTER>
             </COLLECTION>
             <SYSTEM TYPE="Formulae" NAME="HasInventory">
               $IsInventoryEntry = Yes
             </SYSTEM>
           </TDLMESSAGE>
         </TDL>
       </DESC>
     </BODY>
   </ENVELOPE>
   """
   ```

**Note:** The exact XML request format may need adjustment based on testing. Tally's TDL query language has quirks. The test extraction script (below) is designed to try multiple approaches and see what works.

## The Test Extraction Script

This is the FIRST thing to run. It validates connectivity and data quality.

```python
# extraction/test_extraction.py

"""
First-run test script. Run this to validate:
1. Tally HTTP server is reachable
2. All four data extractions work
3. Data quality is as expected
4. Identify any parsing issues

Usage:
    python test_extraction.py

Output:
    Saves XML responses to data/sample_responses/
    Prints summary statistics
"""

import os
import sys
from datetime import datetime
from tally_client import TallyClient
from xml_requests import (
    STOCK_CATEGORIES_REQUEST,
    STOCK_ITEMS_REQUEST,
    LEDGER_LIST_REQUEST,
    inventory_vouchers_request
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'sample_responses')

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    client = TallyClient(host="localhost", port=9000)
    
    # Step 1: Test connection
    print("=" * 60)
    print("STEP 1: Testing connection to Tally...")
    print("=" * 60)
    if not client.test_connection():
        print("FAILED. Cannot proceed. Check that Tally is running with HTTP server enabled.")
        sys.exit(1)
    print("SUCCESS.\n")
    
    # Step 2: Pull stock categories
    print("=" * 60)
    print("STEP 2: Pulling stock categories (brands)...")
    print("=" * 60)
    try:
        raw = client.send_request_raw(STOCK_CATEGORIES_REQUEST)
        filepath = os.path.join(OUTPUT_DIR, "stock_categories.xml")
        with open(filepath, 'wb') as f:
            f.write(raw)
        print(f"Saved to {filepath} ({len(raw)} bytes)")
        # Parse and count
        root = client.send_request(STOCK_CATEGORIES_REQUEST)
        categories = root.findall('.//STOCKCATEGORY')
        print(f"Found {len(categories)} stock categories")
        for cat in categories[:10]:  # Show first 10
            name = cat.get('NAME', cat.findtext('NAME', 'unknown'))
            print(f"  - {name}")
        if len(categories) > 10:
            print(f"  ... and {len(categories) - 10} more")
    except Exception as e:
        print(f"FAILED: {e}")
    print()
    
    # Step 3: Pull stock items
    print("=" * 60)
    print("STEP 3: Pulling stock items (SKUs)...")
    print("=" * 60)
    try:
        raw = client.send_request_raw(STOCK_ITEMS_REQUEST, timeout=600)
        filepath = os.path.join(OUTPUT_DIR, "stock_items.xml")
        with open(filepath, 'wb') as f:
            f.write(raw)
        print(f"Saved to {filepath} ({len(raw)} bytes)")
        root = client.send_request(STOCK_ITEMS_REQUEST, timeout=600)
        items = root.findall('.//STOCKITEM')
        print(f"Found {len(items)} stock items")
        # Count by category
        cat_counts = {}
        for item in items:
            cat = item.findtext('CATEGORY', 'Uncategorized')
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        print("Stock items per category (brand):")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1])[:15]:
            print(f"  {cat}: {count} SKUs")
    except Exception as e:
        print(f"FAILED: {e}")
    print()
    
    # Step 4: Pull ledger list
    print("=" * 60)
    print("STEP 4: Pulling ledger list (for party classification)...")
    print("=" * 60)
    try:
        raw = client.send_request_raw(LEDGER_LIST_REQUEST)
        filepath = os.path.join(OUTPUT_DIR, "ledgers.xml")
        with open(filepath, 'wb') as f:
            f.write(raw)
        print(f"Saved to {filepath} ({len(raw)} bytes)")
        root = client.send_request(LEDGER_LIST_REQUEST)
        ledgers = root.findall('.//LEDGER')
        print(f"Found {len(ledgers)} ledgers")
        # Group by parent
        parent_counts = {}
        for ledger in ledgers:
            parent = ledger.findtext('PARENT', 'Unknown')
            parent_counts[parent] = parent_counts.get(parent, 0) + 1
        print("Ledgers by group:")
        for parent, count in sorted(parent_counts.items(), key=lambda x: -x[1]):
            print(f"  {parent}: {count}")
    except Exception as e:
        print(f"FAILED: {e}")
    print()
    
    # Step 5: Pull vouchers (try current month first as a test)
    print("=" * 60)
    print("STEP 5: Pulling inventory vouchers (current month test)...")
    print("=" * 60)
    today = datetime.now()
    month_start = today.replace(day=1).strftime("%Y%m%d")
    month_end = today.strftime("%Y%m%d")
    try:
        request = inventory_vouchers_request(month_start, month_end)
        raw = client.send_request_raw(request, timeout=600)
        filepath = os.path.join(OUTPUT_DIR, f"vouchers_{month_start}_{month_end}.xml")
        with open(filepath, 'wb') as f:
            f.write(raw)
        print(f"Saved to {filepath} ({len(raw)} bytes)")
        print(f"Date range: {month_start} to {month_end}")
        print()
        print("IMPORTANT: Open this file and examine the XML structure.")
        print("We need to identify:")
        print("  1. How voucher entries are structured")
        print("  2. Where party name appears")
        print("  3. Where stock item name and quantity appear")
        print("  4. Whether godown information is included")
        print("  5. Any unexpected voucher types")
    except Exception as e:
        print(f"FAILED: {e}")
    
    print()
    print("=" * 60)
    print("TEST EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"Check {OUTPUT_DIR} for saved XML files.")
    print("Send these files for analysis before proceeding to database setup.")

if __name__ == "__main__":
    main()
```

## Parsing XML Responses

After we receive and inspect the actual XML responses (which may differ from expectations), we build the parser. The general approach:

```python
# extraction/xml_parser.py

from lxml import etree
from typing import List, Dict, Any

def parse_stock_categories(xml_bytes: bytes) -> List[Dict[str, str]]:
    """Parse stock categories response into list of dicts."""
    root = etree.fromstring(xml_bytes)
    categories = []
    
    # The exact XPath depends on Tally's response format
    # This will need adjustment after seeing actual response
    for cat in root.iter('STOCKCATEGORY'):
        categories.append({
            'name': cat.get('NAME') or cat.findtext('NAME', ''),
            'parent': cat.findtext('PARENT', ''),
        })
    
    return categories

def parse_stock_items(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse stock items response into list of dicts."""
    root = etree.fromstring(xml_bytes)
    items = []
    
    for item in root.iter('STOCKITEM'):
        items.append({
            'name': item.get('NAME') or item.findtext('NAME', ''),
            'stock_group': item.findtext('PARENT', ''),
            'category': item.findtext('CATEGORY', ''),  # This is the BRAND
            'base_unit': item.findtext('BASEUNITS', ''),
            'closing_balance': item.findtext('CLOSINGBALANCE', '0'),
            'closing_value': item.findtext('CLOSINGVALUE', '0'),
        })
    
    return items

def parse_vouchers(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parse voucher/day book response into transaction records.
    
    IMPORTANT: The exact parsing logic depends heavily on the XML structure
    returned by Tally, which varies by report type and Tally version.
    This WILL need adjustment after inspecting actual responses.
    """
    root = etree.fromstring(xml_bytes)
    transactions = []
    
    for voucher in root.iter('VOUCHER'):
        date = voucher.get('DATE') or voucher.findtext('DATE', '')
        vch_type = voucher.findtext('VOUCHERTYPENAME', '')
        vch_number = voucher.findtext('VOUCHERNUMBER', '')
        party = voucher.findtext('PARTYLEDGERNAME', '')
        
        # Inventory entries are nested within the voucher
        for inv_entry in voucher.iter('INVENTORYENTRIES.LIST'):
            stock_item = inv_entry.findtext('STOCKITEMNAME', '')
            
            # Quantity might be in different formats
            # Tally often returns "10 pcs" or "-5 nos" 
            qty_str = inv_entry.findtext('ACTUALQTY', '0')
            
            # Billing quantities
            billed_qty = inv_entry.findtext('BILLEDQTY', '0')
            
            # Rate and amount
            rate = inv_entry.findtext('RATE', '0')
            amount = inv_entry.findtext('AMOUNT', '0')
            
            transactions.append({
                'date': date,
                'party': party,
                'voucher_type': vch_type,
                'voucher_number': vch_number,
                'stock_item': stock_item,
                'quantity': qty_str,      # Will need parsing — "10 pcs" → 10
                'billed_qty': billed_qty,
                'rate': rate,
                'amount': amount,
            })
    
    return transactions
```

## Quantity Parsing

Tally returns quantities with units attached (e.g., "45 pcs", "-12 nos"). We need to strip the unit and parse the number:

```python
import re

def parse_tally_quantity(qty_str: str) -> float:
    """
    Parse Tally quantity strings like '45 pcs', '-12 nos', '0.5 kg'.
    Returns the numeric value. Positive = inward, Negative = outward.
    """
    if not qty_str or qty_str.strip() == '':
        return 0.0
    
    # Remove everything that isn't a digit, minus sign, or decimal point
    match = re.match(r'^\s*([-]?\d+\.?\d*)', qty_str.strip())
    if match:
        return float(match.group(1))
    return 0.0
```

## What Can Go Wrong (and likely will)

1. **XML structure varies by Tally version and configuration.** The field names, nesting, and attributes may differ from examples found online. This is why the test extraction (Step 5 above) saves raw XML for inspection before we build parsers.

2. **Large responses may timeout.** The Day Book for a full year with inventory details could be enormous. Batch by month or by voucher type.

3. **TDL filter syntax may not work as expected.** The custom collection approach (Extraction 4 alternative) uses TDL's filter language which is poorly documented. If filters don't work, fall back to pulling the full Day Book and filtering in Python.

4. **Character encoding issues.** Tally may return non-UTF-8 characters. Use `response.content` (bytes) rather than `response.text` (string) and let lxml handle encoding.

5. **Stock item names with special characters.** Ampersands, quotes, etc. in item names may cause XML parsing issues. The lxml parser handles most of these, but watch for it.

## Next Steps

After running the test extraction:
1. Inspect the saved XML files
2. Adjust parsers to match actual response structure  
3. Verify stock category = brand mapping is correct
4. Count total SKUs and transactions to estimate database size
5. Extract unique party names for classification (document 04)
6. Proceed to database schema (document 03)
