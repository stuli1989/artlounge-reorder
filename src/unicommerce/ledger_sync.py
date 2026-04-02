# src/unicommerce/ledger_sync.py
"""
Nightly sync orchestrator — pulls transaction ledger via Export Job API,
parses, loads into transactions table, runs pipeline.

Usage:
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --backfill
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --dry-run
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --reset
"""
import argparse
import logging
import os
import glob
import time
import threading
from datetime import datetime, timedelta, date

import psycopg2.extras

from unicommerce.client import UnicommerceClient
from unicommerce.ledger_parser import parse_ledger_csv, parse_ledger_file, classify_channel
from unicommerce.catalog import pull_all_skus, load_catalog
from engine.pipeline import run_computation_pipeline
from extraction.data_loader import get_db_connection
from config.settings import UC_FACILITIES_FALLBACK

logger = logging.getLogger(__name__)

# In-memory sync progress — read by the status endpoint
_sync_progress = {
    "running": False,
    "step": None,
    "error": None,
}
_sync_lock = threading.Lock()


def _retry(fn, *args, max_attempts=3, backoff_base=5, **kwargs):
    """Retry a callable with exponential backoff.

    Attempts up to max_attempts times with delays of 5s, 15s, 45s (backoff_base * 3^i).
    Logs each retry attempt. Re-raises on final failure.
    """
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < max_attempts - 1:
                delay = backoff_base * (3 ** attempt)
                logger.warning("Retry %d/%d for %s after error: %s (waiting %ds)",
                               attempt + 1, max_attempts, fn.__name__, e, delay)
                time.sleep(delay)
            else:
                logger.error("All %d attempts failed for %s: %s", max_attempts, fn.__name__, e)
    raise last_exc


def get_sync_progress() -> dict:
    """Read current sync progress (thread-safe)."""
    with _sync_lock:
        return dict(_sync_progress)


def _set_progress(step: str | None, running: bool = True, error: str | None = None):
    """Update sync progress (called from run_nightly_sync)."""
    with _sync_lock:
        _sync_progress["running"] = running
        _sync_progress["step"] = step
        _sync_progress["error"] = error


OVERLAP_DAYS = 3
BACKFILL_WINDOW_DAYS = 90  # Export Job API max is 92


def _fetch_channel_rules(db_conn):
    """Load active channel rules from DB, sorted by priority DESC."""
    with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT rule_type, match_value, facility_filter, channel, priority
            FROM channel_rules WHERE is_active = TRUE
            ORDER BY priority DESC
        """)
        return cur.fetchall()


def _load_transactions(db_conn, parsed_rows, rules):
    """Classify channels and upsert parsed rows into transactions table."""
    if not parsed_rows:
        return 0

    for row in parsed_rows:
        row["channel"] = classify_channel(row, rules)

    # Skip KG PICKLIST — KG demand comes from Shipping Package API (kg_demand table)
    # KG PICKLIST is incomplete (misses counter sales like CUSTOM_SHOP dispatches)
    parsed_rows = [
        row for row in parsed_rows
        if not (row.get("facility") == "PPETPLKALAGHODA" and row.get("entity") == "PICKLIST")
    ]

    sql = """
        INSERT INTO transactions
            (item_code, txn_date, entity, entity_type, entity_code,
             txn_type, units, stock_change, facility, channel, is_demand, sale_order_code)
        VALUES
            (%(sku_code)s, %(txn_date)s, %(entity)s, %(entity_type)s, %(entity_code)s,
             %(txn_type)s, %(units)s, %(stock_change)s, %(facility)s, %(channel)s,
             %(is_demand)s, %(sale_order_code)s)
        ON CONFLICT (entity_code, item_code, txn_type, txn_date, units, facility)
        DO NOTHING
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, parsed_rows, page_size=1000)
    db_conn.commit()
    return len(parsed_rows)


