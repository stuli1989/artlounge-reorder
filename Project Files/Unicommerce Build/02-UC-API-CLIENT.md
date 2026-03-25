# 02 — Unicommerce API Client

## Overview

`src/unicommerce/client.py` — single class that handles authentication, requests, pagination, retry, and facility discovery.

## OAuth2 Authentication

```python
class UnicommerceClient:
    def __init__(self, tenant, username, password):
        self.base_url = f"https://{tenant}.unicommerce.com"
        self.username = username
        self.password = password
        self.access_token = None
        self.token_expiry = None
        self.facilities = None  # discovered dynamically
```

**Token flow:**
1. `GET /oauth/token?grant_type=password&client_id=my-trusted-client&username=...&password=...`
2. Response: `{access_token, refresh_token, expires_in}` (expires_in ~43200s = 12hr)
3. Store token + expiry time. Auto-refresh when within 5 minutes of expiry.
4. Refresh token valid 30 days (for long-running syncs).

**Token refresh logic:**
```python
def _ensure_token(self):
    if self.access_token and time.time() < self.token_expiry - TOKEN_EXPIRY_BUFFER:
        return
    self._authenticate()
```

## Request Helper

```python
def _request(self, method, path, json=None, facility=None, retries=3):
    self._ensure_token()
    headers = {
        "Authorization": f"Bearer {self.access_token}",
        "Content-Type": "application/json"
    }
    if facility:
        headers["Facility"] = facility

    for attempt in range(retries):
        response = requests.request(method, f"{self.base_url}{path}", json=json, headers=headers)
        if response.status_code == 401:
            self._authenticate()  # token expired mid-request
            continue
        if response.status_code == 429:
            time.sleep(2 ** attempt)  # exponential backoff
            continue
        response.raise_for_status()
        return response.json()
    raise Exception(f"UC API failed after {retries} retries: {path}")
```

## Facility Discovery

Dynamic — not hardcoded to current 3 facilities.

```python
def discover_facilities(self):
    """Returns list of active facility codes."""
    # Note: /facility/search is the correct path (not /inventory/facility/search)
    # May need to handle 404 and fall back to known facilities
    self.facilities = [...]
    return self.facilities
```

**Fallback:** If facility search endpoint isn't available, use env var `UC_FACILITIES=ppetpl,ALIBHIWANDI,PPETPLKALAGHODA`.

## Pagination Helper

For endpoints that return paginated results (sale orders, shipping packages):

```python
def _paginate(self, path, body, facility=None, page_size=100):
    """Yields all elements across pages."""
    page = 1
    while True:
        body_with_page = {**body, "pageNumber": page, "pageSize": page_size}
        data = self._request("POST", path, json=body_with_page, facility=facility)
        elements = data.get("elements", [])
        if not elements:
            break
        yield from elements
        if len(elements) < page_size:
            break
        page += 1
```

## URL Case-Sensitivity Gotchas

Unicommerce endpoints are case-sensitive. Known paths:

| Operation | Correct Path |
|---|---|
| Sale order search | `/services/rest/v1/oms/saleOrder/search` (camelCase) |
| Sale order get | `/services/rest/v1/oms/saleorder/get` (lowercase!) |
| Shipping package search | `/services/rest/v1/oms/shippingPackage/search` |
| Return search | `/services/rest/v1/oms/return/search` |
| Return get | `/services/rest/v1/oms/return/get` (field: `reversePickupCode`) |
| PO list | `/services/rest/v1/purchase/purchaseOrder/getPurchaseOrders` |
| GRN list | `/services/rest/v1/purchase/inflowReceipt/getInflowReceipts` |
| GRN detail | `/services/rest/v1/purchase/inflowReceipt/getInflowReceipt` |
| Inventory snapshot | `/services/rest/v1/inventory/inventorySnapshot/get` |
| SKU search | `/services/rest/v1/product/itemType/search` |
| SKU detail | `/services/rest/v1/catalog/itemType/get` |

## Rate Limiting

No documented rate limits from UC. Build in:
- Exponential backoff on 429 responses
- 0.5s delay between paginated calls (gentle throttle)
- Log all API call durations for monitoring

## Error Handling

UC responses follow standard envelope:
```json
{
  "successful": true/false,
  "message": "...",
  "errors": [{"code": ..., "description": "...", "message": "..."}],
  "warnings": [...]
}
```

Client should:
1. Check `successful` field first
2. Log `errors` array with full detail
3. Raise specific exceptions for known error codes (e.g., `INVALID_TIME_INTERVAL` for return date caps)
4. Return parsed data payload (varies per endpoint)
