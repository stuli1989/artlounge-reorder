# 03 — Data Ingestion from Unicommerce

## Overview

Six ingestion modules, each pulling a specific data type. All designed for incremental sync (only changes since last sync).

## 1. Catalog / SKU Master (`unicommerce/catalog.py`)

**Endpoint:** `POST /services/rest/v1/product/itemType/search`
**Scope:** Tenant-level (no facility header)
**Frequency:** Nightly (incremental via `updatedSinceInHour`)

**Full pull (first run):**
```python
def pull_all_skus(client):
    """Pull all ~23,362 SKUs. Used for first sync."""
    return client._request("POST", "/services/rest/v1/product/itemType/search", json={})
    # Returns all items (no pagination needed based on testing — returned 23,362 in one call)
```

**Incremental pull (nightly):**
```python
def pull_updated_skus(client, hours_since_last_sync=25):
    """Pull SKUs updated since last sync. Add 1hr buffer."""
    return client._request("POST", "/services/rest/v1/product/itemType/search",
        json={"updatedSinceInHour": hours_since_last_sync})
```

**Fields to extract per SKU:**
- `skuCode` → primary key
- `name` → display name
- `categoryCode` → brand/category (maps to stock_categories)
- `brand` → brand name (free text)
- `costPrice`, `maxRetailPrice` → pricing
- `ean`, `upc`, `scanIdentifier` → barcodes/part numbers
- `enabled` → is_active flag
- `hsnCode` → tax classification
- `weight`, `length`, `width`, `height` → physical attributes

**Maps to DB tables:** `stock_items`, `stock_categories`

---

## 2. Inventory Snapshots (`unicommerce/inventory.py`)

**Endpoint:** `POST /services/rest/v1/inventory/inventorySnapshot/get`
**Scope:** Facility-level (requires `Facility` header)
**Frequency:** Nightly (always full snapshot — no incremental)

```python
def pull_inventory_snapshot(client):
    """Pull inventory for ALL SKUs across ALL facilities.
    Use conservative chunking (1,000 SKUs) to avoid payload/WAF failures.
    23,362 SKUs → ~24 calls per facility."""
    all_skus = get_all_sku_codes()  # from DB
    results = {}
    for facility in client.facilities:
        for chunk in chunks(all_skus, 1000):
            data = client._request("POST",
                "/services/rest/v1/inventory/inventorySnapshot/get",
                json={"itemTypeSKUs": chunk},
                facility=facility)
            for snap in data.get("inventorySnapshots", []):
                sku = snap["itemTypeSKU"]
                if sku not in results:
                    results[sku] = {"inventory": 0, "blocked": 0, "putaway": 0,
                                    "openSale": 0, "openPurchase": 0, "bad": 0}
                results[sku]["inventory"] += snap.get("inventory", 0)
                results[sku]["blocked"] += snap.get("inventoryBlocked", 0)
                results[sku]["putaway"] += snap.get("putawayPending", 0)
                results[sku]["openSale"] += snap.get("openSale", 0)
                results[sku]["openPurchase"] += snap.get("openPurchase", 0)
                results[sku]["bad"] += snap.get("badInventory", 0)
    return results
```

**Available stock formula (F1):**
```
available = inventory - inventoryBlocked + putawayPending
```

**Store per-facility breakdown** in a `facility_inventory` table for drill-down. Aggregate for computations.

**Maps to DB tables:** `daily_inventory_snapshots` (new), `stock_items.current_stock`

---

## 3. Dispatched Shipments (`unicommerce/orders.py`)

**Endpoint:** `POST /services/rest/v1/oms/shippingPackage/search`
**Scope:** Facility-level
**Frequency:** Nightly (incremental via `updatedSinceInMinutes`)

```python
def pull_dispatched_since(client, minutes_since=1500):
    """Pull shipping packages dispatched/updated since last sync.
    Default 25 hours (1500 min) to catch anything missed."""
    all_packages = []
    for facility in client.facilities:
        packages = list(client._paginate(
            "/services/rest/v1/oms/shippingPackage/search",
            body={"statuses": ["DISPATCHED"], "updatedSinceInMinutes": minutes_since},
            facility=facility))
        for pkg in packages:
            pkg["_facility"] = facility  # tag with source facility
        all_packages.extend(packages)
    return all_packages
```

**Fields to extract per shipping package:**
- `code` → package ID (dedup key)
- `saleOrderCode` → linked sale order
- `channel` → MAGENTO2, CUSTOM, FLIPKART, etc.
- `dispatched` → timestamp (epoch ms → date)
- `items` → dict of {sku: {itemSku, itemName, quantity}}
- `customer` → customer name
- `invoiceCode`, `invoiceDate` → for revenue
- `collectableAmount` → order value

**Channel mapping:**
```python
CHANNEL_MAP = {
    "MAGENTO2": "online",
    "FLIPKART": "online",
    "AMAZON_EASYSHIP_V2": "online",
    "AMAZON_IN_API": "online",
    "CUSTOM": "wholesale",
    "CUSTOM_SHOP": "store",
}
```

