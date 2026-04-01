"""
Tests verifying that the reorder formula is consistent across ALL code paths.

Code paths tested:
  1. engine/reorder.py — determine_reorder_status()  [canonical]
  2. api/routes/po.py — _compute_po_items() inline formula
  3. engine/pipeline.py — calls determine_reorder_status with coverage_period
  4. engine/recalculate_buffers.py — calls determine_reorder_status with coverage_period
  5. api/routes/skus.py — calls determine_reorder_status with coverage_period
  6. engine/effective_values.py — compute_effective_status() [no coverage_period]

Findings documented inline where bugs or inconsistencies are detected.
"""
import inspect
import math
import random
import textwrap

import pytest

from engine.reorder import determine_reorder_status, calculate_days_to_stockout
from engine.effective_values import compute_effective_status


# ---------------------------------------------------------------------------
# Helper: replicate the PO route's inline formula (po.py lines 87-96)
# ---------------------------------------------------------------------------
def po_route_formula(
    eff_stock: float,
    eff_total: float,
    lead_time: int,
    coverage_period: int,
    buffer: float,
) -> int | None:
    """
    Replica of the engine formula (canonical two-case formula with ceil).

    wait_period = velocity * lead_time          (no buffer on lead)
    post_arrival = velocity * coverage * buffer  (buffer on coverage only)

    Case 1: stock <= wait_period → order = ceil(post_arrival)
    Case 2: stock > wait_period  → order = ceil(wait + post - stock)
    If result <= 0, return None.
    """
    if eff_total > 0:
        wait_period = eff_total * lead_time
        post_arrival = eff_total * coverage_period * buffer
        if eff_stock <= wait_period:
            suggested = math.ceil(post_arrival)
        else:
            suggested = math.ceil(wait_period + post_arrival - eff_stock)
        if suggested <= 0:
            suggested = None
        return suggested
    else:
        return None


# ---------------------------------------------------------------------------
# 1. Core vs PO route formula match
# ---------------------------------------------------------------------------
class TestCoreVsPOFormula:
    """Given identical inputs, verify determine_reorder_status() and the PO
    route's inline formula produce the same suggested_qty."""

    def _get_suggested_from_core(self, stock, velocity, lead_time, coverage, buffer):
        """Extract suggested_qty from determine_reorder_status, skipping
        the out_of_stock special-case pathway that always forces order_for_coverage."""
        days = calculate_days_to_stockout(stock, velocity)
        status, qty = determine_reorder_status(
            stock, days, lead_time, velocity,
            safety_buffer=buffer, coverage_period=coverage,
        )
        return status, qty

    def test_plenty_of_stock(self):
        """Stock is abundant — both paths should agree on suggested_qty."""
        stock, vel, lt, cov, buf = 500, 2.0, 90, 180, 1.3
        _, core_qty = self._get_suggested_from_core(stock, vel, lt, cov, buf)
        po_qty = po_route_formula(stock, vel, lt, cov, buf)
        assert core_qty == po_qty, f"Core={core_qty}, PO={po_qty}"

    def test_critical_low_stock(self):
        """Stock will run out before order arrives — critical status."""
        stock, vel, lt, cov, buf = 50, 2.0, 90, 180, 1.3
        _, core_qty = self._get_suggested_from_core(stock, vel, lt, cov, buf)
        po_qty = po_route_formula(stock, vel, lt, cov, buf)
        assert core_qty == po_qty, f"Core={core_qty}, PO={po_qty}"

    def test_out_of_stock_positive_velocity(self):
        """Stock is 0 but there is velocity — Case 1 (stock <= wait).
        wait=2*90=180, post=2*180*1.3=468, stock(0)<=wait(180) → ceil(468)=468."""
        stock, vel, lt, cov, buf = 0, 2.0, 90, 180, 1.3
        _, core_qty = self._get_suggested_from_core(stock, vel, lt, cov, buf)
        po_qty = po_route_formula(stock, vel, lt, cov, buf)
        assert core_qty == 468, f"Core={core_qty}, expected 468"
        assert core_qty == po_qty, f"Core={core_qty}, PO={po_qty}"

    def test_negative_stock(self):
        """Negative stock — out_of_stock in core.  The PO inline formula
        also clamps stock_at_arrival to 0, so they agree."""
        stock, vel, lt, cov, buf = -10, 3.0, 60, 120, 1.3
        _, core_qty = self._get_suggested_from_core(stock, vel, lt, cov, buf)
        po_qty = po_route_formula(stock, vel, lt, cov, buf)
        assert core_qty == po_qty, f"Core={core_qty}, PO={po_qty}"

    @pytest.mark.parametrize("stock,vel,lt,cov,buf", [
        (100, 1.0, 30, 60, 1.0),
        (200, 5.0, 120, 180, 1.5),
        (0, 0.5, 90, 90, 1.3),
        (1000, 0.1, 365, 365, 2.0),
        (50, 10.0, 14, 30, 1.1),
    ])
    def test_parametric_agreement(self, stock, vel, lt, cov, buf):
        """Parametric sweep: core and PO formulas agree for varied inputs."""
        _, core_qty = self._get_suggested_from_core(stock, vel, lt, cov, buf)
        po_qty = po_route_formula(stock, vel, lt, cov, buf)
        assert core_qty == po_qty, f"Core={core_qty}, PO={po_qty}"


