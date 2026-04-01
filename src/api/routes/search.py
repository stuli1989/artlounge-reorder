"""Universal search endpoint — searches brands and SKUs in one call.

IMPORTANT: sku_metrics does NOT have display_name or is_active columns.
These live on stock_items, so all SKU queries JOIN stock_items si ON si.item_code = sm.item_code.
This matches the pattern in skus.py list_skus().
"""
from decimal import Decimal
from fastapi import APIRouter, Query, HTTPException, Depends
from api.database import get_db
from api.auth import get_current_user

router = APIRouter()


def _escape_ilike(s: str) -> str:
    """Escape PostgreSQL ILIKE special characters."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _rank_expr(field: str) -> str:
    """SQL CASE expression for ranking: exact=0, starts-with=1, contains=2."""
    return (
        f"CASE WHEN LOWER({field}) = LOWER(%(q)s) THEN 0 "
        f"WHEN LOWER({field}) LIKE LOWER(%(q_prefix)s) THEN 1 "
        f"ELSE 2 END"
    )


def _to_float(val):
    """Convert Decimal to float for JSON serialization consistency."""
    if isinstance(val, Decimal):
        return float(val)
    return val


def _clean_row(row):
    """Convert a RealDictRow to a plain dict with floats instead of Decimals."""
    return {k: _to_float(v) for k, v in dict(row).items()}


# Common SQL fragments for SKU search (JOIN stock_items for display_name and is_active)
_SKU_SELECT = (
    "SELECT sm.item_code, si.display_name, sm.category_name, "
    "  sm.reorder_status, sm.current_stock "
    "FROM sku_metrics sm "
    "LEFT JOIN stock_items si ON si.item_code = sm.item_code"
)

_SKU_MATCH = (
    "(sm.item_code ILIKE %(pattern)s OR COALESCE(si.display_name, '') ILIKE %(pattern)s)"
)

_SKU_ACTIVE = "COALESCE(si.is_active, TRUE) = TRUE"


@router.get("/search")
def universal_search(
    q: str = Query(None),
    scope: str = Query(None),
    user: dict = Depends(get_current_user),
):
    # --- Validate ---
    if not q or len(q.strip()) < 2:
        raise HTTPException(400, "Query must be at least 2 characters")
    q = q.strip()
    if len(q) > 100:
        raise HTTPException(400, "Query must be at most 100 characters")

    escaped = _escape_ilike(q)
    pattern = f"%{escaped}%"
    prefix_pattern = f"{escaped}%"

    with get_db() as conn:
        with conn.cursor() as cur:
            params = {"q": q, "q_prefix": prefix_pattern, "pattern": pattern}

            # --- Brands ---
            brand_rank = _rank_expr("category_name")
            cur.execute(
                f"SELECT category_name, total_skus, urgent_skus "
                f"FROM brand_metrics "
                f"WHERE category_name ILIKE %(pattern)s "
                f"ORDER BY {brand_rank}, category_name "
                f"LIMIT 5",
                params,
            )
            brands = [_clean_row(r) for r in cur.fetchall()]
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM brand_metrics "
                "WHERE category_name ILIKE %(pattern)s",
                params,
            )
            brand_count = cur.fetchone()["cnt"]

            # --- Scoped SKUs (if scope provided) ---
            scoped_skus = []
            scoped_sku_count = 0
            global_limit = 10
            if scope:
                sku_rank = _rank_expr("sm.item_code")
                cur.execute(
                    f"{_SKU_SELECT} "
                    f"WHERE sm.category_name = %(scope)s "
                    f"  AND {_SKU_MATCH} "
                    f"  AND {_SKU_ACTIVE} "
                    f"ORDER BY {sku_rank}, sm.item_code "
                    f"LIMIT 10",
                    {**params, "scope": scope},
                )
                scoped_skus = [_clean_row(r) for r in cur.fetchall()]
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sku_metrics sm "
                    f"LEFT JOIN stock_items si ON si.item_code = sm.item_code "
                    f"WHERE sm.category_name = %(scope)s "
                    f"  AND {_SKU_MATCH} "
                    f"  AND {_SKU_ACTIVE}",
                    {**params, "scope": scope},
                )
                scoped_sku_count = cur.fetchone()["cnt"]
                global_limit = 5  # Reduce global when scoped results shown

            # --- Global SKUs ---
            sku_rank = _rank_expr("sm.item_code")
            exclude_scope = ""
            if scope:
                exclude_scope = "AND sm.category_name != %(scope)s "
            cur.execute(
                f"{_SKU_SELECT} "
                f"WHERE {_SKU_MATCH} "
                f"  AND {_SKU_ACTIVE} "
                f"  {exclude_scope}"
                f"ORDER BY {sku_rank}, sm.item_code "
                f"LIMIT %(glimit)s",
                {**params, "scope": scope, "glimit": global_limit},
            )
            skus = [_clean_row(r) for r in cur.fetchall()]
            cur.execute(
                f"SELECT COUNT(*) AS cnt FROM sku_metrics sm "
                f"LEFT JOIN stock_items si ON si.item_code = sm.item_code "
                f"WHERE {_SKU_MATCH} "
                f"  AND {_SKU_ACTIVE} "
                f"  {exclude_scope}",
                {**params, "scope": scope},
            )
            sku_count = cur.fetchone()["cnt"]

            # --- Prefix group ---
            # Check if q matches as an item_code prefix (item codes like 0102004)
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM sku_metrics sm "
                "LEFT JOIN stock_items si ON si.item_code = sm.item_code "
                "WHERE sm.item_code ILIKE %(prefix_like)s "
                "  AND " + _SKU_ACTIVE,
                {"prefix_like": prefix_pattern},
            )
            prefix_count = cur.fetchone()["cnt"]

            prefix_group = None
            if prefix_count >= 2:
                cur.execute(
                    "SELECT DISTINCT sm.category_name "
                    "FROM sku_metrics sm "
                    "LEFT JOIN stock_items si ON si.item_code = sm.item_code "
                    "WHERE sm.item_code ILIKE %(prefix_like)s "
                    "  AND " + _SKU_ACTIVE + " "
                    "ORDER BY sm.category_name",
                    {"prefix_like": prefix_pattern},
                )
                prefix_brands = [r["category_name"] for r in cur.fetchall()]
                prefix_group = {"prefix": q, "total": prefix_count, "brands": prefix_brands}

    result = {
        "brands": brands,
        "brand_count": brand_count,
        "skus": skus,
        "sku_count": sku_count,
        "prefix_group": prefix_group,
    }
    if scope:
        result["scoped_skus"] = scoped_skus
        result["scoped_sku_count"] = scoped_sku_count
    return result


@router.get("/search/prefix")
def prefix_search(
    q: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """Return all active SKUs whose item_code starts with the given prefix."""
    if not q or len(q.strip()) < 2:
        raise HTTPException(400, "Query must be at least 2 characters")
    q = q.strip()
    if len(q) > 50:
        raise HTTPException(400, "Query must be at most 50 characters")

    escaped = _escape_ilike(q)
    prefix_like = f"{escaped}%"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"{_SKU_SELECT} "
                f"WHERE sm.item_code ILIKE %(prefix_like)s "
                f"  AND {_SKU_ACTIVE} "
                f"ORDER BY sm.item_code",
                {"prefix_like": prefix_like},
            )
            skus = [_clean_row(r) for r in cur.fetchall()]

    brands = sorted({s["category_name"] for s in skus if s.get("category_name")})
    return {
        "prefix": q,
        "total": len(skus),
        "brands": brands,
        "skus": skus,
    }
