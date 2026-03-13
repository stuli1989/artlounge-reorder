"""Purchase Order data and Excel export endpoints."""
import io
from datetime import date
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openpyxl import Workbook
from openpyxl.styles import Font, Border, Side

from api.database import get_db
from api.sql_fragments import OVERRIDE_AGG_SUBQUERY
from engine.effective_values import compute_effective_values, compute_effective_status
from engine.reorder import must_stock_fallback_qty
from engine.velocity import resolve_date_range, fetch_batch_velocities, velocities_from_batch_row, opt_float

router = APIRouter(tags=["po"])


@router.get("/brands/{category_name}/po-data")
def po_data(
    category_name: str,
    lead_time: int = Query(None),
    buffer: float = Query(1.3),
    include_warning: bool = Query(True),
    include_ok: bool = Query(False),
    from_date: str = Query(None, description="Analysis period start (YYYY-MM-DD)"),
    to_date: str = Query(None, description="Analysis period end (YYYY-MM-DD)"),
):
    """SKUs needing reorder with suggested quantities."""
    custom_range = from_date is not None or to_date is not None

    with get_db() as conn:
        with conn.cursor() as cur:
            # Get supplier lead time if not overridden
            if lead_time is None:
                cur.execute("""
                    SELECT supplier_lead_time FROM brand_metrics
                    WHERE category_name = %s
                """, (category_name,))
                row = cur.fetchone()
                lead_time = row["supplier_lead_time"] if row and row["supplier_lead_time"] else 180

            # Build status filter — skip SQL filter when custom range (status recalculated)
            statuses = ["critical", "out_of_stock"]
            if include_warning:
                statuses.append("warning")
            if include_ok:
                statuses.append("ok")

            status_clause = "AND sm.reorder_status = ANY(%s)" if not custom_range else ""
            query_params = [category_name]
            if not custom_range:
                query_params.append(statuses)

            cur.execute(f"""
                SELECT sm.stock_item_name, sm.current_stock, sm.total_velocity,
                       sm.wholesale_velocity, sm.online_velocity,
                       sm.days_to_stockout, sm.reorder_status,
                       si.part_no,
                       si.is_hazardous,
                       si.reorder_intent,
                       ovr.stock_override_value AS stock_override,
                       ovr.total_vel_override_value AS total_vel_override,
                       ovr.wholesale_vel_override_value AS wholesale_vel_override,
                       ovr.online_vel_override_value AS online_vel_override,
                       ovr.store_vel_override_value AS store_vel_override,
                       COALESCE(ovr.stock_hold_from_po, ovr.total_vel_hold,
                                ovr.wholesale_vel_hold, ovr.online_vel_hold,
                                ovr.store_vel_hold, FALSE) AS hold_from_po
                FROM sku_metrics sm
                LEFT JOIN stock_items si ON si.tally_name = sm.stock_item_name
                LEFT JOIN {OVERRIDE_AGG_SUBQUERY} ovr ON ovr.stock_item_name = sm.stock_item_name
                WHERE sm.category_name = %s {status_clause}
                ORDER BY sm.days_to_stockout ASC NULLS LAST
            """, query_params)
            rows = cur.fetchall()

            # Batch velocity recalculation when custom date range is active
            vel_by_sku = {}
            if custom_range:
                range_start, range_end = resolve_date_range(from_date, to_date)
                sku_names = [r["stock_item_name"] for r in rows]
                vel_by_sku = fetch_batch_velocities(cur, sku_names, range_start, range_end)

    result = []
    for r in rows:
        d = dict(r)
        if d["hold_from_po"] or d.get("reorder_intent") == "do_not_reorder":
            continue

        # Base velocities: recalculated from positions or stored metrics
        if vel_by_sku:
            base_wholesale, base_online, _, base_total = velocities_from_batch_row(
                vel_by_sku.get(d["stock_item_name"])
            )
        else:
            base_wholesale = float(d["wholesale_velocity"] or 0)
            base_online = float(d["online_velocity"] or 0)
            base_total = float(d["total_velocity"] or 0)

        vals = compute_effective_values(
            float(d["current_stock"] or 0),
            base_wholesale,
            base_online,
            base_total,
            stock_ovr=opt_float(d["stock_override"]),
            wholesale_ovr=opt_float(d["wholesale_vel_override"]),
            online_ovr=opt_float(d["online_vel_override"]),
            store_ovr=opt_float(d["store_vel_override"]),
            total_ovr=opt_float(d["total_vel_override"]),
        )
        st = compute_effective_status(vals["eff_stock"], vals["eff_total"], lead_time)

        if vals["eff_total"] > 0:
            suggested = round(vals["eff_total"] * lead_time * buffer)
        elif d.get("reorder_intent") == "must_stock":
            suggested = must_stock_fallback_qty(lead_time)
        else:
            suggested = None
        result.append({
            "stock_item_name": d["stock_item_name"],
            "part_no": d.get("part_no"),
            "current_stock": vals["eff_stock"],
            "total_velocity": vals["eff_total"],
            "days_to_stockout": st["eff_days"],
            "reorder_status": st["eff_status"],
            "suggested_qty": suggested,
            "lead_time": lead_time,
            "buffer": buffer,
            "has_override": vals["has_stock_override"] or vals["has_velocity_override"],
            "is_hazardous": d.get("is_hazardous") or False,
            "reorder_intent": d.get("reorder_intent", "normal"),
        })

    # Post-recalculation status filter when custom range is active
    if custom_range:
        target_statuses = set(statuses)
        result = [r for r in result if r["reorder_status"] in target_statuses]

    return result


