"""Tests for prefix_group in /api/search and the /api/search/prefix endpoint."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager

from fastapi.testclient import TestClient
from api.main import app
from api.auth import get_current_user

# ---------------------------------------------------------------------------
# Auth override — bypass JWT for all tests
# ---------------------------------------------------------------------------

def _fake_user():
    return {"id": 1, "username": "test", "role": "admin"}

app.dependency_overrides[get_current_user] = _fake_user

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers to build mock DB chain
# ---------------------------------------------------------------------------

def _make_row(**kwargs):
    """Return a dict-like object that mimics a psycopg2 RealDictRow."""
    d = dict(**kwargs)
    # Make it subscriptable by key
    m = MagicMock()
    m.__getitem__ = lambda self, k: d[k]
    m.__iter__ = lambda self: iter(d)
    m.items = lambda: d.items()
    m.keys = lambda: d.keys()
    return m


def _build_db_mock(side_effects):
    """
    Build a mock that satisfies:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
                cur.fetchall() / cur.fetchone()

    `side_effects` is a list of return values for successive cursor calls,
    alternating between execute (ignored) and fetch* results.

    Each item in `side_effects` should be either:
      - A list (returned by fetchall)
      - A dict-like object (returned by fetchone)
    """
    cur = MagicMock()
    fetch_queue = list(side_effects)

    def fake_execute(sql, params=None):
        pass  # no-op; we drive via fetch results

    def fake_fetchall():
        return fetch_queue.pop(0) if fetch_queue else []

    def fake_fetchone():
        return fetch_queue.pop(0) if fetch_queue else None

    cur.execute = fake_execute
    cur.fetchall = fake_fetchall
    cur.fetchone = fake_fetchone

    # Support `with conn.cursor() as cur:`
    cursor_ctx = MagicMock()
    cursor_ctx.__enter__ = MagicMock(return_value=cur)
    cursor_ctx.__exit__ = MagicMock(return_value=False)

    conn = MagicMock()
    conn.cursor = MagicMock(return_value=cursor_ctx)

    @contextmanager
    def fake_get_db():
        yield conn

    return fake_get_db, cur


# ---------------------------------------------------------------------------
# /api/search — prefix_group present in response
# ---------------------------------------------------------------------------

class TestUniversalSearchPrefixGroup:
    """Tests for the prefix_group field added to /api/search."""

    def _search_side_effects(
        self,
        brands=None,
        brand_count=0,
        skus=None,
        sku_count=0,
        prefix_count=0,
        prefix_brands=None,
    ):
        """
        Build the fetch* side-effect queue for a simple (no-scope) search.

        Order of DB calls in universal_search (no scope):
          1. fetchall  -> brands list
          2. fetchone  -> brand_count
          3. fetchall  -> global skus
          4. fetchone  -> global sku_count
          5. fetchone  -> prefix_count
          6. fetchall  -> prefix_brands (only if prefix_count >= 2)
        """
        brands = brands or []
        skus = skus or []
        prefix_brands = prefix_brands or []

        effects = [
            brands,
            {"cnt": brand_count},
            skus,
            {"cnt": sku_count},
            {"cnt": prefix_count},
        ]
        if prefix_count >= 2:
            effects.append([{"category_name": b} for b in prefix_brands])
        return effects

    def test_prefix_group_none_when_count_less_than_2(self):
        """prefix_group should be None when fewer than 2 part_nos match."""
        effects = self._search_side_effects(prefix_count=1)
        fake_db, _ = _build_db_mock(effects)

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search?q=WN")

        assert resp.status_code == 200
        data = resp.json()
        assert "prefix_group" in data
        assert data["prefix_group"] is None

    def test_prefix_group_none_when_count_zero(self):
        """prefix_group should be None when no part_nos match."""
        effects = self._search_side_effects(prefix_count=0)
        fake_db, _ = _build_db_mock(effects)

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search?q=ZZ")

        assert resp.status_code == 200
        assert resp.json()["prefix_group"] is None

    def test_prefix_group_populated_when_count_2_or_more(self):
        """prefix_group should have prefix, total, brands when count >= 2."""
        effects = self._search_side_effects(
            prefix_count=5,
            prefix_brands=["WINSOR & NEWTON", "DALER ROWNEY"],
        )
        fake_db, _ = _build_db_mock(effects)

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search?q=WN")

        assert resp.status_code == 200
        pg = resp.json()["prefix_group"]
        assert pg is not None
        assert pg["prefix"] == "WN"
        assert pg["total"] == 5
        assert pg["brands"] == ["WINSOR & NEWTON", "DALER ROWNEY"]

    def test_prefix_group_exactly_2(self):
        """Boundary: prefix_group should appear when count == 2."""
        effects = self._search_side_effects(
            prefix_count=2,
            prefix_brands=["BRAND A"],
        )
        fake_db, _ = _build_db_mock(effects)

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search?q=AB")

        assert resp.status_code == 200
        pg = resp.json()["prefix_group"]
        assert pg is not None
        assert pg["total"] == 2

    def test_prefix_group_prefix_matches_query(self):
        """prefix_group.prefix should echo back the query string (stripped)."""
        effects = self._search_side_effects(prefix_count=3, prefix_brands=["X"])
        fake_db, _ = _build_db_mock(effects)

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search?q=  WN  ")

        assert resp.status_code == 200
        pg = resp.json()["prefix_group"]
        assert pg["prefix"] == "WN"  # stripped

    def test_universal_search_still_returns_other_fields(self):
        """Existing fields (brands, skus, etc.) must not be broken."""
        brand_row = {
            "category_name": "WINSOR & NEWTON",
            "total_skus": 10,
            "urgent_skus": 2,
        }
        sku_row = {
            "stock_item_name": "WN OIL 37ML TITANIUM WHITE",
            "part_no": "WN1234",
            "category_name": "WINSOR & NEWTON",
            "reorder_status": "ok",
            "current_stock": 50.0,
        }
        effects = [
            [_make_row(**brand_row)],
            {"cnt": 1},
            [_make_row(**sku_row)],
            {"cnt": 1},
            {"cnt": 0},  # prefix_count -> None
        ]
        fake_db, _ = _build_db_mock(effects)

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search?q=WN")

        assert resp.status_code == 200
        data = resp.json()
        assert "brands" in data
        assert "brand_count" in data
        assert "skus" in data
        assert "sku_count" in data
        assert "prefix_group" in data

    def test_search_too_short_returns_400(self):
        resp = client.get("/api/search?q=W")
        assert resp.status_code == 400

    def test_search_missing_q_returns_400(self):
        resp = client.get("/api/search")
        assert resp.status_code == 400

    def test_search_too_long_returns_400(self):
        resp = client.get(f"/api/search?q={'X' * 101}")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /api/search/prefix — dedicated prefix endpoint
# ---------------------------------------------------------------------------

class TestPrefixEndpoint:
    """Tests for GET /api/search/prefix."""

    def _prefix_side_effects(self, skus=None, brands=None):
        """
        Order of DB calls in prefix_search:
          1. fetchall  -> skus
          2. fetchall  -> distinct brands
        """
        return [
            skus or [],
            [{"category_name": b} for b in (brands or [])],
        ]

    def test_prefix_returns_correct_shape(self):
        """Response must include prefix, total, brands, skus."""
        effects = self._prefix_side_effects(
            skus=[],
            brands=[],
        )
        fake_db, _ = _build_db_mock(effects)

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search/prefix?q=WN")

        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"prefix", "total", "brands", "skus"}

    def test_prefix_echoes_query(self):
        """prefix field should reflect the (stripped) query."""
        fake_db, _ = _build_db_mock(self._prefix_side_effects())

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search/prefix?q=  AB  ")

        assert resp.status_code == 200
        assert resp.json()["prefix"] == "AB"

    def test_prefix_total_equals_sku_count(self):
        """total should equal len(skus) returned."""
        sku_rows = [
            _make_row(
                stock_item_name=f"SKU {i}",
                part_no=f"WN{i:04d}",
                category_name="WINSOR & NEWTON",
                reorder_status="ok",
                current_stock=float(i * 10),
            )
            for i in range(4)
        ]
        effects = [sku_rows, [{"category_name": "WINSOR & NEWTON"}]]
        fake_db, _ = _build_db_mock(effects)

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search/prefix?q=WN")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["skus"]) == 4

    def test_prefix_brands_correct(self):
        """brands list should reflect distinct categories from DB."""
        effects = self._prefix_side_effects(
            skus=[],
            brands=["BRAND A", "BRAND B", "BRAND C"],
        )
        fake_db, _ = _build_db_mock(effects)

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search/prefix?q=XX")

        assert resp.status_code == 200
        assert resp.json()["brands"] == ["BRAND A", "BRAND B", "BRAND C"]

    def test_prefix_empty_result(self):
        """Zero matches should return total=0, empty lists."""
        fake_db, _ = _build_db_mock(self._prefix_side_effects())

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search/prefix?q=ZZ")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["skus"] == []
        assert data["brands"] == []

    def test_prefix_too_short_returns_400(self):
        resp = client.get("/api/search/prefix?q=X")
        assert resp.status_code == 400

    def test_prefix_missing_q_returns_400(self):
        resp = client.get("/api/search/prefix")
        assert resp.status_code == 400

    def test_prefix_too_long_returns_400(self):
        resp = client.get(f"/api/search/prefix?q={'X' * 51}")
        assert resp.status_code == 400

    def test_prefix_exactly_50_chars_is_valid(self):
        """50-char prefix is at the limit — should not return 400."""
        fake_db, _ = _build_db_mock(self._prefix_side_effects())

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get(f"/api/search/prefix?q={'A' * 50}")

        assert resp.status_code == 200

    def test_prefix_exactly_2_chars_is_valid(self):
        """2-char prefix is at the min — should not return 400."""
        fake_db, _ = _build_db_mock(self._prefix_side_effects())

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search/prefix?q=WN")

        assert resp.status_code == 200

    def test_prefix_sku_fields_present(self):
        """Each SKU in the response should have the standard fields."""
        sku = _make_row(
            stock_item_name="WN OIL 37ML TITANIUM WHITE",
            part_no="WN1001",
            category_name="WINSOR & NEWTON",
            reorder_status="critical",
            current_stock=5.0,
        )
        effects = [[sku], [{"category_name": "WINSOR & NEWTON"}]]
        fake_db, _ = _build_db_mock(effects)

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search/prefix?q=WN")

        assert resp.status_code == 200
        sku_resp = resp.json()["skus"][0]
        assert sku_resp["stock_item_name"] == "WN OIL 37ML TITANIUM WHITE"
        assert sku_resp["part_no"] == "WN1001"
        assert sku_resp["category_name"] == "WINSOR & NEWTON"
        assert sku_resp["reorder_status"] == "critical"
        assert sku_resp["current_stock"] == 5.0

    def test_prefix_ilike_special_chars_escaped(self):
        """Queries with %, _, \\ should not cause 500 (escaping applied)."""
        fake_db, _ = _build_db_mock(self._prefix_side_effects())

        with patch("api.routes.search.get_db", fake_db):
            resp = client.get("/api/search/prefix?q=W%25N")  # URL-encoded %

        # Should reach the DB layer without crashing (400 or 200 OK)
        assert resp.status_code in (200, 400)
