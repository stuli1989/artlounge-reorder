"""
Comprehensive edge-case and boundary-condition tests for the reorder formula.

Tests cover:
  - Boundary conditions around stock vs demand-during-lead
  - Extreme values for velocity, lead time, buffer, stock
  - Rounding and precision
  - Status determination thresholds
  - Coverage auto-calculation edge cases
  - Interaction between status and quantity
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
    """Stock exactly at, above, or below the demand-during-lead threshold."""

    def test_stock_exactly_equals_demand_during_lead(self):
        """Test 1: stock = velocity * lead_time * buffer (234).
        But demand_during_lead = velocity * lead_time (NO buffer) = 180.
        stock_at_arrival = 234 - 180 = 54; order = round(236.6 - 54) = 183.
        """
        # velocity=2, lead_time=90, buffer=1.3
        # demand_during_lead = 2 * 90 = 180  (NO buffer)
        stock = 234.0
        # order_for_coverage = 2 * 91 * 1.3 = 236.6
        # suggested = max(0, round(180 + 236.6 - 234)) = round(182.6) = 183
        status, qty = _reorder(
            stock=stock, days_to_stockout=117.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        # days_to_stockout = 234/2 = 117. 117 > 90 → not critical.
        # warning_buffer = max(30, int(90*0.5)) = 45. 117 <= 135 → warning.
        assert status == "warning"
        assert qty == 183

    def test_stock_one_unit_more_than_demand(self):
        """Test 2: stock = demand_during_lead + 1 = 181.
        demand_during_lead = 2 * 90 = 180 (NO buffer).
        stock_at_arrival = 181 - 180 = 1, order = round(236.6 - 1) = 236.
        """
        stock = 235.0  # using original stock value
        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 2 * 91 * 1.3 = 236.6
        # suggested = max(0, round(180 + 236.6 - 235)) = round(181.6) = 182
        status, qty = _reorder(
            stock=stock, days_to_stockout=117.5,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert qty == 182

    def test_stock_one_unit_less_than_demand(self):
        """Test 3: stock = 233, demand_during_lead = 180 (NO buffer).
        stock_at_arrival = 233 - 180 = 53, order = round(236.6 - 53) = 184.
        """
        stock = 233.0
        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 2 * 91 * 1.3 = 236.6
        # suggested = max(0, round(180 + 236.6 - 233)) = round(183.6) = 184
        status, qty = _reorder(
            stock=stock, days_to_stockout=116.5,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert qty == 184

    def test_coverage_period_zero_returns_none_qty(self):
        """Test 4: coverage_period = 0 means nothing to cover after arrival.
        Suggested qty should always be None.
        """
        # stock=300, velocity=2, lead_time=90, buffer=1.3
        # demand_during_lead = 234, stock_at_arrival = 66
        # order_for_coverage = 2 * 0 * 1.3 = 0
        # suggested = max(0, round(0 - 66)) = 0 → None
        # days_to_stockout = 150, 150 > 90+45=135 → OK
        status, qty = _reorder(
            stock=300, days_to_stockout=150.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=0,
        )
        assert status == "ok"
        assert qty is None

    def test_coverage_period_one_day(self):
        """Test 5: coverage_period = 1 day. Tiny order."""
        # velocity=2, lead_time=90, buffer=1.3, coverage=1
        # demand_during_lead = 2 * 90 = 180 (NO buffer)
        # order_for_coverage = 2 * 1 * 1.3 = 2.6
        # stock=300, suggested = max(0, round(180 + 2.6 - 300)) = max(0, round(-117.4)) = 0 → None
        status, qty = _reorder(
            stock=300, days_to_stockout=150.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=1,
        )
        assert status == "ok"
        assert qty is None

        # Now with low stock so order is needed:
        # stock=50, days_to_stockout=25 → critical
        # suggested = max(0, round(180 + 2.6 - 50)) = round(132.6) = 133
        status2, qty2 = _reorder(
            stock=50, days_to_stockout=25.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=1,
        )
        assert status2 == "critical"
        assert qty2 == 133

    def test_coverage_period_365_days(self):
        """Test 6: coverage_period = 365 (full year). Large order."""
        # velocity=2, lead_time=90, buffer=1.3, coverage=365
        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 2 * 365 * 1.3 = 949.0
        # stock=0 → stocked_out, qty = max(0, round(180 + 949 - 0)) = 1129
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=365,
        )
        assert status == "stocked_out"
        assert qty == 1129


# ===================================================================
# EXTREME VALUES (tests 7-17)
# ===================================================================

class TestExtremeValues:

    def test_near_zero_velocity(self):
        """Test 7: velocity = 0.001 (~1 unit every 3 years).
        With coverage=182, order should be tiny.
        """
        # demand_during_lead = 0.001 * 90 = 0.09
        # order_for_coverage = 0.001 * 182 * 1.3 = 0.2366
        # stock=0 → stocked_out, suggested = round(0.09 + 0.2366) = round(0.3266) = 0 → None
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=0.001, buffer=1.3, coverage=182,
        )
        assert status == "stocked_out"
        assert qty is None  # Too small to round up to 1

        # With larger coverage, it becomes 1:
        # demand_during_lead = 0.001 * 90 = 0.09
        # order_for_coverage = 0.001 * 500 * 1.3 = 0.65
        # suggested = round(0.09 + 0.65) = round(0.74) = 1
        status2, qty2 = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=0.001, buffer=1.3, coverage=500,
        )
        assert status2 == "stocked_out"
        assert qty2 == 1

    def test_huge_velocity(self):
        """Test 8: velocity = 100 (huge volume). Orders proportionally large."""
        # velocity=100, lead_time=90, buffer=1.3, coverage=182
        # demand_during_lead = 100 * 90 = 9000
        # order_for_coverage = 100 * 182 * 1.3 = 23660
        # stock=0 → stocked_out, qty = max(0, round(9000 + 23660 - 0)) = 32660
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=100.0, buffer=1.3, coverage=182,
        )
        assert status == "stocked_out"
        assert qty == 32660

    def test_lead_time_one_day(self):
        """Test 9: lead_time = 1 (instant delivery).
        stock_at_arrival should be close to current_stock.
        """
        # velocity=2, lead_time=1, buffer=1.3, coverage=60
        # demand_during_lead = 2 * 1 = 2  (NO buffer)
        # order_for_coverage = 2 * 60 * 1.3 = 156
        # stock=100, suggested = max(0, round(2 + 156 - 100)) = 58
        # days_to_stockout=50. warning_buffer=max(30,0)=30. 50>1+30=31 → OK
        status, qty = _reorder(
            stock=100, days_to_stockout=50.0,
            lead_time=1, velocity=2.0, buffer=1.3, coverage=60,
        )
        assert status == "ok"
        assert qty == 58

    def test_lead_time_365_days(self):
        """Test 10: lead_time = 365 (one year). Massive depletion during wait."""
        # velocity=2, lead_time=365, buffer=1.3, coverage=365
        # demand_during_lead = 2 * 365 = 730  (NO buffer)
        # order_for_coverage = 2 * 365 * 1.3 = 949
        # stock=500, suggested = max(0, round(730 + 949 - 500)) = 1179
        # days_to_stockout=250. 250 <= 365 → critical
        status, qty = _reorder(
            stock=500, days_to_stockout=250.0,
            lead_time=365, velocity=2.0, buffer=1.3, coverage=365,
        )
        assert status == "critical"
        assert qty == 1179

    def test_buffer_one(self):
        """Test 11: buffer = 1.0 (no safety margin). Formula still works."""
        # velocity=2, lead_time=90, buffer=1.0, coverage=91
        # demand_during_lead = 2 * 90 * 1.0 = 180
        # stock=200, stock_at_arrival = 200 - 180 = 20
        # order_for_coverage = 2 * 91 * 1.0 = 182
        # suggested = round(182 - 20) = 162
        # days_to_stockout=100. 100>90, warning_buffer=max(30,45)=45. 100<135 → warning
        status, qty = _reorder(
            stock=200, days_to_stockout=100.0,
            lead_time=90, velocity=2.0, buffer=1.0, coverage=91,
        )
        assert status == "warning"
        assert qty == 162

    def test_buffer_below_one(self):
        """Test 12: buffer = 0.5 (below 1 — less cautious). Formula still works."""
        # velocity=2, lead_time=90, buffer=0.5, coverage=91
        # demand_during_lead = 2 * 90 = 180  (NO buffer)
        # order_for_coverage = 2 * 91 * 0.5 = 91
        # stock=100, suggested = max(0, round(180 + 91 - 100)) = 171
        # days_to_stockout=50. 50<=90 → critical
        status, qty = _reorder(
            stock=100, days_to_stockout=50.0,
            lead_time=90, velocity=2.0, buffer=0.5, coverage=91,
        )
        assert status == "critical"
        assert qty == 171

    def test_buffer_extreme_three(self):
        """Test 13: buffer = 3.0 (extreme caution). Inflates orders significantly."""
        # velocity=2, lead_time=90, buffer=3.0, coverage=91
        # demand_during_lead = 2 * 90 = 180  (NO buffer)
        # order_for_coverage = 2 * 91 * 3.0 = 546
        # stock=100, suggested = max(0, round(180 + 546 - 100)) = 626
        # days_to_stockout=50 <= 90 → critical
        status, qty = _reorder(
            stock=100, days_to_stockout=50.0,
            lead_time=90, velocity=2.0, buffer=3.0, coverage=91,
        )
        assert status == "critical"
        assert qty == 626

    def test_stock_exactly_zero(self):
        """Test 14: stock = 0, velocity > 0. Should be stocked_out."""
        # velocity=2, lead_time=90, coverage=91, buffer=1.3
        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 2 * 91 * 1.3 = 236.6
        # suggested = max(0, round(180 + 236.6 - 0)) = 417
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "stocked_out"
        assert qty == 417

    def test_stock_negative_one(self):
        """Test 15: stock = -1 (negative from data issues). Should be stocked_out."""
        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 2 * 91 * 1.3 = 236.6
        # suggested = max(0, round(180 + 236.6 - (-1))) = round(417.6) = 418
        status, qty = _reorder(
            stock=-1, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "stocked_out"
        assert qty == 418

    def test_stock_very_negative(self):
        """Test 16: stock = -1000. Negative stock increases the order qty."""
        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 2 * 91 * 1.3 = 236.6
        # suggested = max(0, round(180 + 236.6 - (-1000))) = round(1416.6) = 1417
        status, qty = _reorder(
            stock=-1000, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "stocked_out"
        assert qty == 1417

    def test_stock_huge_inventory(self):
        """Test 17: stock = 999999. So much stock that no order needed."""
        # demand_during_lead = 2 * 90 * 1.3 = 234
        # stock_at_arrival = 999999 - 234 = 999765
        # order_for_coverage = 236.6
        # suggested = max(0, round(236.6 - 999765)) = 0 → None
        # days_to_stockout = 999999 / 2 = 499999.5 → OK
        status, qty = _reorder(
            stock=999999, days_to_stockout=499999.5,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "ok"
        assert qty is None


# ===================================================================
# ROUNDING AND PRECISION (tests 18-20)
# ===================================================================

class TestRoundingAndPrecision:

    def test_rounding_fractional_velocity(self):
        """Test 18: velocity 0.33/day causes non-integer quantities."""
        # stock=0 → stocked_out
        # demand_during_lead = 0.33 * 90 = 29.7
        # order_for_coverage = 0.33 * 182 * 1.3 = 78.078
        # suggested = round(29.7 + 78.078) = round(107.778) = 108
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=0.33, buffer=1.3, coverage=182,
        )
        assert status == "stocked_out"
        assert qty == 108

    def test_exact_integer_result(self):
        """Test 19: exact integers with no rounding error."""
        # stock=0, velocity=2.0, lead_time=90, coverage=180, buffer=1.0
        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 2 * 180 * 1.0 = 360
        # suggested = 180 + 360 = 540
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.0, coverage=180,
        )
        assert status == "stocked_out"
        assert qty == 540

    def test_subtraction_rounds_to_zero(self):
        """Test 20: When stock_at_arrival is just barely above order_for_coverage,
        the difference is negative and rounds to 0 → qty becomes None.
        """
        # velocity=1, lead_time=10, buffer=1.0, coverage=50
        # stock=60.4
        # demand_during_lead = 1 * 10 * 1.0 = 10
        # stock_at_arrival = 60.4 - 10 = 50.4
        # order_for_coverage = 1 * 50 * 1.0 = 50
        # suggested = max(0, round(50 - 50.4)) = max(0, round(-0.4)) = max(0, 0) = 0 → None
        # days_to_stockout = 60.4. warning_buffer = max(30, 5) = 30. 60.4 > 40 → OK
        status, qty = _reorder(
            stock=60.4, days_to_stockout=60.4,
            lead_time=10, velocity=1.0, buffer=1.0, coverage=50,
        )
        assert status == "ok"
        assert qty is None

    def test_subtraction_rounds_up_to_one(self):
        """Complementary: when the fractional difference rounds UP to 1."""
        # stock=59.4, demand_during_lead=10, stock_at_arrival=49.4
        # order_for_coverage=50
        # 50 - 49.4 = 0.6 → round = 1
        # days_to_stockout=59.4 > 40 → OK
        status, qty = _reorder(
            stock=59.4, days_to_stockout=59.4,
            lead_time=10, velocity=1.0, buffer=1.0, coverage=50,
        )
        assert status == "ok"
        assert qty == 1


# ===================================================================
# STATUS DETERMINATION EDGE CASES (tests 21-25)
# ===================================================================

class TestStatusThresholds:

    def test_days_to_stockout_equals_lead_time_is_critical(self):
        """Test 21: days_to_stockout = lead_time exactly → CRITICAL (<=)."""
        # lead_time=90, days_to_stockout=90.0
        # 90 <= 90 → critical
        status, qty = _reorder(
            stock=180, days_to_stockout=90.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "critical"

    def test_days_to_stockout_one_above_lead_time_is_warning(self):
        """Test 22: days_to_stockout = lead_time + 1 → WARNING."""
        # days_to_stockout=91. 91 > 90, warning_buffer=45, 91 <= 135 → warning
        status, qty = _reorder(
            stock=182, days_to_stockout=91.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "warning"

    def test_days_to_stockout_equals_warning_threshold_is_warning(self):
        """Test 23: days_to_stockout = lead_time + warning_buffer exactly → WARNING (<=)."""
        # warning_buffer = max(30, int(90*0.5)) = 45
        # threshold = 90 + 45 = 135
        # days_to_stockout = 135.0, 135 <= 135 → warning
        status, qty = _reorder(
            stock=270, days_to_stockout=135.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "warning"

    def test_days_to_stockout_one_above_warning_threshold_is_ok(self):
        """Test 24: days_to_stockout = lead_time + warning_buffer + 1 → OK."""
        # threshold = 135, days_to_stockout = 136.0, 136 > 135 → OK
        status, qty = _reorder(
            stock=272, days_to_stockout=136.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "ok"

    def test_days_to_stockout_none_with_positive_stock_and_velocity(self):
        """Test 25: days_to_stockout=None but stock>0 and velocity>0.
        This is an unusual state (calculate_days_to_stockout wouldn't produce it
        for positive stock + positive velocity), but determine_reorder_status
        handles it: both None checks fall through to 'ok' (neither is <= lead_time).
        """
        status, qty = _reorder(
            stock=100, days_to_stockout=None,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "ok"
        assert qty == 317

    def test_warning_buffer_minimum_30_for_short_lead_time(self):
        """Warning buffer should be at least 30 days even for very short lead times.
        lead_time=10 → int(10*0.5)=5, max(30,5)=30. threshold = 10+30=40.
        """
        # days_to_stockout=39 → 39 <= 40 but > 10? No, 39 > 10 → not critical.
        # Actually 39 <= 10? No, 39 > 10. So check warning: 39 <= 10+30=40 → warning.
        status, _ = _reorder(
            stock=39, days_to_stockout=39.0,
            lead_time=10, velocity=1.0, buffer=1.0, coverage=50,
        )
        assert status == "warning"

        # days_to_stockout=41 → 41 > 40 → OK
        status2, _ = _reorder(
            stock=41, days_to_stockout=41.0,
            lead_time=10, velocity=1.0, buffer=1.0, coverage=50,
        )
        assert status2 == "ok"


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
        """Test 33: OK status should still have suggested_qty when
        stock_at_arrival < coverage_qty. You're OK now but should prep.
        """
        # velocity=2, lead_time=90, buffer=1.3, coverage=182
        # demand_during_lead = 2 * 90 = 180  (NO buffer)
        # order_for_coverage = 2 * 182 * 1.3 = 473.2
        # stock=400, suggested = max(0, round(180 + 473.2 - 400)) = round(253.2) = 253
        # days_to_stockout=200. warning_buffer=45. 200 > 135 → OK
        status, qty = _reorder(
            stock=400, days_to_stockout=200.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=182,
        )
        assert status == "ok"
        assert qty == 253

    def test_critical_status_coverage_zero_returns_qty(self):
        """Test 34: Critical status with coverage=0 still orders for lead time demand."""
        # velocity=2, lead_time=90, buffer=1.3, coverage=0
        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 0
        # stock=50, suggested = max(0, round(180 + 0 - 50)) = 130
        # days_to_stockout=25 → 25 <= 90 → critical
        status, qty = _reorder(
            stock=50, days_to_stockout=25.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=0,
        )
        assert status == "critical"
        assert qty == 130

    def test_out_of_stock_positive_velocity_positive_coverage(self):
        """Test 35: Stocked out + velocity > 0 + coverage > 0 → positive qty."""
        # velocity=2, lead_time=90, coverage=91, buffer=1.3
        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 2 * 91 * 1.3 = 236.6
        # suggested = max(0, round(180 + 236.6 - 0)) = 417
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "stocked_out"
        assert qty == 417
        assert qty > 0

    def test_out_of_stock_positive_velocity_zero_coverage(self):
        """Test 36: Stocked out + velocity > 0 + coverage = 0.
        Even with zero coverage, demand_during_lead still produces an order.
        """
        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 2 * 0 * 1.3 = 0
        # suggested = max(0, round(180 + 0 - 0)) = 180
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=0,
        )
        assert status == "stocked_out"
        assert qty == 180

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
        assert status == "ok"
        assert qty is None

    def test_warning_status_still_has_qty(self):
        """Warning status with non-zero coverage should provide a qty."""
        # velocity=2, lead_time=90, buffer=1.3, coverage=91
        # demand_during_lead = 2 * 90 = 180  (NO buffer)
        # order_for_coverage = 2 * 91 * 1.3 = 236.6
        # stock=200, suggested = max(0, round(180 + 236.6 - 200)) = round(216.6) = 217
        # 100 > 90 but <= 135 → warning
        status, qty = _reorder(
            stock=200, days_to_stockout=100.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "warning"
        assert qty == 217

    def test_critical_fallback_to_order_for_coverage(self):
        """Critical status: when suggested_qty is None (coverage exceeds need),
        falls back to order_for_coverage.

        This tests the `suggested_qty or round(order_for_coverage) or None` logic.
        """
        # Construct a case where suggested_qty is None but order_for_coverage > 0
        # This happens when stock_at_arrival > order_for_coverage but stock < lead demand
        # Hmm, that's contradictory. Let's think...
        # suggested_qty is None when round(order_for_coverage - stock_at_arrival) <= 0
        # This means stock_at_arrival >= order_for_coverage
        # For critical: days_to_stockout <= lead_time, so stock is running low
        # But stock_at_arrival could still be > 0 if current_stock > demand_during_lead
        # Wait — if days_to_stockout <= lead_time and stock > 0, let's check:
        # days_to_stockout = stock / velocity. For this <= lead_time:
        #   stock / velocity <= lead_time → stock <= velocity * lead_time
        # demand_during_lead = velocity * lead_time * buffer (buffer >= 1 typically)
        # So stock <= demand_during_lead / buffer <= demand_during_lead
        # → stock_at_arrival = max(0, stock - demand_during_lead) = 0
        #
        # With buffer < 1 (e.g. 0.5), stock could be > demand_during_lead:
        # stock <= velocity * lead_time (from critical condition)
        # demand_during_lead = velocity * lead_time * 0.5 < stock
        # stock_at_arrival = stock - demand_during_lead > 0
        # If coverage is small, order_for_coverage < stock_at_arrival → suggested=None
        #
        # velocity=2, lead_time=90, buffer=0.5, coverage=1
        # critical condition: days_to_stockout <= 90
        # stock=180, days_to_stockout=90 → exactly critical
        # demand_during_lead = 2*90*0.5 = 90
        # stock_at_arrival = 180 - 90 = 90
        # order_for_coverage = 2*1*0.5 = 1
        # suggested = max(0, round(1 - 90)) = 0 → None
        # Return: ("critical", None or round(1) or None) = ("critical", 1)
        status, qty = _reorder(
            stock=180, days_to_stockout=90.0,
            lead_time=90, velocity=2.0, buffer=0.5, coverage=1,
        )
        assert status == "critical"
        assert qty == 1  # Falls back to round(order_for_coverage)


# ===================================================================
# ADDITIONAL EDGE CASES
# ===================================================================

class TestAdditionalEdgeCases:

    def test_negative_stock_increases_order(self):
        """Negative stock increases the order because the formula subtracts
        effective_stock (which is negative), effectively adding the deficit.
        """
        # stock=0: suggested = round(180 + 236.6 - 0) = 417
        _, qty_zero = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        # stock=-500: suggested = round(180 + 236.6 - (-500)) = round(916.6) = 917
        _, qty_neg = _reorder(
            stock=-500, days_to_stockout=0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert qty_zero == 417
        assert qty_neg == 917
        assert qty_neg > qty_zero

    def test_algebraic_equivalence_when_stock_exceeds_lead_demand(self):
        """Formula: demand_during_lead + order_for_coverage - stock.
        demand_during_lead = velocity * lead_time (NO buffer).
        """
        velocity = 2.0
        lead_time = 90
        coverage = 182
        buffer = 1.3
        stock = 500.0

        # demand_during_lead = 2 * 90 = 180
        # order_for_coverage = 2 * 182 * 1.3 = 473.2
        # suggested = round(180 + 473.2 - 500) = round(153.2) = 153
        status, qty = _reorder(
            stock=stock, days_to_stockout=250.0,
            lead_time=lead_time, velocity=velocity,
            buffer=buffer, coverage=coverage,
        )
        assert qty == 153

    def test_stock_at_arrival_with_low_stock(self):
        """With low stock, formula includes full lead demand minus stock."""
        # velocity=2, lead_time=90, buffer=1.3
        # demand_during_lead = 2 * 90 = 180  (NO buffer)
        # order_for_coverage = 2 * 91 * 1.3 = 236.6
        # stock=10, suggested = max(0, round(180 + 236.6 - 10)) = round(406.6) = 407
        status, qty = _reorder(
            stock=10, days_to_stockout=5.0,
            lead_time=90, velocity=2.0, buffer=1.3, coverage=91,
        )
        assert status == "critical"
        assert qty == 407

    def test_negative_velocity_treated_as_no_demand(self):
        """Negative velocity (shouldn't happen, but defensive) → no_demand or out_of_stock."""
        # velocity <= 0 check comes first
        status, qty = _reorder(
            stock=100, days_to_stockout=None,
            lead_time=90, velocity=-1.0, buffer=1.3, coverage=91,
        )
        assert status == "no_demand"
        assert qty is None

        # With stock <= 0
        status2, qty2 = _reorder(
            stock=0, days_to_stockout=None,
            lead_time=90, velocity=-1.0, buffer=1.3, coverage=91,
        )
        assert status2 == "out_of_stock"
        assert qty2 is None

    def test_very_long_coverage_with_moderate_velocity(self):
        """Sanity check: large coverage period produces proportionally large order."""
        # velocity=5, lead_time=90, coverage=365, buffer=1.3
        # demand_during_lead = 5 * 90 = 450
        # order_for_coverage = 5 * 365 * 1.3 = 2372.5
        # suggested = round(450 + 2372.5) = round(2822.5) = 2822
        status, qty = _reorder(
            stock=0, days_to_stockout=0,
            lead_time=90, velocity=5.0, buffer=1.3, coverage=365,
        )
        assert status == "stocked_out"
        assert qty == 2822  # round(2822.5) — Python rounds 0.5 to nearest even

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
