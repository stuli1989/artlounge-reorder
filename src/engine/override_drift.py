"""Post-sync drift detection for manual overrides."""
import json
from datetime import datetime

from engine.effective_values import OVERRIDE_FIELD_TO_COLUMN

DRIFT_THRESHOLD_PCT = 20  # Flag as stale if computed value drifts >20%


def process_override_drift(db_conn) -> dict:
    """
    Check all active value overrides for drift against freshly computed sku_metrics.

    Called after run_computation_pipeline() in nightly sync.
    Returns summary dict with counts.
    """
    now = datetime.now()
    overrides_checked = 0
    newly_stale = 0
    auto_expired = 0

    with db_conn.cursor() as cur:
        # 1. Auto-expire overrides past their expiry date
        cur.execute("""
            UPDATE overrides
            SET is_active = FALSE, deactivated_at = NOW(),
                deactivated_reason = 'Auto-expired'
            WHERE is_active = TRUE AND expires_at IS NOT NULL AND expires_at < NOW()
            RETURNING id
        """)
        expired_rows = cur.fetchall()
        auto_expired = len(expired_rows)

        for row in expired_rows:
            cur.execute("""
                INSERT INTO override_audit_log (override_id, action, performed_by, note)
                VALUES (%s, 'auto_expired', 'system', 'Override expired')
            """, (row["id"],))

        # 2. Fetch all active value overrides (not note-only)
        cur.execute("""
            SELECT o.id, o.stock_item_name, o.field_name,
                   o.override_value, o.computed_value_at_creation,
                   o.is_stale
            FROM overrides o
            WHERE o.is_active = TRUE AND o.field_name != 'note'
        """)
        overrides = cur.fetchall()

        # Batch-fetch all sku_metrics for override items (eliminates N+1)
        override_item_names = list({ovr["stock_item_name"] for ovr in overrides})
        metrics_lookup = {}
        if override_item_names:
            cur.execute(
                "SELECT stock_item_name, current_stock, total_velocity, wholesale_velocity, online_velocity "
                "FROM sku_metrics WHERE stock_item_name = ANY(%s)",
                (override_item_names,),
            )
            for row in cur.fetchall():
                metrics_lookup[row["stock_item_name"]] = dict(row)

        for ovr in overrides:
            col = OVERRIDE_FIELD_TO_COLUMN.get(ovr["field_name"])
            if not col:
                # store_velocity isn't a direct column in sku_metrics; skip drift for it
                continue

            overrides_checked += 1

            sm_row = metrics_lookup.get(ovr["stock_item_name"])
            if not sm_row:
                continue

            computed_now = float(sm_row[col]) if sm_row[col] is not None else 0.0

            # Calculate drift
            creation_val = float(ovr["computed_value_at_creation"]) if ovr["computed_value_at_creation"] is not None else 0.0
            if creation_val != 0:
                drift = abs(computed_now - creation_val) / abs(creation_val) * 100
            elif computed_now != 0:
                drift = 100.0  # Was zero, now non-zero
            else:
                drift = 0.0

            drift = round(drift, 1)
            was_stale = ovr["is_stale"]

            # Update latest computed value and drift
            if drift > DRIFT_THRESHOLD_PCT and not was_stale:
                cur.execute("""
                    UPDATE overrides
                    SET computed_value_latest = %s, drift_pct = %s,
                        is_stale = TRUE, stale_since = %s
                    WHERE id = %s
                """, (computed_now, drift, now, ovr["id"]))

                cur.execute("""
                    INSERT INTO override_audit_log
                        (override_id, action, old_values, new_values, performed_by, note)
                    VALUES (%s, 'flagged_stale', %s, %s, 'system', %s)
                """, (
                    ovr["id"],
                    json.dumps({"computed_value_at_creation": creation_val}),
                    json.dumps({"computed_value_latest": computed_now, "drift_pct": drift}),
                    f"Drift {drift}% exceeds {DRIFT_THRESHOLD_PCT}% threshold",
                ))
                newly_stale += 1
            else:
                # Just update the latest value
                cur.execute("""
                    UPDATE overrides
                    SET computed_value_latest = %s, drift_pct = %s
                    WHERE id = %s
                """, (computed_now, drift, ovr["id"]))

    db_conn.commit()

    return {
        "overrides_checked": overrides_checked,
        "newly_stale": newly_stale,
        "auto_expired": auto_expired,
    }