def pull_and_store_snapshots(client, db_conn):
    """Pull UC inventory snapshot and store in inventory_snapshots table."""

    # Get all active SKU codes
    with db_conn.cursor() as cur:
        cur.execute("SELECT sku_code FROM stock_items WHERE is_active = TRUE AND sku_code IS NOT NULL")
        sku_codes = [row[0] for row in cur.fetchall()]

    if not sku_codes:
        logger.warning("No active SKUs for snapshot pull")
        return 0

    snapshots = client.pull_inventory_snapshots(sku_codes)
    today = date.today()

    rows = [
        {
            "item_code": sku,
            "snapshot_date": today,
            "inventory": data["inventory"],
            "inventory_blocked": data["blocked"],
            "bad_inventory": data["bad"],
        }
        for sku, data in snapshots.items()
    ]

    sql = """
        INSERT INTO inventory_snapshots
            (item_code, snapshot_date, inventory, inventory_blocked, bad_inventory)
        VALUES (%(item_code)s, %(snapshot_date)s, %(inventory)s, %(inventory_blocked)s, %(bad_inventory)s)
        ON CONFLICT (item_code, snapshot_date) DO UPDATE SET
            inventory = EXCLUDED.inventory,
            inventory_blocked = EXCLUDED.inventory_blocked,
            bad_inventory = EXCLUDED.bad_inventory
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows, page_size=1000)
    db_conn.commit()

    logger.info("Stored %d inventory snapshots for %s", len(rows), today)
    return len(rows)


def pull_and_store_kg_demand(client, db_conn):
    """Pull KG dispatched shipping packages and store as demand in kg_demand table."""
    from datetime import timezone

    KG_FACILITY = "PPETPLKALAGHODA"

    # UC channel mapping
    CHANNEL_MAP = {
        "CUSTOM": "wholesale",
        "CUSTOM_SHOP": "store",
        "MAGENTO2": "online",
        "FLIPKART": "online",
        "AMAZON_EASYSHIP_V2": "online",
        "AMAZON_IN_API": "online",
    }

    data = client._request(
        "POST",
        "/services/rest/v1/oms/shippingPackage/search",
        json={"statuses": ["DISPATCHED"], "updatedSinceInMinutes": 525600},
        facility=KG_FACILITY,
        timeout=180,
    )
    packages = data.get("elements", [])

    rows = []
    for pkg in packages:
        pkg_code = pkg.get("code", "")
        dispatch_ms = pkg.get("dispatched", 0)
        if not dispatch_ms or not pkg_code:
            continue

        dispatch_date = datetime.fromtimestamp(dispatch_ms / 1000, tz=timezone.utc).date()
        uc_channel = pkg.get("channel", "")
        channel = CHANNEL_MAP.get(uc_channel, "unclassified")

        items = pkg.get("items", {})
        if isinstance(items, dict):
            for item_code, item_data in items.items():
                sku = item_data.get("itemSku", item_code) if isinstance(item_data, dict) else item_code
                qty = item_data.get("quantity", 1) if isinstance(item_data, dict) else 1
                if not sku or qty <= 0:
                    continue
                rows.append({
                    "item_code": sku,
                    "txn_date": dispatch_date,
                    "quantity": float(qty),
                    "channel": channel,
                    "shipping_package_code": pkg_code,
                })

    if rows:
        sql = """
            INSERT INTO kg_demand
                (item_code, txn_date, quantity, channel, shipping_package_code)
            VALUES (%(item_code)s, %(txn_date)s, %(quantity)s, %(channel)s, %(shipping_package_code)s)
            ON CONFLICT (item_code, shipping_package_code) DO NOTHING
        """
        with db_conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, rows, page_size=1000)
        db_conn.commit()

    logger.info("Stored %d KG demand rows from %d packages", len(rows), len(packages))
    return len(rows)


def pull_ledger_for_facility(client, facility, start_date, end_date):
    """Pull transaction ledger CSV for one facility via Export Job API.

    Returns parsed rows list, or empty list on failure.
    """
    try:
        job_code = client.create_export_job(facility, start_date, end_date)
        status, file_path = client.poll_export_job(job_code, facility=facility, timeout=300)

        if status != "COMPLETE" or not file_path:
            logger.error("Export job %s for %s: status=%s", job_code, facility, status)
            return []

        csv_text = client.download_export_csv(file_path)
        rows = parse_ledger_csv(csv_text)
        logger.info("Facility %s: %d rows parsed", facility, len(rows))
        return rows

    except Exception as e:
        logger.error("Failed to pull ledger for %s: %s", facility, e)
        return []


def _send_sync_email(total_loaded, facilities_ok, total_facilities, db_conn=None, error=None):
    """Send email notification on sync completion via Resend API."""
    import json
    import urllib.request
    import urllib.error

    resend_key = os.environ.get("RESEND_API_KEY", "")
    notify_email = os.environ.get("NOTIFY_EMAIL", "")
    if not resend_key or not notify_email:
        logger.info("Email skipped: RESEND_API_KEY or NOTIFY_EMAIL not configured")
        return

    is_success = not error
    status_label = "SUCCESS" if is_success else "FAILED"
    status_emoji = "\u2705" if is_success else "\u274c"
    status_color = "#16a34a" if is_success else "#dc2626"
    subject = f"{status_emoji} Art Lounge Sync {status_label} — {date.today()}"

    # Gather DB metrics if connection available
    metrics = {}
    if db_conn and is_success:
        try:
            with db_conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM sku_metrics")
                metrics["total_skus"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM sku_metrics WHERE reorder_status IN ('urgent', 'lost_sales')")
                metrics["critical_skus"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM sku_metrics WHERE reorder_status = 'reorder'")
                metrics["warning_skus"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM sku_metrics WHERE reorder_status = 'healthy'")
                metrics["healthy_skus"] = cur.fetchone()[0]
                cur.execute("SELECT MAX(snapshot_date) FROM inventory_snapshots")
                metrics["latest_snapshot"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM brand_metrics")
                metrics["total_brands"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM transactions")
                metrics["total_transactions"] = cur.fetchone()[0]
        except Exception:
            db_conn.rollback()

    # Build HTML email
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a;">
      <div style="background: {status_color}; color: white; padding: 20px 24px; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 20px; font-weight: 600;">Nightly Sync {status_label}</h1>
        <p style="margin: 6px 0 0; opacity: 0.9; font-size: 14px;">{date.today().strftime('%A, %d %B %Y')}</p>
      </div>

      <div style="border: 1px solid #e5e5e5; border-top: none; border-radius: 0 0 8px 8px; padding: 24px;">
    """

    if error:
        html += f"""
        <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 14px 16px; margin-bottom: 20px;">
          <p style="margin: 0; font-size: 14px; color: #991b1b; font-weight: 600;">Error Details</p>
          <p style="margin: 6px 0 0; font-size: 13px; color: #dc2626; font-family: monospace; word-break: break-all;">{str(error)[:300]}</p>
        </div>
        """

    # Sync summary section
    html += f"""
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
          <tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; color: #666;">Ledger Rows Loaded</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; font-weight: 600; text-align: right;">{total_loaded:,}</td>
          </tr>
          <tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; color: #666;">Facilities Synced</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; font-weight: 600; text-align: right;">{facilities_ok} / {total_facilities}</td>
          </tr>
    """

    if metrics.get("latest_snapshot"):
        html += f"""
          <tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; color: #666;">Snapshot Date</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; font-weight: 600; text-align: right;">{metrics['latest_snapshot']}</td>
          </tr>
          <tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; color: #666;">Total Transactions</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; font-weight: 600; text-align: right;">{metrics.get('total_transactions', 0):,}</td>
          </tr>
        """

    html += "</table>"

    # Inventory health cards (only on success with metrics)
    if metrics.get("total_skus"):
        critical = metrics.get("critical_skus", 0)
        warning = metrics.get("warning_skus", 0)
        healthy = metrics.get("healthy_skus", 0)
        total = metrics["total_skus"]

        html += f"""
        <p style="font-size: 13px; color: #666; margin: 0 0 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Inventory Health</p>
        <div style="display: flex; gap: 8px; margin-bottom: 20px;">
          <div style="flex: 1; background: #fef2f2; border-radius: 6px; padding: 12px; text-align: center;">
            <div style="font-size: 22px; font-weight: 700; color: #dc2626;">{critical:,}</div>
            <div style="font-size: 11px; color: #991b1b; margin-top: 2px;">Critical</div>
          </div>
          <div style="flex: 1; background: #fffbeb; border-radius: 6px; padding: 12px; text-align: center;">
            <div style="font-size: 22px; font-weight: 700; color: #d97706;">{warning:,}</div>
            <div style="font-size: 11px; color: #92400e; margin-top: 2px;">Warning</div>
          </div>
          <div style="flex: 1; background: #f0fdf4; border-radius: 6px; padding: 12px; text-align: center;">
            <div style="font-size: 22px; font-weight: 700; color: #16a34a;">{healthy:,}</div>
            <div style="font-size: 11px; color: #166534; margin-top: 2px;">Healthy</div>
          </div>
          <div style="flex: 1; background: #f8fafc; border-radius: 6px; padding: 12px; text-align: center;">
            <div style="font-size: 22px; font-weight: 700; color: #475569;">{total:,}</div>
            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Total SKUs</div>
          </div>
        </div>
        """

    # Footer
    html += f"""
        <div style="border-top: 1px solid #f0f0f0; padding-top: 16px; margin-top: 8px;">
          <a href="https://reorder.artlounge.in" style="display: inline-block; background: #18181b; color: white; text-decoration: none; padding: 8px 20px; border-radius: 6px; font-size: 13px; font-weight: 500;">Open Dashboard</a>
          <span style="margin-left: 12px; font-size: 12px; color: #999;">Brands: {metrics.get('total_brands', '—')} &middot; Next sync: 3:30 AM IST</span>
        </div>
      </div>

      <p style="text-align: center; font-size: 11px; color: #aaa; margin-top: 16px;">
        Art Lounge Stock Intelligence &middot; Sent from sync@artlounge.in
      </p>
    </div>
    """

    payload = json.dumps({
        "from": "Art Lounge Sync <sync@artlounge.in>",
        "to": [notify_email],
        "subject": subject,
        "html": html,
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json",
            "User-Agent": "ArtLounge-Sync/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            logger.info("Sync email sent to %s (status %s)", notify_email, resp.status)
    except Exception as e:
        logger.warning("Failed to send sync email via Resend: %s", e)


def run_validation_check(client, db_conn, sample_size=50):
    """Compare ledger-derived stock vs UC snapshot for a sample of SKUs.

    Flags any diff where inventoryBlocked=0 as a potential data problem.
    Diffs where inventoryBlocked>0 are expected (orders committed but not yet picked).
    """
    import random

    print("Step 7: Running validation check...")

    # Get a sample of active SKUs from our metrics
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT item_code, current_stock
            FROM sku_metrics
            WHERE current_stock IS NOT NULL AND current_stock != 0
            ORDER BY RANDOM() LIMIT %s
        """, (sample_size,))
        sample = {row[0]: float(row[1]) for row in cur.fetchall()}

    if not sample:
        print("  No SKUs to validate")
        return

    sku_list = list(sample.keys())

    # Pull snapshot for these SKUs
    snapshot = {}
    for facility in client.facilities:
        try:
            data = client._request("POST", "/services/rest/v1/inventory/inventorySnapshot/get",
                json={"itemTypeSKUs": sku_list}, facility=facility, timeout=120)
            for snap in data.get("inventorySnapshots", []):
                sku = snap.get("itemTypeSKU")
                if not sku:
                    continue
                if sku not in snapshot:
                    snapshot[sku] = {"inv": 0, "blocked": 0, "putaway": 0}
                snapshot[sku]["inv"] += snap.get("inventory", 0) or 0
                snapshot[sku]["blocked"] += snap.get("inventoryBlocked", 0) or 0
                snapshot[sku]["putaway"] += snap.get("putawayPending", 0) or 0
        except Exception as e:
            logger.warning("Validation snapshot failed for %s: %s", facility, e)

    # Compare
    matches = 0
    expected_diffs = 0  # diffs where blocked > 0 (expected)
    unexpected_diffs = []  # diffs where blocked = 0 (potential problem)

    for sku in sku_list:
        our_stock = sample[sku]
        snap = snapshot.get(sku)
        if not snap:
            continue

        uc_inventory = snap["inv"]
        blocked = snap["blocked"]
        diff = our_stock - uc_inventory

        if abs(diff) < 0.01:
            matches += 1
        elif blocked > 0:
            expected_diffs += 1
        else:
            unexpected_diffs.append({
                "sku": sku, "our_stock": our_stock,
                "uc_inventory": uc_inventory, "diff": diff,
            })

    validated = len([s for s in sku_list if s in snapshot])
    print(f"  Validated {validated} SKUs: {matches} exact matches, "
          f"{expected_diffs} expected diffs (blocked>0), "
          f"{len(unexpected_diffs)} UNEXPECTED diffs (blocked=0)")

    if unexpected_diffs:
        print("  WARNING: Unexpected diffs (inventoryBlocked=0):")
        for d in unexpected_diffs[:10]:
            print(f"    {d['sku']}: our={d['our_stock']:.0f} uc={d['uc_inventory']:.0f} diff={d['diff']:+.0f}")
        logger.warning("Validation found %d unexpected diffs (blocked=0): %s",
                       len(unexpected_diffs),
                       [(d["sku"], d["diff"]) for d in unexpected_diffs[:10]])

    return {
        "validated": validated, "matches": matches,
        "expected_diffs": expected_diffs,
        "unexpected_diffs": len(unexpected_diffs),
    }


def run_nightly_sync(db_conn, days_back=OVERLAP_DAYS, dry_run=False):
    """Main nightly sync: pull ledger, load transactions, run pipeline."""
    try:
        _set_progress("Starting sync...")
        print("=== NIGHTLY LEDGER SYNC ===")

        client = UnicommerceClient()
        client.authenticate()
        client.discover_facilities()

        # 1. Pull catalog (with retry)
        _set_progress("Pulling catalog...")
        print("Step 1: Pulling catalog...")
        try:
            skus = _retry(pull_all_skus, client)
            if skus and not dry_run:
                _retry(load_catalog, db_conn, skus)
                print(f"  Catalog: {len(skus)} SKUs loaded")
        except Exception as e:
            db_conn.rollback()
            print(f"  Catalog pull failed: {e} (continuing)")

        # 2. Pull ledger per facility (with retry per facility)
        _set_progress("Pulling transaction ledger...")
        print(f"Step 2: Pulling ledger (last {days_back} days)...")
        end_dt = datetime.now().replace(hour=23, minute=59, second=59)
        start_dt = (end_dt - timedelta(days=days_back)).replace(hour=0, minute=0, second=0)

        rules = _fetch_channel_rules(db_conn)
        total_loaded = 0
        facilities_ok = 0

        for facility in client.facilities:
            rows = _retry(pull_ledger_for_facility, client, facility, start_dt, end_dt)
            if rows:
                if not dry_run:
                    loaded = _load_transactions(db_conn, rows, rules)
                    total_loaded += loaded
                else:
                    total_loaded += len(rows)
                facilities_ok += 1
                print(f"  {facility}: {len(rows)} rows")
            else:
                print(f"  {facility}: FAILED or empty")

        print(f"  Total: {total_loaded} rows loaded, {facilities_ok}/{len(client.facilities)} facilities OK")

        # 3. Pull KG shipping packages (demand) (with retry)
        if not dry_run:
            _set_progress("Pulling KG shipping packages...")
            print("Step 3: Pulling KG shipping packages...")
            try:
                kg_count = _retry(pull_and_store_kg_demand, client, db_conn)
                print(f"  KG demand: {kg_count} rows")
            except Exception as e:
                db_conn.rollback()
                print(f"  KG demand pull failed: {e} (continuing)")

        # 4. Pull inventory snapshots (with retry)
        if not dry_run:
            _set_progress("Pulling inventory snapshots...")
            print("Step 4: Pulling inventory snapshots...")
            try:
                snap_count = _retry(pull_and_store_snapshots, client, db_conn)
                print(f"  Snapshots: {snap_count} SKUs")
            except Exception as e:
                db_conn.rollback()
                print(f"  Snapshot pull failed: {e} (continuing)")

        # 5. Run pipeline
        if not dry_run:
            _set_progress("Running computation pipeline...")
            print("Step 5: Running pipeline...")
            run_computation_pipeline(db_conn)
            print("  Pipeline complete")

        # 6. Log sync
        if not dry_run:
            _set_progress("Logging sync results...")
            with db_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sync_log (source, sync_started, sync_completed, status,
                                          ledger_rows_loaded, facilities_synced)
                    VALUES ('ledger', NOW() - INTERVAL '1 minute', NOW(), 'completed', %s, %s)
                """, (total_loaded, facilities_ok))
            db_conn.commit()

        # 7. Validation check (compare ledger stock vs UC snapshot for sample)
        if not dry_run:
            try:
                run_validation_check(client, db_conn)
            except Exception as e:
                db_conn.rollback()
                logger.warning("Validation check failed: %s", e)

        # 8. Email notification
        try:
            _send_sync_email(total_loaded, facilities_ok, len(client.facilities), db_conn=db_conn)
        except Exception as e:
            logger.warning("Email notification failed: %s", e)

        _set_progress(None, running=False)
        print("=== SYNC COMPLETE ===")

    except Exception as e:
        _set_progress(None, running=False, error=str(e))
        # Log failure to sync_log
        try:
            with db_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sync_log (source, sync_started, sync_completed, status, notes)
                    VALUES ('ledger', NOW() - INTERVAL '1 minute', NOW(), 'failed', %s)
                """, (str(e)[:500],))
            db_conn.commit()
        except Exception:
            db_conn.rollback()
        # Send failure email
        try:
            _send_sync_email(0, 0, 0, db_conn=db_conn, error=str(e))
        except Exception:
            pass
        raise


def run_backfill(db_conn, from_csv_dir=None):
    """Historical backfill — either from API (92-day windows) or from CSV directory."""
    print("=== HISTORICAL BACKFILL ===")

    # Always pull catalog first (needed for pipeline to find stock_items)
    print("Step 0: Pulling catalog...")
    try:
        client = UnicommerceClient()
        client.authenticate()
        client.discover_facilities()
        skus = _retry(pull_all_skus, client)
        if skus:
            _retry(load_catalog, db_conn, skus)
            print(f"  Catalog: {len(skus)} SKUs loaded")

            # Seed suppliers from brands
            with db_conn.cursor() as cur:
                cur.execute("SELECT name FROM stock_categories ORDER BY name")
                brands = [row[0] for row in cur.fetchall()]
            for brand in brands:
                with db_conn.cursor() as cur:
                    cur.execute("""INSERT INTO suppliers (name, lead_time_default, typical_order_months, notes)
                                  VALUES (%s, 90, 3, 'Auto-seeded') ON CONFLICT (name) DO NOTHING""", (brand,))
            db_conn.commit()
            print(f"  Suppliers: {len(brands)} seeded")
    except Exception as e:
        db_conn.rollback()
        print(f"  Catalog pull failed: {e} (continuing)")

    rules = _fetch_channel_rules(db_conn)

    if from_csv_dir:
        # Load from local CSV files
        files = sorted(glob.glob(os.path.join(from_csv_dir, "**", "*.csv"), recursive=True))
        print(f"Loading {len(files)} CSV files from {from_csv_dir}")
        total = 0
        for f in files:
            rows = parse_ledger_file(f)
            loaded = _load_transactions(db_conn, rows, rules)
            total += loaded
            print(f"  {os.path.basename(f)}: {loaded} rows")
        print(f"Total loaded: {total}")
    else:
        # Pull from API in 90-day windows
        client = UnicommerceClient()
        client.authenticate()
        client.discover_facilities()

        # Jun 1 2025 to today
        start = datetime(2025, 6, 1)
        end = datetime.now()
        total = 0

        window_start = start
        while window_start < end:
            window_end = min(window_start + timedelta(days=BACKFILL_WINDOW_DAYS), end)
            start_dt = window_start.replace(hour=0, minute=0, second=0)
            end_dt = window_end.replace(hour=23, minute=59, second=59)

            print(f"\nWindow: {start_dt.date()} to {end_dt.date()}")
            for facility in client.facilities:
                rows = _retry(pull_ledger_for_facility, client, facility, start_dt, end_dt)
                if rows:
                    loaded = _load_transactions(db_conn, rows, rules)
                    total += loaded
                    print(f"  {facility}: {loaded} rows")

            window_start = window_end + timedelta(days=1)

        print(f"\nTotal loaded: {total}")

    # Pull KG demand and snapshots (with retry)
    print("\nPulling KG shipping packages...")
    try:
        kg_count = _retry(pull_and_store_kg_demand, client, db_conn)
        print(f"  KG demand: {kg_count} rows")
    except Exception as e:
        db_conn.rollback()
        print(f"  KG demand pull failed: {e}")

    print("Pulling inventory snapshots...")
    try:
        snap_count = _retry(pull_and_store_snapshots, client, db_conn)
        print(f"  Snapshots: {snap_count} SKUs")
    except Exception as e:
        db_conn.rollback()
        print(f"  Snapshot pull failed: {e}")

    # Run full pipeline
    print("\nRunning full pipeline...")
    run_computation_pipeline(db_conn)
    print("=== BACKFILL COMPLETE ===")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="Ledger-based sync")
    parser.add_argument("--backfill", action="store_true", help="Run historical backfill from API")
    parser.add_argument("--backfill-csv", type=str, help="Backfill from local CSV directory")
    parser.add_argument("--dry-run", action="store_true", help="Pull data but don't write to DB")
    parser.add_argument("--days", type=int, default=OVERLAP_DAYS, help="Days to look back (default 3)")
    parser.add_argument("--reset", action="store_true", help="Wipe all tables and run fresh backfill")
    args = parser.parse_args()

    db_conn = get_db_connection()
    try:
        if args.reset:
            print("=== FULL RESET ===")
            with db_conn.cursor() as cur:
                for table in ['daily_stock_positions', 'sku_metrics', 'brand_metrics', 'drift_log',
                               'sync_log', 'kg_demand', 'inventory_snapshots', 'transactions',
                               'stock_items', 'stock_categories', 'suppliers']:
                    cur.execute(f"TRUNCATE {table} CASCADE")
                    print(f"  Truncated {table}")
            db_conn.commit()
            print("All tables cleared.")
            run_backfill(db_conn)
        elif args.backfill:
            run_backfill(db_conn)
        elif args.backfill_csv:
            run_backfill(db_conn, from_csv_dir=args.backfill_csv)
        else:
            run_nightly_sync(db_conn, days_back=args.days, dry_run=args.dry_run)
    finally:
        db_conn.close()


if __name__ == "__main__":
    main()