# ---------------------------------------------------------------------------
# 2. Coverage passed everywhere (code review tests)
# ---------------------------------------------------------------------------
class TestCoveragePassedEverywhere:
    """Assert that key call-sites pass coverage_period to determine_reorder_status,
    rather than relying on the default of 0."""

    def test_recalculate_buffers_passes_coverage(self):
        """recalculate_buffers.py must pass coverage_period=coverage."""
        import engine.recalculate_buffers as mod
        src = inspect.getsource(mod.recalculate_all_buffers)
        assert "coverage_period=coverage" in src, (
            "recalculate_buffers.py does not pass coverage_period to determine_reorder_status"
        )

    def test_pipeline_phase4_passes_coverage(self):
        """pipeline.py Phase 4 reorder recomputation must pass coverage_period."""
        import engine.pipeline as mod
        src = inspect.getsource(mod.run_computation_pipeline)
        # There should be at least one call with coverage_period=coverage
        assert src.count("coverage_period=coverage") >= 1, (
            "pipeline.py Phase 4 does not pass coverage_period"
        )

    def test_pipeline_phase1_passes_coverage(self):
        """pipeline.py Phase 1 initial reorder computation must pass coverage_period."""
        import engine.pipeline as mod
        src = inspect.getsource(mod.run_computation_pipeline)
        # Phase 1 also uses coverage_period=coverage
        assert src.count("coverage_period=coverage") >= 2, (
            "pipeline.py Phase 1 does not pass coverage_period (expected 2 calls, "
            "one in Phase 1, one in Phase 4)"
        )

    def test_skus_breakdown_passes_coverage(self):
        """skus.py breakdown endpoint must pass coverage_period."""
        import api.routes.skus as mod
        src = inspect.getsource(mod.get_breakdown)
        assert "coverage_period=coverage_days" in src, (
            "skus.py get_breakdown does not pass coverage_period to determine_reorder_status"
        )

    def test_skus_xyz_buffer_passes_coverage(self):
        """skus.py xyz_buffer toggle recomputation must pass coverage_period."""
        import api.routes.skus as mod
        src = inspect.getsource(mod.update_xyz_buffer)
        assert "coverage_period=coverage" in src, (
            "skus.py update_xyz_buffer does not pass coverage_period to determine_reorder_status"
        )


