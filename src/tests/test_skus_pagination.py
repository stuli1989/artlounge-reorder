import unittest
from datetime import date, timedelta
from unittest.mock import patch

from api.routes import skus as skus_module


class _FakeCursor:
    def __init__(self, metric_rows):
        self.metric_rows = metric_rows
        self.fetchall_calls = 0

    def execute(self, _sql, _params=None):
        return None

    def fetchall(self):
        self.fetchall_calls += 1
        if self.fetchall_calls == 1:
            return [
                {"key": "dead_stock_threshold_days", "value": "30"},
                {"key": "slow_mover_velocity_threshold", "value": "0.1"},
            ]
        if self.fetchall_calls == 2:
            return self.metric_rows
        return []

    def fetchone(self):
        return {"supplier_lead_time": 60}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, metric_rows):
        self.metric_rows = metric_rows

    def cursor(self):
        return _FakeCursor(self.metric_rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeDbContext:
    def __init__(self, metric_rows):
        self.metric_rows = metric_rows

    def __enter__(self):
        return _FakeConn(self.metric_rows)

    def __exit__(self, exc_type, exc, tb):
        return False


def _fake_compute_effective_values(current_stock, _wholesale, _online, total, **_kwargs):
    return {
        "eff_stock": current_stock,
        "eff_wholesale": 0.0,
        "eff_online": 0.0,
        "eff_store": 0.0,
        "eff_total": total,
        "has_stock_override": False,
        "has_velocity_override": False,
    }


def _fake_compute_effective_status(eff_stock, _eff_total, _lead_time, _buffer=1.3):
    if eff_stock <= 0:
        return {"eff_days": 0, "eff_status": "out_of_stock", "eff_suggested": 0}
    if eff_stock < 5:
        return {"eff_days": 5, "eff_status": "critical", "eff_suggested": 10}
    return {"eff_days": 20, "eff_status": "warning", "eff_suggested": 5}


class SkuPaginationTests(unittest.TestCase):
    def test_paginated_response_returns_items_total_and_counts(self):
        today = date.today()
        rows = [
            {
                "stock_item_name": "SKU-001",
                "category_name": "WINSOR & NEWTON",
                "current_stock": -2,
                "wholesale_velocity": 0.0,
                "online_velocity": 0.0,
                "store_velocity": 0.0,
                "total_velocity": 0.2,
                "reorder_status": "out_of_stock",
                "days_to_stockout": 0,
                "part_no": "P1",
                "is_hazardous": False,
                "reorder_intent": "normal",
                "stock_override_value": None,
                "stock_override_note": None,
                "stock_override_stale": False,
                "stock_hold_from_po": False,
                "total_vel_override_value": None,
                "total_vel_override_stale": False,
                "wholesale_vel_override_value": None,
                "online_vel_override_value": None,
                "store_vel_override_value": None,
                "override_note": None,
                "note_override_stale": False,
                "hold_from_po": False,
                "last_sale_date": today,
                "total_zero_activity_days": 0,
                "last_import_date": None,
                "last_import_qty": None,
                "reorder_qty_suggested": None,
                "safety_buffer": 1.3,
                "abc_class": None,
                "xyz_class": None,
                "trend_direction": None,
                "trend_ratio": None,
                "total_in_stock_days": 100,
                "total_revenue": 0,
                "wma_total_velocity": 0,
                "wma_wholesale_velocity": 0,
                "wma_online_velocity": 0,
            },
            {
                "stock_item_name": "SKU-002",
                "category_name": "WINSOR & NEWTON",
                "current_stock": 2,
                "wholesale_velocity": 0.0,
                "online_velocity": 0.0,
                "store_velocity": 0.0,
                "total_velocity": 0.3,
                "reorder_status": "critical",
                "days_to_stockout": 5,
                "part_no": "P2",
                "is_hazardous": False,
                "reorder_intent": "normal",
                "stock_override_value": None,
                "stock_override_note": None,
                "stock_override_stale": False,
                "stock_hold_from_po": False,
                "total_vel_override_value": None,
                "total_vel_override_stale": False,
                "wholesale_vel_override_value": None,
                "online_vel_override_value": None,
                "store_vel_override_value": None,
                "override_note": None,
                "note_override_stale": False,
                "hold_from_po": False,
                "last_sale_date": today - timedelta(days=45),
                "total_zero_activity_days": 10,
                "last_import_date": None,
                "last_import_qty": None,
                "reorder_qty_suggested": None,
                "safety_buffer": 1.3,
                "abc_class": None,
                "xyz_class": None,
                "trend_direction": None,
                "trend_ratio": None,
                "total_in_stock_days": 100,
                "total_revenue": 0,
                "wma_total_velocity": 0,
                "wma_wholesale_velocity": 0,
                "wma_online_velocity": 0,
            },
            {
                "stock_item_name": "SKU-003",
                "category_name": "WINSOR & NEWTON",
                "current_stock": 12,
                "wholesale_velocity": 0.0,
                "online_velocity": 0.0,
                "store_velocity": 0.0,
                "total_velocity": 0.4,
                "reorder_status": "warning",
                "days_to_stockout": 20,
                "part_no": "P3",
                "is_hazardous": False,
                "reorder_intent": "normal",
                "stock_override_value": None,
                "stock_override_note": None,
                "stock_override_stale": False,
                "stock_hold_from_po": False,
                "total_vel_override_value": None,
                "total_vel_override_stale": False,
                "wholesale_vel_override_value": None,
                "online_vel_override_value": None,
                "store_vel_override_value": None,
                "override_note": None,
                "note_override_stale": False,
                "hold_from_po": False,
                "last_sale_date": today,
                "total_zero_activity_days": 0,
                "last_import_date": None,
                "last_import_qty": None,
                "reorder_qty_suggested": None,
                "safety_buffer": 1.3,
                "abc_class": None,
                "xyz_class": None,
                "trend_direction": None,
                "trend_ratio": None,
                "total_in_stock_days": 100,
                "total_revenue": 0,
                "wma_total_velocity": 0,
                "wma_wholesale_velocity": 0,
                "wma_online_velocity": 0,
            },
        ]

        with patch.object(skus_module, "get_db", return_value=_FakeDbContext(rows)), \
             patch.object(skus_module, "compute_effective_values", side_effect=_fake_compute_effective_values), \
             patch.object(skus_module, "compute_effective_status", side_effect=_fake_compute_effective_status):
            result = skus_module.list_skus(
                category_name="WINSOR & NEWTON",
                status=None,
                min_velocity=None,
                sort="days_to_stockout",
                sort_dir="asc",
                search=None,
                hazardous=None,
                dead_stock=None,
                reorder_intent=None,
                slow_mover=None,
                from_date=None,
                to_date=None,
                abc_class=None,
                xyz_class=None,
                hide_inactive=False,
                velocity_type="flat",
                paginated=True,
                limit=2,
                offset=1,
                user={"id": 1, "username": "test", "role": "viewer"},
            )

        self.assertEqual(result["total"], 3)
        self.assertEqual(result["offset"], 1)
        self.assertEqual(result["limit"], 2)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["stock_item_name"], "SKU-002")
        self.assertEqual(result["items"][1]["stock_item_name"], "SKU-003")
        self.assertEqual(result["counts"]["critical"], 1)
        self.assertEqual(result["counts"]["warning"], 1)
        self.assertEqual(result["counts"]["out_of_stock"], 1)
        self.assertEqual(result["counts"]["dead_stock"], 1)


if __name__ == "__main__":
    unittest.main()
