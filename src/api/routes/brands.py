"""Brand overview API endpoints."""
from fastapi import APIRouter, Query
from api.database import get_db

router = APIRouter(tags=["brands"])


@router.get("/brands")
def list_brands(search: str = Query(None)):
    """List all brand metrics, sorted by urgency."""
    with get_db() as conn:
        with conn.cursor() as cur:
            sql = "SELECT * FROM brand_metrics"
            params = []
            if search:
                sql += " WHERE category_name ILIKE %s"
                params.append(f"%{search}%")
            sql += " ORDER BY critical_skus DESC, warning_skus DESC, avg_days_to_stockout ASC NULLS LAST"
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/brands/summary")
def brands_summary():
    """Aggregate summary stats for dashboard header cards."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total_brands,
                    SUM(CASE WHEN critical_skus > 0 THEN 1 ELSE 0 END) AS brands_with_critical,
                    SUM(CASE WHEN warning_skus > 0 THEN 1 ELSE 0 END) AS brands_with_warning,
                    SUM(out_of_stock_skus) AS total_skus_out_of_stock,
                    SUM(COALESCE(dead_stock_skus, 0)) AS total_dead_stock_skus
                FROM brand_metrics
            """)
            row = cur.fetchone()
    return dict(row)