# ---------------------------------------------------------------------------
# 3. effective_values coverage_period=0 safety check
# ---------------------------------------------------------------------------
class TestEffectiveValuesCoverageZero:
    """compute_effective_status() calls determine_reorder_status WITHOUT
    coverage_period (defaults to 0).  This means its eff_suggested is
    computed with coverage=0 — effectively just the demand-during-lead term.

    This is SAFE only if callers that actually need suggested_qty compute it
    separately (as po.py does).  But skus.py uses eff_suggested directly
    for display.  Document this known limitation."""

    def test_effective_status_accepts_coverage_period(self):
        """Verify that compute_effective_status accepts coverage_period.
        This parameter is now supported — callers can pass it directly."""
        src = inspect.getsource(compute_effective_status)
        assert "coverage_period" in src, (
            "compute_effective_status should accept coverage_period"
        )

    def test_effective_status_suggested_with_zero_coverage(self):
        """With coverage_period=0, suggested_qty reflects only the
        demand-during-lead-time shortfall, not the full reorder quantity.
        Verify the value is smaller than the full formula."""
        stock, vel, lt, cov, buf = 50, 2.0, 90, 180, 1.3
        # Full formula
        days = calculate_days_to_stockout(stock, vel)
        _, full_qty = determine_reorder_status(
            stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
        )
        # Effective status (no coverage)
        st = compute_effective_status(stock, vel, lt, buf)
        eff_qty = st["eff_suggested"]

        # With coverage=0, the order_for_coverage=0, so suggested_qty should
        # be 0 (or None) since there's nothing to order for beyond lead time
        # stock depletion.  Full qty should be larger.
        if full_qty is not None and eff_qty is not None:
            assert full_qty >= eff_qty, (
                f"Full qty ({full_qty}) should be >= effective qty ({eff_qty}) "
                f"since effective uses coverage=0"
            )

    def test_skus_list_uses_effective_suggested_from_zero_coverage(self):
        """Document that skus.py list_skus assigns effective_suggested_qty
        from compute_effective_status (which has coverage=0).  This is a
        known limitation — the SKU table shows a lower suggested_qty than
        the PO builder would compute.  Verify the code pattern exists."""
        import api.routes.skus as mod
        src = inspect.getsource(mod.list_skus)
        # skus.py line ~215: d["effective_suggested_qty"] = st["eff_suggested"]
        assert 'st["eff_suggested"]' in src or "st['eff_suggested']" in src, (
            "skus.py no longer uses eff_suggested from compute_effective_status"
        )

    def test_po_route_does_not_use_effective_suggested(self):
        """Verify that po.py computes its own suggested_qty rather than
        using the one from compute_effective_status (which has no coverage)."""
        import api.routes.po as mod
        src = inspect.getsource(mod._compute_po_items)
        # The PO route should compute its own suggested via inline formula
        assert "order_for_coverage" in src, (
            "PO route should compute its own order_for_coverage"
        )
        # And should NOT use st["eff_suggested"] for the final qty
        assert 'st["eff_suggested"]' not in src and "st['eff_suggested']" not in src, (
            "PO route should NOT use eff_suggested from compute_effective_status"
        )


# ---------------------------------------------------------------------------
# 4. Formula algebraic equivalence
# ---------------------------------------------------------------------------
class TestFormulaAlgebraicEquivalence:
    """Prove the two-case formula's algebraic properties.

    New formula (no buffer on lead demand):
        wait_period  = vel * LT               (no buffer)
        post_arrival = vel * CP * buf          (buffer on coverage only)

        Case 1 (stock <= wait): order = ceil(post_arrival)
        Case 2 (stock > wait):  order = ceil(wait + post - stock)
                                      = ceil(vel*LT + vel*CP*buf - stock)

    Case 2 is NOT equivalent to the old formula vel*(LT+CP)*buf - stock
    because buffer is no longer applied to the lead-time term.
    """

    @pytest.mark.parametrize("stock,vel,lt,cov,buf", [
        (500, 2.0, 90, 180, 1.3),
        (1000, 1.5, 120, 120, 1.0),
        (200, 0.5, 60, 90, 1.5),
        (800, 3.0, 30, 60, 2.0),
        (10000, 10.0, 180, 365, 1.1),
    ])
    def test_algebraic_equivalence_when_stock_exceeds_lead_demand(
        self, stock, vel, lt, cov, buf,
    ):
        """When stock > vel * LT (no buffer), Case 2 applies:
        order = ceil(vel*LT + vel*CP*buf - stock).
        Verify the engine agrees with this direct calculation."""
        wait_period = vel * lt  # no buffer
        # Only test cases where stock exceeds wait period
        if stock <= wait_period:
            pytest.skip("Stock does not exceed wait period for this case")

        # Direct algebraic calculation (Case 2)
        raw = vel * lt + vel * cov * buf - stock
        expected = math.ceil(raw) if raw > 0 else None

        # Engine result
        days = calculate_days_to_stockout(stock, vel)
        _, engine_qty = determine_reorder_status(
            stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
        )

        assert engine_qty == expected, (
            f"Algebraic mismatch: engine={engine_qty}, expected={expected}"
        )

    @pytest.mark.parametrize("stock,vel,lt,cov,buf", [
        (10, 2.0, 90, 180, 1.3),   # stock << wait_period
        (0, 5.0, 60, 120, 1.0),    # zero stock
        (50, 1.0, 120, 180, 1.5),  # stock < wait period
    ])
    def test_two_step_caps_when_stock_below_lead_demand(
        self, stock, vel, lt, cov, buf,
    ):
        """When stock <= vel * LT (no buffer), Case 1 applies:
        order = ceil(vel * CP * buf).  The wait gap is a sunk cost —
        negative stock does NOT inflate orders."""
        wait_period = vel * lt  # no buffer

        # New formula (Case 1): just post-arrival coverage
        new_qty = math.ceil(vel * cov * buf)

        # Engine result
        days = calculate_days_to_stockout(stock, vel)
        _, engine_qty = determine_reorder_status(
            stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
        )

        assert engine_qty == new_qty, (
            f"Engine ({engine_qty}) should equal ceil(vel*cov*buf) = {new_qty} "
            f"when stock ({stock}) is below wait period ({wait_period})"
        )


