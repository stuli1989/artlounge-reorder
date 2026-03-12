# T02: Tally HTTP Client + XML Request Templates

## Prerequisites
- T01 completed (project structure exists)

## Objective
Create the TallyClient class for communicating with Tally Prime's HTTP XML API, and all XML request templates needed for data extraction.

## Context
Tally Prime exposes an HTTP server (default port 9000) that accepts XML POST requests and returns XML responses. All extraction uses this interface.

## Files to Create

### 1. `extraction/tally_client.py`

HTTP client class with these methods:
- `__init__(self, host="localhost", port=9000)` — stores base URL
- `send_request(self, xml_request: str, timeout=300) -> etree._Element` — POST XML, return parsed lxml Element
- `send_request_raw(self, xml_request: str, timeout=300) -> bytes` — POST XML, return raw bytes (for saving to file)
- `test_connection(self) -> bool` — send "List of Companies" request, print company names, return True/False

Key implementation details:
- Use `requests.post()` with `Content-Type: application/xml`
- Encode request as UTF-8: `xml_request.encode('utf-8')`
- Parse response with `etree.fromstring(response.content)` (use .content not .text for encoding safety)
- Raise `ConnectionError` if Tally unreachable
- Raise `ValueError` if response is not valid XML
- Test connection XML:
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

### 2. `extraction/xml_requests.py`

Four XML request templates:

**A. STOCK_CATEGORIES_REQUEST** — Get all stock categories (= brands)
```xml
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
```

**B. STOCK_ITEMS_REQUEST** — Get all stock items (SKUs) with category (brand) and group
Fields: Name, Parent (stock group), Category (brand), BaseUnits, OpeningBalance, OpeningValue, ClosingBalance, ClosingValue, MasterId

**C. LEDGER_LIST_REQUEST** — Get all ledgers (parties) with parent group
Fields: Name, Parent (e.g. "Sundry Debtors", "Sundry Creditors"), MasterId

**D. `inventory_vouchers_request(from_date: str, to_date: str) -> str`** — Function that returns XML for inventory vouchers in a date range
- Dates in YYYYMMDD format (e.g., "20250401")
- Uses Day Book report with EXPLODEFLAG=Yes
- This is the biggest response — may need monthly batching
```xml
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
```

Note: All XML templates use TDL custom collections (except vouchers which use built-in Day Book report). The exact element structure in responses may vary — parsers (T05) will handle this.

## Acceptance Criteria
- [ ] `TallyClient` handles connection errors gracefully with clear error messages
- [ ] `test_connection()` prints company names found
- [ ] All 4 XML request templates are defined as module-level constants/functions
- [ ] `inventory_vouchers_request()` accepts date strings and returns formatted XML
- [ ] Timeout defaults to 300s (5min), configurable per request