**Maps to DB tables:** `transactions` (outward, channel-tagged)

---

## 4. Returns (`unicommerce/returns.py`)

**Endpoint:** `POST /services/rest/v1/oms/return/search` + `/get`
**Scope:** Facility-level
**Frequency:** Nightly (incremental via `updatedFrom`/`updatedTo`)
**Constraint:** 30-day max window per search call

```python
def pull_returns_since(client, since_date):
    """Pull returns (CIR + RTO) since a given date.
    Loops in 30-day windows if needed."""
    all_returns = []
    for return_type in ["CIR", "RTO"]:
        for facility in client.facilities:
            for window_start, window_end in date_windows(since_date, today, max_days=30):
                codes = client._request("POST",
                    "/services/rest/v1/oms/return/search",
                    json={"returnType": return_type,
                          "updatedFrom": window_start,
                          "updatedTo": window_end},
                    facility=facility)
                for ret in codes.get("returnOrders", []):
                    detail = client._request("POST",
                        "/services/rest/v1/oms/return/get",
                        json={"reversePickupCode": ret["code"]},
                        facility=facility)
                    detail["_return_type"] = return_type
                    detail["_facility"] = facility
                    all_returns.append(detail)
    return all_returns
```

**Fields to extract per return:**
- `reversePickupCode` → return ID
- `returnType` → CIR or RTO
- `returnSaleOrderItems[]` → SKU, quantity (inferred), saleOrderCode, channel
- `returnSaleOrderValue.returnCreatedDate` → date
- `returnSaleOrderValue.returnInvoiceCode` → credit note

**For incremental sync:** Track `last_return_sync_at` in sync_log. Pull returns **updated** since that timestamp (not created date). 30-day window looping handles the API cap transparently.

**Maps to DB tables:** `transactions` (inward, return_type tagged), `returns` (new detail table)

---

## 5. Purchase Orders + GRNs (`unicommerce/inbound.py`)

**PO List:** `POST /services/rest/v1/purchase/purchaseOrder/getPurchaseOrders`
**GRN List:** `POST /services/rest/v1/purchase/inflowReceipt/getInflowReceipts`
**GRN Detail:** `POST /services/rest/v1/purchase/inflowReceipt/getInflowReceipt`
**Scope:** Facility-level
**Frequency:** Nightly (incremental)

```python
def pull_grns_since(client, since_date):
    """Pull GRN details changed since last sync (bounded + paginated)."""
    all_grns = []
    for facility in client.facilities:
        for window_start, window_end in date_windows(since_date, today, max_days=30):
            body = build_grn_search_body(window_start, window_end)
            # build_grn_search_body should include tenant-supported date filters
            # (e.g. updatedFrom/updatedTo or updatedSinceInMinutes).
            for code in client.iter_grn_codes(body=body, facility=facility):
                detail = client._request("POST",
                    "/services/rest/v1/purchase/inflowReceipt/getInflowReceipt",
                    json={"inflowReceiptCode": code},
                    facility=facility)
                grn = detail.get("inflowReceipt", {})
                if parse_date(grn.get("created")) >= since_date:
                    all_grns.append(grn)
    return all_grns
```

Never call `getInflowReceipts` with an empty `{}` body in nightly syncs; it becomes an unbounded full-history fetch as data volume grows.

**Fields to extract per GRN:**
- `code` → GRN ID
- `created` → receipt date (used for lead time calc)
- `purchaseOrder.code`, `purchaseOrder.created` → PO linkage + PO date
- `purchaseOrder.vendorCode`, `purchaseOrder.vendorName` → supplier
- `inflowReceiptItems[]` → SKU, quantity, unitPrice, rejectedQuantity

**Lead time computation:**
```
lead_time = grn.created - grn.purchaseOrder.created  (per PO)
```

**Maps to DB tables:** `transactions` (inward, supplier channel), `purchase_orders` (new), `grn_receipts` (new)

---

## 6. Sale Order Details (on-demand)

**Endpoint:** `POST /services/rest/v1/oms/saleorder/get` (lowercase!)
**Scope:** Tenant-level
**Frequency:** On-demand only (not part of nightly sync)

Used for:
- Getting `sellingPrice` per item for ABC revenue calculation
- Investigating specific orders

The nightly sync gets revenue data from shipping packages (`collectableAmount`) and/or sale order search. Full order detail is fetched only when needed.

---

## Data Flow Summary

```
Nightly Sync:
  1. catalog.pull_updated_skus()     → stock_items, stock_categories
  2. inventory.pull_snapshot()        → daily_inventory_snapshots
  3. orders.pull_dispatched_since()   → transactions (outward)
  4. returns.pull_returns_since()     → transactions (inward/return)
  5. inbound.pull_grns_since()        → transactions (inward/supplier)
  6. pipeline.run_computation()       → sku_metrics, brand_metrics, daily_stock_positions
```
