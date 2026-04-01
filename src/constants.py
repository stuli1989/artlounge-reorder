"""
Centralized field name constants for SKU data.

Unicommerce provides:
  - skuCode  -> stored as `item_code` (the SKU identifier, e.g. "0102004")
  - name     -> stored as `display_name` (human-readable, e.g. "WN PWC 5ML ALIZ CRIMSON")

All code should use these constants instead of hardcoding column/field names.
"""


class SKU_FIELDS:
    """Column and API field names for SKU identification."""
    ITEM_CODE = "item_code"
    DISPLAY_NAME = "display_name"
    CATEGORY = "category_name"
