"""
Comprehensive edge-case and boundary-condition tests for the reorder formula.

Tests cover:
  - Boundary conditions around stock vs wait-period demand
  - Extreme values for velocity, lead time, buffer, stock
  - Rounding and precision (ceil instead of round)
  - Status determination thresholds
  - Coverage auto-calculation edge cases
  - Interaction between status and quantity

New two-case formula:
  wait_period = velocity * lead_time          (no buffer)
  post_arrival = velocity * coverage * buffer  (buffer on coverage only)

  if stock <= wait_period:
      order = ceil(post_arrival)              # wait gap is sunk cost
  else:
      order = ceil(wait + post - stock)       # deduct surplus

  If result <= 0 -> None.
  Negative stock does NOT inflate orders (capped at ceil(post_arrival)).
"""

from engine.reorder import compute_coverage_days, determine_reorder_status


# ---------------------------------------------------------------------------
# Helper: call determine_reorder_status with common defaults to reduce noise
# ---------------------------------------------------------------------------
def _reorder(
    stock, days_to_stockout, lead_time, velocity,
    buffer=1.3, coverage=182,
):
    return determine_reorder_status(
        current_stock=stock,
        days_to_stockout=days_to_stockout,
        supplier_lead_time=lead_time,
        total_velocity=velocity,
        safety_buffer=buffer,
        coverage_period=coverage,
    )


# ===================================================================
# BOUNDARY CONDITIONS (tests 1-6)
# ===================================================================

