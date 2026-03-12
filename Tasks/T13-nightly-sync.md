# T13: Nightly Sync Script

## Prerequisites
- T06 (master data loader)
- T08 (transaction loader)
- T12 (computation pipeline)

## Objective
Build the main nightly sync script that orchestrates: Tally connection → master data pull → transaction pull → new party detection → computation pipeline → logging.

## Files to Create

### 1. `sync/nightly_sync.py`

CLI script with arguments:
- `--full` — Force full re-sync (pull entire FY)
- `--dry-run` — Pull data but don't load or compute

```python
"""
Nightly sync job: Pull data from Tally -> Load into PostgreSQL -> Compute metrics.

Usage:
    python sync/nightly_sync.py              # Normal nightly run
    python sync/nightly_sync.py --full       # Force full re-sync
    python sync/nightly_sync.py --dry-run    # Pull data but don't load
"""
```

#### Execution flow:
1. Parse CLI args
2. Initialize TallyClient and DB connection
3. Create sync_log entry (status='running')
4. Test Tally connection — abort if fails
5. Sync stock categories (always full refresh)
6. Sync stock items (always full refresh)
7. Determine transaction date range:
   - If `--full`: FY start (20250401) to today
   - Otherwise: 7 days before last successful sync end date, to today
8. Sync transactions (monthly batching via `sync_transactions()`)
9. Detect new unclassified parties — print warning if found
10. Run computation pipeline (unless `--dry-run`)
11. Update sync_log (status='completed', counts)
12. Handle exceptions: update sync_log with status='failed', error_message

#### Date range for delta sync:
```python
def get_sync_date_range(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT MAX(txn_to_date) FROM sync_log WHERE status = 'completed'
    """)
    last_sync_end = cursor.fetchone()[0]

    if last_sync_end is None:
        return ("20250401", date.today().strftime("%Y%m%d"))

    # 7-day overlap for backdated entries
    overlap_start = last_sync_end - timedelta(days=7)
    return (overlap_start.strftime("%Y%m%d"), date.today().strftime("%Y%m%d"))
```

### 2. `sync/sync_helpers.py`

#### `create_sync_log(db_conn) -> int`
- INSERT into sync_log with sync_started=NOW(), status='running'
- Return the sync log ID

#### `update_sync_log(db_conn, sync_id, **kwargs)`
- UPDATE sync_log SET status, sync_completed, counts, error_message
- If status='completed', set sync_completed=NOW()

#### `check_new_parties(db_conn) -> list[str]`
- Find parties in transactions table not in parties table
- Insert as 'unclassified'
- Return list of new party names

## Why 7-day overlap?
Vouchers can be backdated — someone might enter a July 15 sale on July 18. The overlap ensures we catch backdated entries. The UNIQUE constraint on transactions prevents duplicates.

## Error handling strategy:
| Error | Recovery |
|-------|----------|
| Tally not reachable | Log error, abort. Dashboard shows stale data. Send failure email. |
| Single month fails | Skip that month, continue. Log partial sync. |
| DB connection fails | Abort entire sync, log error. Send failure email. |
| New unclassified parties | Sync completes but dashboard shows warning. Note in email. |

### 3. `sync/email_notifier.py`

Send email notifications after sync completes or fails.

```python
"""
Email notifications for sync status.
Uses SMTP (Gmail app password or any SMTP provider).
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL
)

def send_sync_notification(status, summary_dict, error_message=None):
    """
    Send email after sync completes or fails.

    Args:
        status: 'completed' or 'failed'
        summary_dict: {categories_synced, items_synced, transactions_synced, new_parties_found}
        error_message: Error details if status='failed'
    """
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL]):
        print("Email not configured, skipping notification")
        return

    subject = f"[Art Lounge Sync] {'✓ Success' if status == 'completed' else '✗ FAILED'}"

    if status == 'completed':
        body = f"""Nightly sync completed successfully.

Categories synced: {summary_dict.get('categories_synced', 0)}
Items synced: {summary_dict.get('items_synced', 0)}
Transactions synced: {summary_dict.get('transactions_synced', 0)}
New parties found: {summary_dict.get('new_parties_found', 0)}
"""
        if summary_dict.get('new_parties_found', 0) > 0:
            body += "\n⚠ New unclassified parties detected — classify them in the dashboard."
    else:
        body = f"""Nightly sync FAILED.

Error: {error_message}

Dashboard data may be stale. Check the sync agent on the AWS box.
"""

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = NOTIFY_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"Notification email sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"Failed to send email notification: {e}")
```

#### Integration in `nightly_sync.py`:
After step 11 (update sync_log), call `send_sync_notification('completed', counts_dict)`.
In the exception handler (step 12), call `send_sync_notification('failed', {}, str(error))`.

## Acceptance Criteria
- [ ] `--full` flag forces full FY re-sync
- [ ] `--dry-run` pulls data without loading or computing
- [ ] Delta sync uses 7-day overlap from last successful sync
- [ ] First run (no prior sync) pulls entire FY
- [ ] Sync log tracks start/end times, counts, and errors
- [ ] New unclassified parties detected and logged
- [ ] Individual month failures don't crash the full sync
- [ ] Timestamps printed with each step for debugging
- [ ] Email sent on sync success with summary counts
- [ ] Email sent on sync failure with error details
- [ ] Email warns about new unclassified parties
- [ ] Email gracefully skipped if SMTP not configured