class PoItem(BaseModel):
    stock_item_name: str
    order_qty: int
    current_stock: float = 0
    velocity_per_month: float = 0
    days_to_stockout: float | None = None
    notes: str = ""


class PoExportRequest(BaseModel):
    category_name: str
    supplier_name: str = ""
    lead_time: int = 180
    buffer: float = 1.3
    items: list[PoItem]


@router.post("/export/po")
def export_po(req: PoExportRequest):
    """Generate and download an Excel purchase order."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Purchase Order"

    # Styles
    title_font = Font(size=14, bold=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # Header section
    ws.merge_cells("A1:H1")
    ws["A1"] = "Art Lounge India - Purchase Order"
    ws["A1"].font = title_font

    ws["A2"] = f"To: {req.supplier_name}" if req.supplier_name else "To: (supplier)"
    ws["A3"] = f"Date: {date.today().isoformat()}"

    brand_prefix = req.category_name[:3].upper().replace(" ", "")
    ws["A4"] = f"Reference: PO-{brand_prefix}-{date.today().strftime('%Y%m%d')}"
    ws["A5"] = f"Lead Time: {req.lead_time} days | Buffer: {req.buffer}x"

    # Column headers (row 7)
    headers = ["#", "Item Name", "Qty", "Unit", "Current Stock",
               "Velocity/Month", "Days Left", "Notes"]
    col_widths = [5, 50, 10, 8, 14, 14, 12, 20]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=7, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.border = thin_border
        ws.column_dimensions[cell.column_letter].width = width

    # Data rows
    total_qty = 0
    for i, item in enumerate(req.items, 1):
        row = 7 + i
        ws.cell(row=row, column=1, value=i).border = thin_border
        ws.cell(row=row, column=2, value=item.stock_item_name).border = thin_border
        ws.cell(row=row, column=3, value=item.order_qty).border = thin_border
        ws.cell(row=row, column=4, value="Nos").border = thin_border
        ws.cell(row=row, column=5, value=item.current_stock).border = thin_border
        ws.cell(row=row, column=6, value=round(item.velocity_per_month, 1)).border = thin_border
        ws.cell(row=row, column=7, value=item.days_to_stockout).border = thin_border
        ws.cell(row=row, column=8, value=item.notes).border = thin_border
        total_qty += item.order_qty

    # Totals row
    totals_row = 8 + len(req.items)
    ws.cell(row=totals_row, column=1, value="").font = Font(bold=True)
    ws.cell(row=totals_row, column=2, value=f"Total Items: {len(req.items)}").font = Font(bold=True)
    ws.cell(row=totals_row, column=3, value=total_qty).font = Font(bold=True)

    # Footer
    footer_row = totals_row + 2
    ws.cell(row=footer_row, column=1,
            value="Generated by Art Lounge Stock Intelligence System").font = Font(italic=True, color="888888")

    # Write to buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"PO-{brand_prefix}-{date.today().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