class TestBoundaryConditions:
    """Stock exactly at, above, or below the wait-period demand threshold."""

    def test_stock_exactly_equals_demand_during_lead(self):
        """Test 1: stock = 234, velocity=2, lead_time=90, coverage=91, buffer=1.3.
        wait = 2 * 90 = 180. post = 2 * 91 * 1.3 = 236.6.
        stock(234) > wait(180) → ceil(180 + 236.6 - 234) = ceil(182.6) = 183.
        """
        stock = 234.0
        status, qty = _reorder(
            stock=stock, days_to_stockout=117.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        # days_to_stockout = 234/2 = 117. 117 > 90 → not critical.
        # warning_buffer = max(30, int(90*0.5)) = 45. 117 <= 135 → reorder.
        assert status == "reorder"
        assert qty == 183

    def test_stock_one_unit_more_than_demand(self):
        """Test 2: stock = 235.
        wait = 180. post = 236.6.
        stock(235) > wait(180) → ceil(180 + 236.6 - 235) = ceil(181.6) = 182.
        """
        stock = 235.0
        status, qty = _reorder(
            stock=stock, days_to_stockout=117.5,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert qty == 182

    def test_stock_one_unit_less_than_demand(self):
        """Test 3: stock = 233.
        wait = 180. post = 236.6.
        stock(233) > wait(180) → ceil(180 + 236.6 - 233) = ceil(183.6) = 184.
        """
        stock = 233.0
        status, qty = _reorder(
            stock=stock, days_to_stockout=116.5,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert qty == 184

    def test_coverage_period_zero_returns_none_qty(self):
        """Test 4: coverage_period = 0 means nothing to cover after arrival.
        wait = 180. post = 0. stock(300) > wait(180) → ceil(180+0-300) = ceil(-120) → None.
        """
        status, qty = _reorder(
            stock=300, days_to_stockout=150.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=0,
        )
        assert status == "healthy"
        assert qty is None

    def test_coverage_period_one_day(self):
        """Test 5: coverage_period = 1 day. Tiny order.
        wait = 180. post = 2 * 1 * 1.3 = 2.6.
        stock(300) > wait(180) → ceil(180 + 2.6 - 300) = ceil(-117.4) → None.
        """
        status, qty = _reorder(
            stock=300, days_to_stockout=150.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=1,
        )
        assert status == "healthy"
        assert qty is None

        # Now with low stock so order is needed:
        # stock=50, wait=180. stock(50) <= wait(180) → ceil(post) = ceil(2.6) = 3.
        status2, qty2 = _reorder(
            stock=50, days_to_stockout=25.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=1,
        )
        assert status2 == "urgent"
        assert qty2 == 3

    def test_coverage_period_365_days(self):
        """Test 6: coverage_period = 365 (full year). Large order.
        wait = 2 * 90 = 180. post = 2 * 365 * 1.3 = 949.
        stock(0) <= wait(180) → ceil(949) = 949.
        """
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=365,
        )
        assert status == "lost_sales"
        assert qty == 949


# ===================================================================
# EXTREME VALUES (tests 7-17)
# ===================================================================

class TestExtremeValues:

    def test_near_zero_velocity(self):
        """Test 7: velocity = 0.001 (~1 unit every 3 years).
        wait = 0.001 * 90 = 0.09. post = 0.001 * 182 * 1.3 = 0.2366.
        stock(0) <= wait(0.09) → ceil(0.2366) = 1.
        """
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=0.001, buffer=1.3, coverage=182,
        )
        assert status == "lost_sales"
        assert qty == 1

        # With larger coverage:
        # wait = 0.09. post = 0.001 * 500 * 1.3 = 0.65.
        # stock(0) <= wait(0.09) → ceil(0.65) = 1.
        status2, qty2 = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=0.001, buffer=1.3, coverage=500,
        )
        assert status2 == "lost_sales"
        assert qty2 == 1

    def test_huge_velocity(self):
        """Test 8: velocity = 100 (huge volume). Orders proportionally large.
        wait = 100 * 90 = 9000. post = 100 * 182 * 1.3 = 23660.
        stock(0) <= wait(9000) → ceil(23660) = 23660.
        """
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=100.0, buffer=1.3, coverage=182,
        )
        assert status == "lost_sales"
        assert qty == 23660

    def test_lead_time_one_day(self):
        """Test 9: lead_time = 1 (instant delivery).
        wait = 2 * 1 = 2. post = 2 * 60 * 1.3 = 156.
        stock(100) > wait(2) → ceil(2 + 156 - 100) = ceil(58) = 58.
        days_to_stockout=50. warning_buffer=max(30,0)=30. 50>1+30=31 → healthy.
        """
        status, qty = _reorder(
            stock=100, days_to_stockout=50.0,
            lead_time=1, velocity=2.0, buffer=1.3, coverage=60,
        )
        assert status == "healthy"
        assert qty == 58

    def test_lead_time_365_days(self):
        """Test 10: lead_time = 365 (one year). Massive depletion during wait.
        wait = 2 * 365 = 730. post = 2 * 365 * 1.3 = 949.
        stock(500) <= wait(730) → ceil(949) = 949.
        days_to_stockout=250. 250 <= 365 → urgent.
        """
        status, qty = _reorder(
            stock=500, days_to_stockout=250.0,
            lead_time=365, velocity=2.0, buffer=1.3, coverage=365,
        )
        assert status == "urgent"
        assert qty == 949

    def test_buffer_one(self):
        """Test 11: buffer = 1.0 (no safety margin). Formula still works.
        wait = 2 * 90 = 180. post = 2 * 91 * 1.0 = 182.
        stock(200) > wait(180) → ceil(180 + 182 - 200) = ceil(162) = 162.
        days_to_stockout=100. 100>90, warning_buffer=max(30,45)=45. 100<135 → reorder.
        """
        status, qty = _reorder(
            stock=200, days_to_stockout=100.0,
            lead_time=90, velocity=2.0, buffer=1.0, coverage=91,
        )
        assert status == "reorder"
        assert qty == 162

    def test_buffer_below_one(self):
        """Test 12: buffer = 0.5 (below 1 — less cautious).
        wait = 2 * 90 = 180. post = 2 * 91 * 0.5 = 91.
        stock(100) <= wait(180) → ceil(91) = 91.
        days_to_stockout=50. 50<=90 → urgent.
        """
        status, qty = _reorder(
            stock=100, days_to_stockout=50.0,
            lead_time=90, velocity=2.0, buffer=0.5, coverage=91,
        )
        assert status == "urgent"
        assert qty == 91

    def test_buffer_extreme_three(self):
        """Test 13: buffer = 3.0 (extreme caution). Inflates orders significantly.
        wait = 2 * 90 = 180. post = 2 * 91 * 3.0 = 546.
        stock(100) <= wait(180) → ceil(546) = 546.
        days_to_stockout=50 <= 90 → urgent.
        """
        status, qty = _reorder(
            stock=100, days_to_stockout=50.0,
            lead_time=90, velocity=2.0, buffer=3.0, coverage=91,
        )
        assert status == "urgent"
        assert qty == 546

    def test_stock_exactly_zero(self):
        """Test 14: stock = 0, velocity > 0. Should be lost_sales.
        wait = 2 * 90 = 180. post = 2 * 91 * 1.3 = 236.6.
        stock(0) <= wait(180) → ceil(236.6) = 237.
        """
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "lost_sales"
        assert qty == 237

    def test_stock_negative_one(self):
        """Test 15: stock = -1 (negative from data issues). Should be lost_sales.
        wait = 180. post = 236.6.
        stock(-1) <= wait(180) → ceil(236.6) = 237. Negative stock does NOT inflate.
        """
        status, qty = _reorder(
            stock=-1, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "lost_sales"
        assert qty == 237

    def test_stock_very_negative(self):
        """Test 16: stock = -1000. Negative stock does NOT inflate order qty.
        wait = 180. post = 236.6.
        stock(-1000) <= wait(180) → ceil(236.6) = 237. Same as stock=0.
        """
        status, qty = _reorder(
            stock=-1000, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "lost_sales"
        assert qty == 237

    def test_stock_huge_inventory(self):
        """Test 17: stock = 999999. So much stock that no order needed.
        wait = 180. post = 236.6.
        stock(999999) > wait(180) → ceil(180 + 236.6 - 999999) → negative → None.
        """
        status, qty = _reorder(
            stock=999999, days_to_stockout=499999.5,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "healthy"
        assert qty is None


# ===================================================================
# ROUNDING AND PRECISION (tests 18-20)
# ===================================================================

class TestRoundingAndPrecision:

    def test_rounding_fractional_velocity(self):
        """Test 18: velocity 0.33/day causes non-integer quantities.
        wait = 0.33 * 90 = 29.7. post = 0.33 * 182 * 1.3 = 78.078.
        stock(0) <= wait(29.7) → ceil(78.078) = 79.
        """
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=0.33, buffer=1.3, coverage=182,
        )
        assert status == "lost_sales"
        assert qty == 79

    def test_exact_integer_result(self):
        """Test 19: exact integers with no rounding error.
        wait = 2 * 90 = 180. post = 2 * 180 * 1.0 = 360.
        stock(0) <= wait(180) → ceil(360) = 360.
        """
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.0, coverage=180,
        )
        assert status == "lost_sales"
        assert qty == 360

    def test_subtraction_rounds_to_zero(self):
        """Test 20: When stock exceeds wait+post, result is negative → None.
        wait = 1 * 10 = 10. post = 1 * 50 * 1.0 = 50.
        stock(60.4) > wait(10) → ceil(10 + 50 - 60.4) = ceil(-0.4) = 0 → None.
        days_to_stockout = 60.4. warning_buffer = max(30, 5) = 30. 60.4 > 40 → healthy.
        """
        status, qty = _reorder(
            stock=60.4, days_to_stockout=60.4,
            lead_time=10, velocity=1.0, buffer=1.0, coverage=50,
        )
        assert status == "healthy"
        assert qty is None

    def test_subtraction_rounds_up_to_one(self):
        """Complementary: when the fractional difference ceils to 1.
        wait = 10. post = 50.
        stock(59.4) > wait(10) → ceil(10 + 50 - 59.4) = ceil(0.6) = 1.
        """
        status, qty = _reorder(
            stock=59.4, days_to_stockout=59.4,
            lead_time=10, velocity=1.0, buffer=1.0, coverage=50,
        )
        assert status == "healthy"
        assert qty == 1


# ===================================================================
# STATUS DETERMINATION EDGE CASES (tests 21-25)
# ===================================================================

class TestStatusThresholds:

    def test_days_to_stockout_equals_lead_time_is_critical(self):
        """Test 21: days_to_stockout = lead_time exactly → URGENT (<=)."""
        # lead_time=90, days_to_stockout=90.0
        # 90 <= 90 → urgent
        status, qty = _reorder(
            stock=180, days_to_stockout=90.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "urgent"

    def test_days_to_stockout_one_above_lead_time_is_warning(self):
        """Test 22: days_to_stockout = lead_time + 1 → REORDER."""
        # days_to_stockout=91. 91 > 90, warning_buffer=45, 91 <= 135 → reorder
        status, qty = _reorder(
            stock=182, days_to_stockout=91.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "reorder"

    def test_days_to_stockout_equals_warning_threshold_is_warning(self):
        """Test 23: days_to_stockout = lead_time + warning_buffer exactly → REORDER (<=)."""
        # warning_buffer = max(30, int(90*0.5)) = 45
        # threshold = 90 + 45 = 135
        # days_to_stockout = 135.0, 135 <= 135 → reorder
        status, qty = _reorder(
            stock=270, days_to_stockout=135.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "reorder"

    def test_days_to_stockout_one_above_warning_threshold_is_ok(self):
        """Test 24: days_to_stockout = lead_time + warning_buffer + 1 → HEALTHY."""
        # threshold = 135, days_to_stockout = 136.0, 136 > 135 → healthy
        status, qty = _reorder(
            stock=272, days_to_stockout=136.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "healthy"

    def test_days_to_stockout_none_with_positive_stock_and_velocity(self):
        """Test 25: days_to_stockout=None but stock>0 and velocity>0.
        Both None checks fall through to 'healthy'.
        wait = 180. post = 236.6. stock(100) <= wait(180) → ceil(236.6) = 237.
        """
        status, qty = _reorder(
            stock=100, days_to_stockout=None,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "healthy"
        assert qty == 237

    def test_warning_buffer_minimum_30_for_short_lead_time(self):
        """Warning buffer should be at least 30 days even for very short lead times.
        lead_time=10 → int(10*0.5)=5, max(30,5)=30. threshold = 10+30=40.
        """
        # days_to_stockout=39 → 39 > 10 → not urgent. 39 <= 40 → reorder.
        status, _ = _reorder(
            stock=39, days_to_stockout=39.0,
            lead_time=10, velocity=1.0, buffer=1.0, coverage=50,
        )
        assert status == "reorder"

        # days_to_stockout=41 → 41 > 40 → healthy
        status2, _ = _reorder(
            stock=41, days_to_stockout=41.0,
            lead_time=10, velocity=1.0, buffer=1.0, coverage=50,
        )
        assert status2 == "healthy"


# ===================================================================
# COVERAGE AUTO-CALCULATION EDGE CASES (tests 26-32)
# ===================================================================

class TestCoverageAutoCalculation:

    def test_lead_time_1_capped_at_6_turns(self):
        """Test 26: lead_time=1 → 365 turns, capped at 6 → 365//6 = 60."""
        assert compute_coverage_days(lead_time=1) == 60

    def test_lead_time_365_one_turn(self):
        """Test 27: lead_time=365 → 1 turn → 365//1 = 365."""
        assert compute_coverage_days(lead_time=365) == 365

    def test_lead_time_182_two_turns(self):
        """Test 28: lead_time=182 → 365//182 = 2 turns → 365//2 = 182."""
        assert compute_coverage_days(lead_time=182) == 182

    def test_lead_time_183_one_turn(self):
        """Test 29: lead_time=183 → 365//183 = 1 turn → 365//1 = 365."""
        assert compute_coverage_days(lead_time=183) == 365

    def test_typical_order_months_zero(self):
        """Test 30: typical_order_months=0 → coverage = 0 days.
        This is allowed — means 'no coverage after arrival'.
        """
        assert compute_coverage_days(lead_time=90, typical_order_months=0) == 0

    def test_typical_order_months_twelve(self):
        """Test 31: typical_order_months=12 → 360 days."""
        assert compute_coverage_days(lead_time=90, typical_order_months=12) == 360

    def test_typical_order_months_one(self):
        """Test 32: typical_order_months=1 → 30 days."""
        assert compute_coverage_days(lead_time=90, typical_order_months=1) == 30

    def test_lead_time_60_six_turns(self):
        """lead_time=60 → 365//60=6 turns (exactly at cap) → 365//6 = 60."""
        assert compute_coverage_days(lead_time=60) == 60

    def test_lead_time_61_five_turns(self):
        """lead_time=61 → 365//61=5 turns (under cap) → 365//5 = 73."""
        assert compute_coverage_days(lead_time=61) == 73

    def test_lead_time_73_five_turns(self):
        """lead_time=73 → 365//73=5 turns → 365//5 = 73."""
        assert compute_coverage_days(lead_time=73) == 73

    def test_typical_months_overrides_auto(self):
        """When typical_order_months is set, lead_time is irrelevant for coverage."""
        # Same lead time, different typical months → different coverage
        assert compute_coverage_days(lead_time=90, typical_order_months=3) == 90
        assert compute_coverage_days(lead_time=90, typical_order_months=6) == 180
        # Auto would give 91 for lead_time=90, but typical overrides:
        assert compute_coverage_days(lead_time=90, typical_order_months=4) == 120


# ===================================================================
# INTERACTION BETWEEN STATUS AND QUANTITY (tests 33-36)
# ===================================================================

class TestStatusQuantityInteraction:

    def test_ok_status_with_suggested_qty(self):
        """Test 33: HEALTHY status should still have suggested_qty when
        stock surplus doesn't cover full target.
        wait = 2 * 90 = 180. post = 2 * 182 * 1.3 = 473.2.
        stock(400) > wait(180) → ceil(180 + 473.2 - 400) = ceil(253.2) = 254.
        days_to_stockout=200. warning_buffer=45. 200 > 135 → healthy.
        """
        status, qty = _reorder(
            stock=400, days_to_stockout=200.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=182,
        )
        assert status == "healthy"
        assert qty == 254

    def test_critical_status_coverage_zero_returns_none(self):
        """Test 34: Critical status with coverage=0 — post_arrival = 0.
        wait = 180. post = 0.
        stock(50) <= wait(180) → ceil(0) = 0 → None.
        Nothing to order for post-arrival when coverage is zero.
        """
        status, qty = _reorder(
            stock=50, days_to_stockout=25.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=0,
        )
        assert status == "urgent"
        assert qty is None

    def test_out_of_stock_positive_velocity_positive_coverage(self):
        """Test 35: Stocked out + velocity > 0 + coverage > 0 → positive qty.
        wait = 180. post = 236.6.
        stock(0) <= wait(180) → ceil(236.6) = 237.
        """
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "lost_sales"
        assert qty == 237
        assert qty > 0

    def test_out_of_stock_positive_velocity_zero_coverage(self):
        """Test 36: Stocked out + velocity > 0 + coverage = 0.
        wait = 180. post = 0.
        stock(0) <= wait(180) → ceil(0) = 0 → None.
        With zero coverage, nothing to order for post-arrival.
        """
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=0,
        )
        assert status == "lost_sales"
        assert qty is None

    def test_out_of_stock_zero_velocity_returns_none(self):
        """Out of stock with no velocity → can't compute a meaningful order."""
        status, qty = _reorder(
            stock=0, days_to_stockout=None,
            lead_time=90, velocity=0.0, buffer=1.3, coverage=182,
        )
        assert status == "out_of_stock"
        assert qty is None

    def test_ok_status_excess_stock_returns_none_qty(self):
        """OK status where stock exceeds all demand → no order needed."""
        status, qty = _reorder(
            stock=10000, days_to_stockout=5000.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=182,
        )
        assert status == "healthy"
        assert qty is None

    def test_warning_status_still_has_qty(self):
        """Warning status with non-zero coverage should provide a qty.
        wait = 180. post = 236.6.
        stock(200) > wait(180) → ceil(180 + 236.6 - 200) = ceil(216.6) = 217.
        100 > 90 but <= 135 → reorder.
        """
        status, qty = _reorder(
            stock=200, days_to_stockout=100.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "reorder"
        assert qty == 217

    def test_critical_fallback_to_order_for_coverage(self):
        """Critical status: stock exactly at wait threshold, tiny coverage.
        wait = 2 * 90 = 180. post = 2 * 1 * 0.5 = 1.
        stock(180) <= wait(180) → ceil(1) = 1.
        """
        status, qty = _reorder(
            stock=180, days_to_stockout=90.0,
            lead_time=90, velocity=2.0, buffer=0.5, coverage=1,
        )
        assert status == "urgent"
        assert qty == 1


# ===================================================================
# ADDITIONAL EDGE CASES
# ===================================================================

class TestAdditionalEdgeCases:

    def test_negative_stock_does_not_inflate_order(self):
        """With the two-case formula, negative stock does NOT inflate orders.
        Both stock=0 and stock=-500 are <= wait(180), so both get ceil(post_arrival).
        wait = 180. post = 236.6. ceil(236.6) = 237.
        """
        _, qty_zero = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        _, qty_neg = _reorder(
            stock=-500, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert qty_zero == 237
        assert qty_neg == 237
        assert qty_neg == qty_zero  # negative stock no longer inflates order

    def test_algebraic_equivalence_when_stock_exceeds_lead_demand(self):
        """When stock > wait, formula is: ceil(wait + post - stock).
        wait = 2 * 90 = 180. post = 2 * 182 * 1.3 = 473.2.
        stock(500) > wait(180) → ceil(180 + 473.2 - 500) = ceil(153.2) = 154.
        """
        velocity = 2.0
        lead_time = 90
        coverage = 182
        buffer = 1.3
        stock = 500.0

        status, qty = _reorder(
            stock=stock, days_to_stockout=250.0,
            lead_time=lead_time, velocity=velocity,
            buffer=buffer, coverage=coverage,
        )
        assert qty == 154

    def test_stock_at_arrival_with_low_stock(self):
        """With low stock, stock <= wait so order = ceil(post_arrival) only.
        wait = 180. post = 236.6.
        stock(10) <= wait(180) → ceil(236.6) = 237.
        """
        status, qty = _reorder(
            stock=10, days_to_stockout=5.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "urgent"
        assert qty == 237

    def test_negative_velocity_treated_as_no_demand(self):
        """Negative velocity (shouldn't happen, but defensive) → dead_stock or out_of_stock."""
        # velocity <= 0 check comes first
        status, qty = _reorder(
            stock=100, days_to_stockout=None,
            lead_time=90, velocity=-1.0, buffer=1.3, coverage=91,
        )
        assert status == "dead_stock"
        assert qty is None

        # With stock <= 0
        status2, qty2 = _reorder(
            stock=0, days_to_stockout=None,
            lead_time=90, velocity=-1.0, buffer=1.3, coverage=91,
        )
        assert status2 == "out_of_stock"
        assert qty2 is None

    def test_very_long_coverage_with_moderate_velocity(self):
        """Sanity check: large coverage period produces proportionally large order.
        wait = 5 * 90 = 450. post = 5 * 365 * 1.3 = 2372.5.
        stock(0) <= wait(450) → ceil(2372.5) = 2373.
        """
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=5.0, buffer=1.3, coverage=365,
        )
        assert status == "lost_sales"
        assert qty == 2373

    def test_must_stock_fallback_independent_of_reorder(self):
        """must_stock_fallback_qty uses coverage_period / 90, verify for completeness."""
        from engine.reorder import must_stock_fallback_qty
        assert must_stock_fallback_qty(30) == 1    # max(1, round(30/90)) = max(1, 0) = 1
        assert must_stock_fallback_qty(90) == 1    # max(1, round(90/90)) = max(1, 1) = 1
        assert must_stock_fallback_qty(180) == 2   # max(1, round(180/90)) = max(1, 2) = 2
        assert must_stock_fallback_qty(1) == 1     # max(1, round(1/90)) = max(1, 0) = 1
        assert must_stock_fallback_qty(15) == 1    # max(1, round(15/90)) = max(1, 0) = 1

    def test_calculate_days_to_stockout_directly(self):
        """Verify the days_to_stockout calculator for completeness."""
        from engine.reorder import calculate_days_to_stockout
        assert calculate_days_to_stockout(100, 2.0) == 50.0
        assert calculate_days_to_stockout(0, 2.0) == 0
        assert calculate_days_to_stockout(-10, 2.0) == 0
        assert calculate_days_to_stockout(100, 0) is None
        assert calculate_days_to_stockout(100, -1) is None
        assert calculate_days_to_stockout(0, 0) == 0  # velocity<=0 and stock<=0 → 0
        assert calculate_days_to_stockout(1, 0.001) == 1000.0
