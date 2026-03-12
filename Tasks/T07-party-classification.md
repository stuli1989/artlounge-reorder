# T07: Party Classification System

## Prerequisites
- T06 completed (master data loader exists, parties loaded into database)

## Objective
Build tools for the one-time party classification workflow: export parties to CSV with pre-classification, then import classified CSV back into the database.

## File to Create

### `extraction/party_classifier.py`

#### 1. `pre_classify_parties(parties: list[dict]) -> list[dict]`
Apply automatic rules to pre-fill obvious classifications:

```python
def pre_classify_parties(parties):
    for party in parties:
        name = party['tally_name']
        parent = party.get('tally_parent', '')

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
            party['channel'] = 'supplier'
            party['confidence'] = 'medium'
        elif parent == 'Sundry Debtors':
            party['channel'] = 'wholesale'
            party['confidence'] = 'medium'
        else:
            party['channel'] = 'unclassified'
            party['confidence'] = 'low'

    return parties
```

#### 2. `export_parties_csv(db_conn, csv_path: str) -> int`
- Query all parties from database
- Apply pre-classification rules
- Write to CSV with columns: `tally_name, tally_parent, channel, confidence`
- Sort by confidence (low first, so unclassified are at top)
- Return count of parties exported
- Default path: `data/party_classification.csv`

#### 3. `import_classified_csv(db_conn, csv_path: str) -> dict`
- Read the CSV (after human has reviewed and corrected classifications)
- Update `parties` table: SET channel, classified_at=NOW()
- Return `{'updated': count, 'still_unclassified': count}`
- Validate channel values against allowed list before updating

#### 4. `detect_new_parties(db_conn) -> list[str]`
- Find party names that appear in `transactions` table but not in `parties` table
- Insert them into `parties` as 'unclassified'
- Return list of new party names found

#### 5. `get_unclassified_count(db_conn) -> int`
- Return count of parties where channel = 'unclassified'

## Channel Definitions (for reference in CSV header/comments)
| Channel | Meaning | Examples |
|---------|---------|----------|
| supplier | International brand you import from | Speedball Art Products LLC |
| wholesale | Shops/distributors that buy from you | Hindustan Trading Company |
| online | E-commerce platform | MAGENTO2 |
| store | Own retail locations | Art Lounge India |
| internal | Accounting entries for internal transfers | Art Lounge India - Purchase |
| ignore | System adjustments | Physical Stock |
| unclassified | Needs human review | (temporary) |

## Impact of Misclassification
- Wholesale tagged as online → wholesale velocity too low, delayed reorder triggers (HIGH impact)
- Supplier tagged as wholesale → purchase returns treated as sales, velocity corrupted (HIGH impact)
- Internal tagged as anything else → double-counting (HIGH impact)

## Acceptance Criteria
- [ ] Pre-classification applies known rules (MAGENTO2, Physical Stock, Art Lounge India patterns)
- [ ] CSV export includes confidence column for human reviewer
- [ ] CSV import validates channel values before updating
- [ ] `detect_new_parties()` finds transaction parties not yet in parties table
- [ ] Import uses `ON CONFLICT DO UPDATE` to update existing party classifications
- [ ] Unclassified parties at top of CSV for easy review
