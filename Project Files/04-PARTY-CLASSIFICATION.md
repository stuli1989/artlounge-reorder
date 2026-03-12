# 04 — Party Classification

## Overview

Party classification is the single most important manual step. Every party (ledger) in Tally that appears in inventory transactions must be classified into a channel. This classification drives the entire velocity calculation — if a wholesale customer is accidentally tagged as "online," it corrupts the demand signals.

This is done ONCE, manually, by someone who knows the business. It takes 30-60 minutes.

## The Classification Categories

| Channel | What it means | How to identify | Examples |
|---------|--------------|----------------|----------|
| `supplier` | International brand you import from | Appears in Purchase vouchers, foreign company names | Speedball Art Products LLC, Winsor & Newton |
| `wholesale` | Retail shops/distributors who buy from you | Appears in Sales/Sales-Tally vouchers, Indian business names | Hindustan Trading Company, A N Commtrade LLP, Mango Stationery Pvt. Ltd |
| `online` | E-commerce platform connector | Party name is the platform system name | MAGENTO2 |
| `store` | Your own retail store (Kala Ghoda) | Art Lounge branded names, store POS names | Art Lounge India, Counter Collection - QR |
| `internal` | Accounting entries for internal transfers | "Art Lounge India - Purchase" pattern | Art Lounge India - Purchase |
| `ignore` | System adjustments, not real demand | Physical stock adjustments, opening balance entries | Physical Stock |
| `unclassified` | New party, needs human review | Not yet tagged | (temporary state only) |

## Process

### Step 1: Extract all parties from Tally

The test extraction script (document 02) pulls the full ledger list. From that, we also scan the transaction data to find every unique party name that appears in inventory vouchers — some parties might exist as ledgers but never transact in inventory.

The output is a CSV like:

```csv
tally_name,tally_parent,transaction_count,channel
"Speedball Art Products, LLC","Sundry Creditors",5,
"Hindustan Trading Company","Sundry Debtors",28,
"MAGENTO2","Sundry Debtors",145,
"Art Lounge India","Sundry Debtors",12,
"Art Lounge India - Purchase","Sundry Creditors",8,
"Physical Stock","",3,
"A N Commtrade LLP","Sundry Debtors",15,
...
```

### Step 2: Apply automatic pre-classification

Before manual review, the system pre-fills obvious ones:

```python
def pre_classify_parties(parties: list) -> list:
    """Apply obvious classification rules. Human reviews everything after."""
    
    for party in parties:
        name = party['tally_name']
        parent = party['tally_parent']
        
        # Known patterns
        if name == 'MAGENTO2':
            party['channel'] = 'online'
            party['confidence'] = 'high'
        elif name == 'Physical Stock':
            party['channel'] = 'ignore'
            party['confidence'] = 'high'
        elif name == 'Art Lounge India - Purchase':
            party['channel'] = 'internal'
            party['confidence'] = 'high'
        elif 'Art Lounge India' in name or 'Counter Collection' in name:
            party['channel'] = 'store'
            party['confidence'] = 'high'
        elif parent == 'Sundry Creditors':
            # Creditors are usually suppliers
            party['channel'] = 'supplier'
            party['confidence'] = 'medium'
        elif parent == 'Sundry Debtors':
            # Debtors are usually customers (wholesale by default)
            party['channel'] = 'wholesale'
            party['confidence'] = 'medium'
        else:
            party['channel'] = 'unclassified'
            party['confidence'] = 'low'
    
    return parties
```

### Step 3: Manual review

You open the CSV, review every row, correct any wrong pre-classifications, and fill in unclassified ones. The key questions for each:

- **Is this a company you buy imported goods from?** → `supplier`
- **Is this a shop or distributor that buys from you?** → `wholesale`
- **Is this MAGENTO2 or another e-commerce platform name?** → `online`
- **Is this your own retail store or its POS system?** → `store`
- **Is this an internal accounting entity?** → `internal`
- **Is this a system/adjustment entry?** → `ignore`

### Step 4: Load into database

```python
import csv
import psycopg2

def load_party_classification(csv_path: str, db_conn):
    """Load classified parties from CSV into database."""
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        
        cursor = db_conn.cursor()
        for row in reader:
            cursor.execute("""
                INSERT INTO parties (tally_name, tally_parent, channel, classified_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (tally_name) DO UPDATE
                SET channel = EXCLUDED.channel,
                    classified_at = NOW(),
                    updated_at = NOW()
            """, (row['tally_name'], row['tally_parent'], row['channel']))
        
        db_conn.commit()
```

## Handling New Parties

After the initial classification, new parties may appear in future nightly syncs. The sync job handles this:

```python
def handle_new_parties(db_conn, transaction_parties: set):
    """Check for parties in transactions that aren't in the parties table."""
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT tally_name FROM parties")
    known_parties = {row[0] for row in cursor.fetchall()}
    
    new_parties = transaction_parties - known_parties
    
    if new_parties:
        for party_name in new_parties:
            cursor.execute("""
                INSERT INTO parties (tally_name, channel)
                VALUES (%s, 'unclassified')
                ON CONFLICT (tally_name) DO NOTHING
            """, (party_name,))
        
        db_conn.commit()
        
        # Log alert
        print(f"WARNING: {len(new_parties)} new unclassified parties found:")
        for p in new_parties:
            print(f"  - {p}")
        print("Please classify these parties before the next computation run.")
        
    return new_parties
```

The dashboard should show a warning banner when unclassified parties exist: "3 new parties need classification. Velocity calculations may be incomplete."

## Impact of Misclassification

| Mistake | Impact | Severity |
|---------|--------|----------|
| Wholesale tagged as online | Wholesale velocity too low, online too high. Reorder triggers delayed. | **High** |
| Online tagged as wholesale | Wholesale velocity inflated. May trigger early reorders. | Medium |
| Supplier tagged as wholesale | Their purchase returns treated as sales. Velocity corrupted. | **High** |
| Store tagged as wholesale | Wholesale velocity slightly inflated by store transfers. | Low |
| Internal tagged as anything else | Double-counting of quantities. | **High** |

The most critical classifications are: MAGENTO2 = online, all "Art Lounge India*" variants, and suppliers. Everything else defaulting to wholesale is safe because most parties ARE wholesale customers.

## Known Parties from Sample Data

From the Speedball Sealer SKU analysis, these parties were identified:

| Party | Classification | Confidence |
|-------|---------------|-----------|
| Speedball Art Products, LLC | `supplier` | Certain |
| Hindustan Trading Company | `wholesale` | Certain |
| A N Commtrade LLP | `wholesale` | Certain |
| Artorium the Colour World | `wholesale` | Certain |
| Himalaya Stationary Mart | `wholesale` | Certain |
| Mango Stationery Pvt. Ltd | `wholesale` | Certain |
| Saremisons | `wholesale` | Certain |
| Vardhman Trading Company | `wholesale` | Certain |
| Ansh | `wholesale` | Certain |
| Shruti G. Dev | `wholesale` | Certain |
| Monica kharkar | `wholesale` | Certain |
| MAGENTO2 | `online` | Certain |
| Art Lounge India | `store` | Certain |
| Counter Collection - QR | `store` | Certain |
| Art Lounge India - Purchase | `internal` | Certain |
| Physical Stock | `ignore` | Certain |

This is only from ONE SKU. The full extraction will reveal many more parties.
