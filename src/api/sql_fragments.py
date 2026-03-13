"""Shared SQL fragments used across multiple API routes."""

# Pre-aggregated override subquery — consolidates 6 LEFT JOINs into 1.
# Used by skus.py (full detail) and po.py (PO builder).
# skus.py selects additional columns (stale, note) from this subquery;
# po.py selects a subset. Both JOIN on ovr.stock_item_name.
OVERRIDE_AGG_SUBQUERY = """(
    SELECT stock_item_name,
           MAX(CASE WHEN field_name='current_stock' THEN override_value END) AS stock_override_value,
           MAX(CASE WHEN field_name='current_stock' THEN note END) AS stock_override_note,
           MAX(CASE WHEN field_name='current_stock' THEN is_stale END) AS stock_override_stale,
           MAX(CASE WHEN field_name='current_stock' THEN hold_from_po END) AS stock_hold_from_po,
           MAX(CASE WHEN field_name='total_velocity' THEN override_value END) AS total_vel_override_value,
           MAX(CASE WHEN field_name='total_velocity' THEN is_stale END) AS total_vel_override_stale,
           MAX(CASE WHEN field_name='total_velocity' THEN hold_from_po END) AS total_vel_hold,
           MAX(CASE WHEN field_name='wholesale_velocity' THEN override_value END) AS wholesale_vel_override_value,
           MAX(CASE WHEN field_name='wholesale_velocity' THEN hold_from_po END) AS wholesale_vel_hold,
           MAX(CASE WHEN field_name='online_velocity' THEN override_value END) AS online_vel_override_value,
           MAX(CASE WHEN field_name='online_velocity' THEN hold_from_po END) AS online_vel_hold,
           MAX(CASE WHEN field_name='store_velocity' THEN override_value END) AS store_vel_override_value,
           MAX(CASE WHEN field_name='store_velocity' THEN hold_from_po END) AS store_vel_hold,
           MAX(CASE WHEN field_name='note' THEN note END) AS override_note,
           MAX(CASE WHEN field_name='note' THEN is_stale END) AS note_override_stale
    FROM overrides WHERE is_active = TRUE
    GROUP BY stock_item_name
)"""
