"""Tests for /api/search endpoint — uses live database.

Run: cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_search.py -v
Requires: local PostgreSQL with artlounge_reorder database populated.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.auth import get_current_user

# Override auth for all tests
app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "test", "role": "viewer"}
client = TestClient(app)


class TestSearchValidation:
    def test_missing_q_returns_400(self):
        resp = client.get("/api/search")
        assert resp.status_code == 400

    def test_short_q_returns_400(self):
        resp = client.get("/api/search?q=a")
        assert resp.status_code == 400

    def test_whitespace_only_returns_400(self):
        resp = client.get("/api/search?q=%20%20")
        assert resp.status_code == 400

    def test_too_long_q_returns_400(self):
        resp = client.get(f"/api/search?q={'x' * 101}")
        assert resp.status_code == 400


class TestSearchResults:
    def test_basic_search_returns_brands_and_skus(self):
        resp = client.get("/api/search?q=winsor")
        assert resp.status_code == 200
        data = resp.json()
        assert "brands" in data
        assert "skus" in data
        assert "brand_count" in data
        assert "sku_count" in data

    def test_scoped_search_returns_scoped_skus(self):
        resp = client.get("/api/search?q=blue&scope=WINSOR%20%26%20NEWTON")
        assert resp.status_code == 200
        data = resp.json()
        assert "scoped_skus" in data
        assert "scoped_sku_count" in data
        for s in data["scoped_skus"]:
            assert s["category_name"] == "WINSOR & NEWTON"

    def test_no_scope_omits_scoped_fields(self):
        resp = client.get("/api/search?q=blue")
        assert resp.status_code == 200
        data = resp.json()
        assert "scoped_skus" not in data
        assert "scoped_sku_count" not in data

    def test_sku_results_include_display_name(self):
        resp = client.get("/api/search?q=winsor")
        assert resp.status_code == 200
        data = resp.json()
        for s in data["skus"]:
            assert "display_name" in s
            assert "item_code" in s
            assert "category_name" in s
            assert "reorder_status" in s
            assert "current_stock" in s

    def test_brand_results_limited_to_5(self):
        resp = client.get("/api/search?q=ar")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["brands"]) <= 5

    def test_sku_results_limited_to_10(self):
        resp = client.get("/api/search?q=blue")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["skus"]) <= 10


class TestSearchEscaping:
    def test_special_chars_dont_break_query(self):
        resp = client.get("/api/search?q=100%25")
        assert resp.status_code == 200

    def test_underscore_escaped(self):
        resp = client.get("/api/search?q=test_item")
        assert resp.status_code == 200
