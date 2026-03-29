"""Brand overview API endpoints."""
from fastapi import APIRouter, Depends, Query
from api.auth import get_current_user
from api.database import get_db
from api.routes.skus import _escape_ilike

router = APIRouter(tags=["brands"])


@router.get("/brands")
def list_brands(search: str = Query(None), user: dict = Depends(get_current_user)):
    """List all brand metrics, sorted by urgency."""
    with get_db() as conn:
        with conn.cursor() as cur:
            sql = "SELECT * FROM brand_metrics"
            params = []
            if search:
                escaped = _escape_ilike(search)
                sql += " WHERE category_name ILIKE %s"
                params.append(f"%{escaped}%")
            sql += " ORDER BY urgent_skus DESC, reorder_skus DESC, avg_days_to_stockout ASC NULLS LAST"
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def _brands_summary_query(cur) -> dict:
    """Execute the brands summary query using the provided cursor."""
    cur.execute("""
        SELECT
            COUNT(*) AS total_brands,
            SUM(CASE WHEN urgent_skus > 0 THEN 1 ELSE 0 END) AS brands_with_urgent,
            SUM(CASE WHEN reorder_skus > 0 THEN 1 ELSE 0 END) AS brands_with_reorder,
            SUM(out_of_stock_skus) AS total_skus_out_of_stock,
            SUM(COALESCE(dead_stock_skus, 0)) AS total_dead_stock_skus,
            SUM(COALESCE(slow_mover_skus, 0)) AS total_slow_mover_skus,
            SUM(COALESCE(a_class_skus, 0)) AS total_a_class_skus,
            SUM(COALESCE(b_class_skus, 0)) AS total_b_class_skus,
            SUM(COALESCE(c_class_skus, 0)) AS total_c_class_skus,
            SUM(COALESCE(inactive_skus, 0)) AS total_inactive_skus
        FROM brand_metrics
    """)
    return dict(cur.fetchone())


@router.get("/brands/summary")
def brands_summary(cur=None, user: dict = Depends(get_current_user)):
    """Aggregate summary stats for dashboard header cards.

    If ``cur`` is provided, use it instead of opening a new connection.
    """
    if cur is not None:
        return _brands_summary_query(cur)
    with get_db() as conn:
        with conn.cursor() as c:
            return _brands_summary_query(c)


@router.get("/dashboard-summary")
def dashboard_summary(user: dict = Depends(get_current_user)):
    """Cross-cutting summary for the command center home page."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # ABC x Status cross-product + trend counts from sku_metrics
            cur.execute("""
                SELECT
                  COUNT(*) AS total_active_skus,
                  SUM(CASE WHEN abc_class='A' AND reorder_status='urgent' THEN 1 ELSE 0 END) AS a_urgent,
                  SUM(CASE WHEN abc_class='A' AND reorder_status='reorder' THEN 1 ELSE 0 END) AS a_reorder,
                  SUM(CASE WHEN abc_class='B' AND reorder_status='urgent' THEN 1 ELSE 0 END) AS b_urgent,
                  SUM(CASE WHEN abc_class='B' AND reorder_status='reorder' THEN 1 ELSE 0 END) AS b_reorder,
                  SUM(CASE WHEN abc_class='C' AND reorder_status='urgent' THEN 1 ELSE 0 END) AS c_urgent,
                  SUM(CASE WHEN abc_class='C' AND reorder_status='reorder' THEN 1 ELSE 0 END) AS c_reorder,
                  SUM(CASE WHEN reorder_status='urgent' THEN 1 ELSE 0 END) AS total_urgent,
                  SUM(CASE WHEN reorder_status='reorder' THEN 1 ELSE 0 END) AS total_reorder,
                  SUM(CASE WHEN reorder_status='healthy' THEN 1 ELSE 0 END) AS total_healthy,
                  SUM(CASE WHEN reorder_status='out_of_stock' THEN 1 ELSE 0 END) AS total_out_of_stock,
                  SUM(CASE WHEN trend_direction='up' AND total_velocity>0 THEN 1 ELSE 0 END) AS trending_up,
                  SUM(CASE WHEN trend_direction='down' AND total_velocity>0 THEN 1 ELSE 0 END) AS trending_down,
                  SUM(CASE WHEN trend_direction='flat' AND total_velocity>0 THEN 1 ELSE 0 END) AS trending_flat
                FROM sku_metrics sm
                LEFT JOIN stock_items si ON si.name = sm.stock_item_name
                WHERE COALESCE(si.is_active, TRUE) = TRUE
            """)
            sku_row = dict(cur.fetchone())

            # Top priority brands (with per-brand A-critical counts)
            cur.execute("""
                SELECT bm.category_name, bm.urgent_skus, bm.reorder_skus,
                       bm.a_class_skus, bm.b_class_skus, bm.avg_days_to_stockout,
                       COALESCE(ac.a_urgent_skus, 0) AS a_urgent_skus
                FROM brand_metrics bm
                LEFT JOIN (
                    SELECT category_name, COUNT(*) AS a_urgent_skus
                    FROM sku_metrics
                    WHERE abc_class = 'A' AND reorder_status = 'urgent'
                    GROUP BY category_name
                ) ac ON ac.category_name = bm.category_name
                WHERE bm.urgent_skus > 0 OR bm.reorder_skus > 0
                ORDER BY (COALESCE(bm.a_class_skus,0)*3 + COALESCE(bm.b_class_skus,0)) * COALESCE(bm.urgent_skus,0) DESC
                LIMIT 7
            """)
            top_brands = [dict(r) for r in cur.fetchall()]

            # Reuse brands_summary with the current cursor to avoid opening a second connection
            brand_row = brands_summary(cur=cur)

    return {**sku_row, **brand_row, "top_brands": top_brands}