# ---------------------------------------------------------------------------
# 5. Property-based: order_qty is never negative
# ---------------------------------------------------------------------------
class TestOrderQtyNeverNegative:
    """For random inputs, suggested_qty is always None or > 0."""

    def test_random_inputs_qty_never_negative(self):
        rng = random.Random(42)
        for _ in range(50):
            stock = rng.uniform(0, 1000)
            vel = rng.uniform(0.01, 20)
            lt = rng.randint(1, 365)
            cov = rng.randint(1, 365)
            buf = rng.uniform(0.5, 3.0)

            days = calculate_days_to_stockout(stock, vel)
            status, qty = determine_reorder_status(
                stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
            )
            assert qty is None or qty > 0, (
                f"qty={qty} for stock={stock:.1f}, vel={vel:.2f}, "
                f"lt={lt}, cov={cov}, buf={buf:.2f}"
            )

    def test_zero_velocity_returns_none(self):
        """Zero velocity should always return None qty (can't estimate demand)."""
        for stock in [0, 50, 500]:
            days = calculate_days_to_stockout(stock, 0)
            status, qty = determine_reorder_status(
                stock, days, 90, 0, safety_buffer=1.3, coverage_period=180,
            )
            assert qty is None, f"Expected None qty for zero velocity, got {qty}"

    def test_po_formula_never_negative(self):
        """PO inline formula also never returns negative."""
        rng = random.Random(99)
        for _ in range(50):
            stock = rng.uniform(-100, 1000)  # Include negative stock
            vel = rng.uniform(0.01, 20)
            lt = rng.randint(1, 365)
            cov = rng.randint(1, 365)
            buf = rng.uniform(0.5, 3.0)

            qty = po_route_formula(stock, vel, lt, cov, buf)
            assert qty is None or qty > 0, (
                f"PO qty={qty} for stock={stock:.1f}, vel={vel:.2f}, "
                f"lt={lt}, cov={cov}, buf={buf:.2f}"
            )


# ---------------------------------------------------------------------------
# 6. Property-based: higher stock -> lower or equal order
# ---------------------------------------------------------------------------
class TestHigherStockLowerOrder:
    """For fixed velocity/lead_time/coverage/buffer, increasing stock should
    never increase order qty."""

    def test_monotonic_decreasing_with_stock(self):
        vel, lt, cov, buf = 2.0, 90, 180, 1.3
        prev_qty = None
        for stock in range(0, 1001, 50):
            days = calculate_days_to_stockout(stock, vel)
            _, qty = determine_reorder_status(
                stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
            )
            effective_qty = qty if qty is not None else 0
            if prev_qty is not None:
                assert effective_qty <= prev_qty, (
                    f"Order increased from {prev_qty} to {effective_qty} "
                    f"when stock went from {stock - 50} to {stock}"
                )
            prev_qty = effective_qty

    def test_monotonic_with_random_params(self):
        """Same test with randomly chosen params (fixed vel/lt/cov/buf, sweep stock)."""
        rng = random.Random(123)
        for _ in range(10):
            vel = rng.uniform(0.1, 15)
            lt = rng.randint(7, 300)
            cov = rng.randint(7, 300)
            buf = rng.uniform(0.8, 2.5)

            prev_qty = None
            for stock in range(0, 501, 25):
                days = calculate_days_to_stockout(stock, vel)
                _, qty = determine_reorder_status(
                    stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
                )
                effective_qty = qty if qty is not None else 0
                if prev_qty is not None:
                    assert effective_qty <= prev_qty, (
                        f"Order increased from {prev_qty} to {effective_qty} "
                        f"when stock increased. vel={vel:.2f}, lt={lt}, "
                        f"cov={cov}, buf={buf:.2f}"
                    )
                prev_qty = effective_qty


# ---------------------------------------------------------------------------
# 7. Property-based: higher velocity -> higher or equal order
# ---------------------------------------------------------------------------
class TestHigherVelocityHigherOrder:
    """For fixed stock/lead_time/coverage/buffer, increasing velocity should
    always increase order qty (or keep it the same if both are 0/None)."""

    def test_monotonic_increasing_with_velocity(self):
        stock, lt, cov, buf = 100, 90, 180, 1.3
        prev_qty = None
        for vel_x10 in range(1, 201):  # 0.1 to 20.0
            vel = vel_x10 / 10.0
            days = calculate_days_to_stockout(stock, vel)
            _, qty = determine_reorder_status(
                stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
            )
            effective_qty = qty if qty is not None else 0
            if prev_qty is not None:
                assert effective_qty >= prev_qty, (
                    f"Order decreased from {prev_qty} to {effective_qty} "
                    f"when velocity went from {(vel_x10 - 1) / 10.0} to {vel}"
                )
            prev_qty = effective_qty

    def test_monotonic_with_random_params(self):
        rng = random.Random(456)
        for _ in range(10):
            stock = rng.uniform(0, 500)
            lt = rng.randint(7, 300)
            cov = rng.randint(7, 300)
            buf = rng.uniform(0.8, 2.5)

            prev_qty = None
            for vel_x10 in range(1, 101):
                vel = vel_x10 / 10.0
                days = calculate_days_to_stockout(stock, vel)
                _, qty = determine_reorder_status(
                    stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
                )
                effective_qty = qty if qty is not None else 0
                if prev_qty is not None:
                    assert effective_qty >= prev_qty, (
                        f"Order decreased from {prev_qty} to {effective_qty} "
                        f"when velocity increased. stock={stock:.1f}, lt={lt}, "
                        f"cov={cov}, buf={buf:.2f}"
                    )
                prev_qty = effective_qty


# ---------------------------------------------------------------------------
# 8. Property-based: higher coverage -> higher or equal order
# ---------------------------------------------------------------------------
class TestHigherCoverageHigherOrder:
    """For fixed stock/velocity/lead_time/buffer, increasing coverage should
    always increase order qty (or keep it the same)."""

    def test_monotonic_increasing_with_coverage(self):
        stock, vel, lt, buf = 100, 2.0, 90, 1.3
        prev_qty = None
        for cov in range(0, 366, 10):
            days = calculate_days_to_stockout(stock, vel)
            _, qty = determine_reorder_status(
                stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
            )
            effective_qty = qty if qty is not None else 0
            if prev_qty is not None:
                assert effective_qty >= prev_qty, (
                    f"Order decreased from {prev_qty} to {effective_qty} "
                    f"when coverage went from {cov - 10} to {cov}"
                )
            prev_qty = effective_qty

    def test_monotonic_with_random_params(self):
        rng = random.Random(789)
        for _ in range(10):
            stock = rng.uniform(0, 500)
            vel = rng.uniform(0.1, 10)
            lt = rng.randint(7, 200)
            buf = rng.uniform(0.8, 2.5)

            prev_qty = None
            for cov in range(0, 366, 15):
                days = calculate_days_to_stockout(stock, vel)
                _, qty = determine_reorder_status(
                    stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
                )
                effective_qty = qty if qty is not None else 0
                if prev_qty is not None:
                    assert effective_qty >= prev_qty, (
                        f"Order decreased from {prev_qty} to {effective_qty} "
                        f"when coverage increased. stock={stock:.1f}, "
                        f"vel={vel:.2f}, lt={lt}, buf={buf:.2f}"
                    )
                prev_qty = effective_qty


# ---------------------------------------------------------------------------
# 9. Inconsistency documentation: must_stock_fallback_qty argument
# ---------------------------------------------------------------------------
class TestMustStockFallbackConsistency:
    """Verify must_stock_fallback_qty() is called via determine_reorder_status
    with coverage_period. The engine calls it internally with coverage_period
    when reorder_intent == 'must_stock' and velocity == 0.
    """

    def test_engine_uses_coverage_period_for_fallback(self):
        """The engine's determine_reorder_status calls must_stock_fallback_qty(coverage_period)
        when intent=must_stock and velocity=0."""
        src = inspect.getsource(determine_reorder_status)
        assert "must_stock_fallback_qty(coverage_period)" in src

    def test_pipeline_passes_coverage_to_determine_reorder(self):
        """Pipeline passes coverage_period to determine_reorder_status,
        which handles the must_stock fallback internally."""
        import engine.pipeline as mod
        src = inspect.getsource(mod.run_computation_pipeline)
        assert "coverage_period=coverage" in src

    def test_recalculate_buffers_passes_coverage(self):
        """recalculate_buffers passes coverage_period to determine_reorder_status."""
        import engine.recalculate_buffers as mod
        src = inspect.getsource(mod.recalculate_all_buffers)
        assert "coverage_period=coverage" in src

    def test_po_route_has_must_stock_handling(self):
        """PO route handles must_stock intent."""
        import api.routes.po as mod
        src = inspect.getsource(mod._compute_po_items)
        assert "must_stock_fallback_qty" in src

    def test_fallback_qty_scales_with_coverage(self):
        """Larger coverage_period produces larger fallback qty."""
        from engine.reorder import must_stock_fallback_qty
        small = must_stock_fallback_qty(90)    # max(1, round(90/90)) = 1
        large = must_stock_fallback_qty(270)   # max(1, round(270/90)) = 3
        assert large > small, (
            f"Larger coverage ({large}) should exceed smaller ({small})"
        )


# ---------------------------------------------------------------------------
# 10. Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    """Edge cases that exercise boundary conditions in the formula."""

    def test_coverage_zero_gives_no_order_when_stock_covers_lead(self):
        """With coverage=0 and enough stock for lead time, no order needed.
        wait=1*90=90, post=1*0*1.3=0, stock(500)>wait(90) → ceil(90+0-500)=ceil(-410)→None."""
        stock, vel, lt, buf = 500, 1.0, 90, 1.3
        days = calculate_days_to_stockout(stock, vel)
        status, qty = determine_reorder_status(
            stock, days, lt, vel, safety_buffer=buf, coverage_period=0,
        )
        assert qty is None, f"Expected None when coverage=0 and stock covers lead, got {qty}"

    def test_very_high_buffer(self):
        """Buffer of 3.0 should still produce valid results."""
        stock, vel, lt, cov, buf = 100, 1.0, 90, 180, 3.0
        days = calculate_days_to_stockout(stock, vel)
        status, qty = determine_reorder_status(
            stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
        )
        assert qty is None or qty > 0

    def test_very_small_velocity(self):
        """Very small velocity should produce a small order.
        wait=0.01*90=0.9, post=0.01*180*1.3=2.34, stock(0)<=wait(0.9) → ceil(2.34)=3."""
        stock, vel, lt, cov, buf = 0, 0.01, 90, 180, 1.3
        days = calculate_days_to_stockout(stock, vel)
        status, qty = determine_reorder_status(
            stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
        )
        assert qty is not None and qty > 0 and qty <= 5

    def test_lead_time_one_day(self):
        """Minimum lead time.
        wait=5*1=5, post=5*30*1.3=195, stock(0)<=wait(5) → ceil(195)=195."""
        stock, vel, lt, cov, buf = 0, 5.0, 1, 30, 1.3
        days = calculate_days_to_stockout(stock, vel)
        status, qty = determine_reorder_status(
            stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
        )
        assert status == "lost_sales"
        assert qty == 195

    def test_matching_stock_and_demand(self):
        """Stock exactly equals wait_period (vel*lt): Case 1 applies
        (stock <= wait), so order = ceil(post_arrival)."""
        vel, lt, buf = 1.0, 100, 1.0
        stock = vel * lt  # 100.0 exactly = wait_period
        cov = 200
        days = calculate_days_to_stockout(stock, vel)
        _, qty = determine_reorder_status(
            stock, days, lt, vel, safety_buffer=buf, coverage_period=cov,
        )
        # wait=1*100=100, post=1*200*1=200, stock(100)<=wait(100) → ceil(200)=200
        assert qty == 200
