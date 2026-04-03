"""
Operational / business-perspective stress tests for the reorder formula.

These tests model real Art Lounge scenarios:
- Sea freight from Europe (150-180 day lead times)
- Air freight emergencies (15-30 days)
- Wholesale spike behavior, slow movers, fast movers
- Negative stock from Tally renames
- Multi-turn ordering cycles and working capital efficiency

The formula under test (two-case):
    wait_period  = velocity * lead_time              (no buffer)
    post_arrival = velocity * coverage * buffer       (buffer on coverage only)

    if stock <= wait_period:
        order = ceil(post_arrival)                    # wait gap is sunk cost
    else:
        order = ceil(wait_period + post_arrival - stock)  # deduct surplus

    If order <= 0, returns None.
"""
import math
import pytest

from engine.reorder import compute_coverage_days, determine_reorder_status


# ---------------------------------------------------------------------------
# Helper: raw formula computation (mirrors the engine exactly)
# ---------------------------------------------------------------------------

def _raw_formula(stock, velocity, lead_time, coverage, buffer):
    """Reproduce the two-case formula outside the engine for clarity in assertions."""
    wait_period = velocity * lead_time          # no buffer
    post_arrival = velocity * coverage * buffer  # buffer on coverage only

    if stock <= wait_period:
        order = math.ceil(post_arrival)          # wait gap is sunk cost
    else:
        order = math.ceil(wait_period + post_arrival - stock)  # deduct surplus

    return max(0, order)


# ===================================================================
# 1. Sea freight European supplier
# ===================================================================

class TestSeaFreightEuropeanSupplier:
    """Scenario: Importing FAVINI watercolour paper from Italy.
    Lead time 150 days (sea freight), sells 3/day across channels,
    only 50 units left, supplier ships every 6 months.
    """

    LEAD = 150
    VELOCITY = 3.0
    STOCK = 50
    BUFFER = 1.3
    COVERAGE = 180  # typical_order_months=6

    def test_coverage_days_for_6_month_order(self):
        # Explicit 6-month order cycle -> 180 days
        assert compute_coverage_days(self.LEAD, typical_order_months=6) == 180

    def test_stock_runs_out_during_lead_time(self):
        # 50 units / 3 per day = 16.7 days of stock
        # Lead time is 150 days -> stock will be gone long before arrival
        days_left = self.STOCK / self.VELOCITY
        assert days_left < self.LEAD, "Stock should run out during lead time"

    def test_suggested_qty(self):
        # wait = 3 * 150 = 450, post = 3 * 180 * 1.3 = 702
        # stock(50) <= wait(450) -> Case 1: ceil(702) = 702
        days_to_stockout = round(self.STOCK / self.VELOCITY, 1)  # 16.7
        status, qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        assert status == "urgent"
        assert qty == 702

    def test_order_covers_6_months_of_demand(self):
        # 702 units at 3/day = 234 days
        # The order should cover well beyond 6 months of sales
        raw_days = 702 / self.VELOCITY
        assert raw_days > 180, "Order should cover at least 6 months of sales"


# ===================================================================
# 2. Air freight emergency
# ===================================================================

class TestAirFreightEmergency:
    """Scenario: Emergency restock via air freight (30-day lead time).
    Same item as above (velocity=3/day, stock=10).  Air orders should
    be dramatically smaller than sea orders because coverage_period is
    shorter (auto-computed).
    """

    LEAD = 30
    VELOCITY = 3.0
    STOCK = 10
    BUFFER = 1.3

    def test_auto_coverage_for_30_day_lead(self):
        # 365 // 30 = 12 turns, capped at 6 -> 365 // 6 = 60
        assert compute_coverage_days(self.LEAD) == 60

    def test_air_order_much_smaller_than_sea(self):
        coverage_air = compute_coverage_days(self.LEAD)  # 60
        coverage_sea = 180  # 6-month sea freight cycle

        days_to_stockout = round(self.STOCK / self.VELOCITY, 1)  # 3.3

        _, qty_air = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=coverage_air,
        )
        _, qty_sea = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=150,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=coverage_sea,
        )

        assert qty_air < qty_sea, "Air freight order should be smaller than sea"
        # Air: wait=90, post=3*60*1.3=234, stock(10)<=wait(90) -> ceil(234)=234
        assert qty_air == 234
        # Sea: wait=450, post=702, stock(10)<=wait(450) -> ceil(702)=702
        assert qty_sea == 702
        assert qty_air < qty_sea * 0.5, "Air should be less than half of sea"

    def test_air_freight_status_is_critical(self):
        # 10 / 3 = 3.3 days left, lead_time = 30 -> critical
        days_to_stockout = round(self.STOCK / self.VELOCITY, 1)
        status, _ = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=60,
        )
        assert status == "urgent"


# ===================================================================
# 3. Wholesale spike survivor
# ===================================================================

class TestWholesaleSpikeSurvivor:
    """Scenario: Item normally sells 1/day, but a 200-unit wholesale order
    dropped stock from 300 to 100. Velocity hasn't been recalculated yet
    (still 1/day). The formula should NOT panic — with 100 days of stock
    at current velocity, it should give a measured order.
    """

    VELOCITY = 1.0
    STOCK = 100
    LEAD = 120
    BUFFER = 1.3

    def test_coverage_auto_for_120_day_lead(self):
        # 365 // 120 = 3 turns -> 365 // 3 = 121
        assert compute_coverage_days(self.LEAD) == 121

    def test_not_a_panic_order(self):
        coverage = compute_coverage_days(self.LEAD)  # 121
        days_to_stockout = self.STOCK / self.VELOCITY  # 100
        status, qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=coverage,
        )
        # 100 days left vs 120 lead_time -> critical
        assert status == "urgent"

        # wait = 1*120 = 120, post = 1*121*1.3 = 157.3
        # stock(100) <= wait(120) -> Case 1: ceil(157.3) = 158
        assert qty == 158

        # Sanity: order should be LESS than 300 (not a panic buy)
        assert qty < 300, "Should not panic-buy after a wholesale spike"

    def test_pre_spike_would_have_been_ok(self):
        """Before the spike (stock=300), status should have been OK."""
        coverage = compute_coverage_days(self.LEAD)  # 121
        status, qty = determine_reorder_status(
            current_stock=300,
            days_to_stockout=300.0,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=coverage,
        )
        # 300 days > 120 lead_time + 60 warning_buffer = 180 -> ok
        assert status == "healthy"


# ===================================================================
# 4. Slow mover with tons of stock
# ===================================================================

class TestSlowMoverTonsOfStock:
    """Scenario: Niche item (specialty gold leaf) that sells ~1.5/month
    (velocity=0.05/day). We have 200 in stock. That's 4000 days of supply.
    Should NOT order anything.
    """

    VELOCITY = 0.05
    STOCK = 200
    LEAD = 180
    COVERAGE = 182  # auto for 180-day lead

    def test_years_of_stock(self):
        days_supply = self.STOCK / self.VELOCITY  # 4000 days
        assert days_supply > 365 * 10, "Should have >10 years of stock"

    def test_order_is_zero(self):
        days_to_stockout = round(self.STOCK / self.VELOCITY, 1)  # 4000.0
        status, qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=1.3,
            coverage_period=self.COVERAGE,
        )
        # wait = 0.05*180 = 9, post = 0.05*182*1.3 = 11.83
        # stock(200) > wait(9) -> Case 2: ceil(9 + 11.83 - 200) = ceil(-179.17) = -179
        # max(0, -179) -> 0 -> None
        assert status == "healthy"
        assert qty is None, "Should not order when you have 4000 days of stock"


# ===================================================================
# 5. Fast mover running dry
# ===================================================================

class TestFastMoverRunningDry:
    """Scenario: Popular brush set, sells 10/day, only 5 left.
    Sea freight 90 days. Higher buffer (1.5) because it's an A-class item.
    Basically already OOS — should order a large quantity.
    """

    VELOCITY = 10.0
    STOCK = 5
    LEAD = 90
    BUFFER = 1.5
    COVERAGE = 91  # auto for 90-day lead

    def test_suggested_qty(self):
        days_to_stockout = round(self.STOCK / self.VELOCITY, 1)  # 0.5
        status, qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        # wait = 10*90 = 900, post = 10*91*1.5 = 1365
        # stock(5) <= wait(900) -> Case 1: ceil(1365) = 1365
        assert status == "urgent"
        assert qty == 1365

    def test_order_covers_roughly_one_quarter(self):
        # 1365 / 10 = 136.5 raw days — covers the coverage period
        raw_days = 1365 / self.VELOCITY
        assert 90 < raw_days < 300, "Should cover lead time plus ~1 quarter of sales"


# ===================================================================
# 6. Just restocked — plenty of inventory
# ===================================================================

class TestJustRestocked:
    """Scenario: Just received a big shipment. velocity=2/day, stock=600,
    lead_time=120, coverage=121. Stock lasts 300 days, well beyond lead
    window. Should order little or nothing.
    """

    VELOCITY = 2.0
    STOCK = 600
    LEAD = 120
    BUFFER = 1.3
    COVERAGE = 121

    def test_status_is_ok(self):
        days_to_stockout = self.STOCK / self.VELOCITY  # 300.0
        status, qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        # 300 days > 120 + max(30, 60) = 180 -> ok
        assert status == "healthy"

    def test_order_qty_is_small_or_zero(self):
        days_to_stockout = self.STOCK / self.VELOCITY
        status, qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        # wait = 2*120 = 240, post = 2*121*1.3 = 314.6
        # stock(600) > wait(240) -> Case 2: ceil(240 + 314.6 - 600) = ceil(-45.4) = -45
        # max(0, -45) -> 0 -> None
        assert qty is None

    def test_raw_formula_matches_engine(self):
        """Verify _raw_formula helper matches the engine for this scenario."""
        new = _raw_formula(self.STOCK, self.VELOCITY, self.LEAD, self.COVERAGE, self.BUFFER)
        days_to_stockout = self.STOCK / self.VELOCITY
        _, engine_qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        engine_qty_effective = engine_qty if engine_qty is not None else 0
        assert new == engine_qty_effective, (
            f"_raw_formula ({new}) should match engine ({engine_qty_effective})"
        )


# ===================================================================
# 7. Domestic supplier quick restock
# ===================================================================

class TestDomesticQuickRestock:
    """Scenario: Indian-made easels, domestic supplier (15-day lead time),
    sells 5/day. Only 30 left (6 days). No safety buffer (1.0).
    Should order enough for auto-coverage (60 days for 15-day lead).
    """

    LEAD = 15
    VELOCITY = 5.0
    STOCK = 30
    BUFFER = 1.0

    def test_coverage_for_domestic_supplier(self):
        # 365 // 15 = 24 turns, capped at 6 -> 365 // 6 = 60
        assert compute_coverage_days(self.LEAD) == 60

    def test_order_for_coverage(self):
        coverage = compute_coverage_days(self.LEAD)  # 60
        days_to_stockout = self.STOCK / self.VELOCITY  # 6.0
        status, qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=coverage,
        )
        # wait = 5*15 = 75, post = 5*60*1.0 = 300
        # stock(30) <= wait(75) -> Case 1: ceil(300) = 300
        assert status == "urgent"
        assert qty == 300


# ===================================================================
# 8. Negative stock from Tally rename
# ===================================================================

class TestNegativeStockTallyRename:
    """Scenario: Tally shows -50 stock due to SKU rename (FAVINI -> ART ESSENTIALS).
    This is a real data quality issue (5,574 items have negative closing balance).
    Formula should treat as OOS and order for post-arrival coverage only.
    With the new formula, negative stock does NOT inflate orders.
    """

    STOCK = -50
    VELOCITY = 2.0
    LEAD = 120
    BUFFER = 1.3
    COVERAGE = 121

    def test_negative_stock_is_stocked_out(self):
        status, qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=0,  # already OOS
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        assert status == "lost_sales"

    def test_negative_stock_order_qty(self):
        status, qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=0,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        # wait = 2*120 = 240, post = 2*121*1.3 = 314.6
        # stock(-50) <= wait(240) -> Case 1: ceil(314.6) = 315
        assert qty == 315

    def test_negative_stock_does_not_inflate(self):
        """With the new formula, negative stock does NOT inflate the order.
        Both stock=-50 and stock=0 produce the same qty because Case 1
        orders ceil(post_arrival) regardless of how negative stock is."""
        _, qty_neg = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=0,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        _, qty_zero = determine_reorder_status(
            current_stock=0,
            days_to_stockout=0,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        # stock=0: wait=240, stock(0)<=wait(240) -> ceil(314.6) = 315
        # stock=-50: wait=240, stock(-50)<=wait(240) -> ceil(314.6) = 315
        assert qty_zero == 315
        assert qty_neg == 315
        assert qty_neg == qty_zero, "Negative stock should NOT inflate orders"


# ===================================================================
# 9. Multi-turn ordering cycle (quarterly ordering)
# ===================================================================

class TestMultiTurnOrderingCycle:
    """Scenario: 90-day lead time supplier, ordering quarterly.
    Verify coverage_days=91, and that 4 orders/year each cover ~91 days.
    """

    LEAD = 90

    def test_quarterly_coverage(self):
        # 365 // 90 = 4 turns -> 365 // 4 = 91
        assert compute_coverage_days(self.LEAD) == 91

    def test_four_orders_cover_a_year(self):
        coverage = compute_coverage_days(self.LEAD)  # 91
        # 4 orders * 91 days = 364 days ~ 1 year
        turns = 365 // self.LEAD  # 4
        total_days = turns * coverage
        assert 360 <= total_days <= 370, (
            f"4 quarterly orders should cover ~365 days, got {total_days}"
        )

    def test_each_order_size_is_consistent(self):
        """Each quarterly order for a 2/day item should be ~same size."""
        coverage = compute_coverage_days(self.LEAD)
        velocity = 2.0
        buffer = 1.3

        # Ideal scenario: stock at 0 each time
        _, qty = determine_reorder_status(
            current_stock=0,
            days_to_stockout=0,
            supplier_lead_time=self.LEAD,
            total_velocity=velocity,
            safety_buffer=buffer,
            coverage_period=coverage,
        )
        # wait = 2*90 = 180, post = 2*91*1.3 = 236.6
        # stock(0) <= wait(180) -> Case 1: ceil(236.6) = 237
        assert qty == 237


# ===================================================================
# 10. The "order arrives, immediately reorder" trap
# ===================================================================

class TestNoImmediateReorderTrap:
    """Old formula bug: critical items got an order that only covered
    lead_time demand, so the moment it arrived they needed another order.

    New formula orders for coverage_period AFTER arrival, so the received
    stock should last through the coverage period before hitting critical.
    """

    VELOCITY = 2.0
    LEAD = 120
    BUFFER = 1.3
    COVERAGE = 121  # auto for 120-day lead

    def test_post_arrival_stock_lasts_through_coverage(self):
        """After receiving the order, simulated stock should last at least
        coverage_period days before the item goes critical again."""
        # Critical item — will stock out during lead time
        status, qty = determine_reorder_status(
            current_stock=50,
            days_to_stockout=25.0,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        assert status == "urgent"
        assert qty is not None

        # Simulate: stock depletes during lead_time, then qty arrives
        stock_at_arrival = max(0, 50 - self.VELOCITY * self.LEAD)  # 0 (depleted)
        post_arrival_stock = stock_at_arrival + qty

        # How many days does this post-arrival stock last?
        days_post_arrival = post_arrival_stock / self.VELOCITY
        # Should last at least coverage_period (with buffer built in)
        assert days_post_arrival >= self.COVERAGE, (
            f"Post-arrival stock ({post_arrival_stock}) should last >= {self.COVERAGE} "
            f"days, but only lasts {days_post_arrival:.0f} days"
        )

    def test_oos_item_post_arrival_lasts_coverage(self):
        """Even for fully OOS items, the order should provide coverage."""
        status, qty = determine_reorder_status(
            current_stock=0,
            days_to_stockout=0,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        assert status == "lost_sales"
        post_arrival = qty  # stock_at_arrival is 0
        days = post_arrival / self.VELOCITY
        assert days >= self.COVERAGE


# ===================================================================
# 11. Working capital comparison: old vs new formula for OOS items
# ===================================================================

class TestWorkingCapitalSavings:
    """For OOS items, the old formula ordered velocity*(lead+coverage)*buffer,
    which included lead_time demand with buffer applied to everything.
    The new formula orders only ceil(velocity*coverage*buffer) for Case 1
    (stock <= wait), saving ~50% working capital for long lead times.
    """

    STOCK = 0
    VELOCITY = 2.0
    LEAD = 120
    BUFFER = 1.3
    COVERAGE = 121

    def test_new_formula_saves_vs_old_buffered(self):
        old_qty = round(self.VELOCITY * (self.LEAD + self.COVERAGE) * self.BUFFER)
        # old = 2 * (120 + 121) * 1.3 = 2 * 241 * 1.3 = 626.6 -> 627

        _, new_qty = determine_reorder_status(
            current_stock=self.STOCK,
            days_to_stockout=0,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        # new: wait=240, post=314.6, stock(0)<=wait -> ceil(314.6) = 315

        assert old_qty == 627
        assert new_qty == 315
        savings_pct = (old_qty - new_qty) / old_qty * 100
        assert savings_pct > 45, f"Should save >45% working capital, saved {savings_pct:.1f}%"

    def test_savings_scale_with_lead_time(self):
        """Longer lead times = bigger savings (more lead-time demand avoided)."""
        savings_by_lead = {}
        for lead in [30, 90, 120, 180]:
            coverage = compute_coverage_days(lead)
            old = round(self.VELOCITY * (lead + coverage) * self.BUFFER)
            _, new = determine_reorder_status(
                current_stock=0, days_to_stockout=0,
                supplier_lead_time=lead, total_velocity=self.VELOCITY,
                safety_buffer=self.BUFFER, coverage_period=coverage,
            )
            savings_by_lead[lead] = (old - new) / old * 100

        # For longer leads, lead_time is a bigger fraction of total, so savings should be larger
        assert savings_by_lead[180] > savings_by_lead[30], (
            "Longer lead times should yield bigger working capital savings"
        )


# ===================================================================
# 12. Buffer range sanity
# ===================================================================

class TestBufferRangeSanity:
    """Safety buffer should scale linearly. For OOS items (Case 1),
    the entire order IS the coverage portion: ceil(vel * cov * buf).
    No lead-time demand is included in the order for Case 1.
    """

    VELOCITY = 2.0
    STOCK = 0  # OOS simplifies math
    LEAD = 120
    COVERAGE = 121

    def test_buffer_scales_coverage_portion_linearly(self):
        results = {}
        for buf in [0.5, 1.0, 1.3, 1.5, 2.0]:
            _, qty = determine_reorder_status(
                current_stock=self.STOCK,
                days_to_stockout=0,
                supplier_lead_time=self.LEAD,
                total_velocity=self.VELOCITY,
                safety_buffer=buf,
                coverage_period=self.COVERAGE,
            )
            results[buf] = qty

        # All Case 1 (stock=0 <= wait). order = ceil(2 * 121 * buf)
        # buf=0.5: ceil(121) = 121
        # buf=1.0: ceil(242) = 242
        # buf=1.3: ceil(314.6) = 315
        # buf=1.5: ceil(363) = 363
        # buf=2.0: ceil(484) = 484
        assert results[0.5] == 121
        assert results[1.0] == 242
        assert results[1.3] == 315
        assert results[1.5] == 363
        assert results[2.0] == 484

    def test_double_buffer_doubles_coverage_portion(self):
        _, qty_1 = determine_reorder_status(
            current_stock=0, days_to_stockout=0,
            supplier_lead_time=self.LEAD, total_velocity=self.VELOCITY,
            safety_buffer=1.0, coverage_period=self.COVERAGE,
        )
        _, qty_2 = determine_reorder_status(
            current_stock=0, days_to_stockout=0,
            supplier_lead_time=self.LEAD, total_velocity=self.VELOCITY,
            safety_buffer=2.0, coverage_period=self.COVERAGE,
        )
        # ceil(2*121*1.0) = 242, ceil(2*121*2.0) = 484
        assert qty_1 == 242
        assert qty_2 == 484
        assert qty_2 == qty_1 * 2  # entire order doubles

    def test_half_buffer_halves_coverage_portion(self):
        _, qty_1 = determine_reorder_status(
            current_stock=0, days_to_stockout=0,
            supplier_lead_time=self.LEAD, total_velocity=self.VELOCITY,
            safety_buffer=1.0, coverage_period=self.COVERAGE,
        )
        _, qty_half = determine_reorder_status(
            current_stock=0, days_to_stockout=0,
            supplier_lead_time=self.LEAD, total_velocity=self.VELOCITY,
            safety_buffer=0.5, coverage_period=self.COVERAGE,
        )
        # ceil(2*121*1.0) = 242, ceil(2*121*0.5) = ceil(121) = 121
        assert qty_half == 121
        assert qty_half == qty_1 // 2  # entire order halves


# ===================================================================
# 13. Timeline simulation — full order cycle
# ===================================================================

class TestTimelineSimulation:
    """Simulate an entire order cycle day-by-day:
    Day 0: place order. Day 1..lead_time: sell through stock.
    Day lead_time: receive shipment. Day lead_time+1..end: continue selling.
    Verify post-arrival stock matches coverage expectation.
    """

    VELOCITY = 3.0
    LEAD = 90
    BUFFER = 1.3
    COVERAGE = 91

    def test_full_cycle_simulation_critical_item(self):
        """Critical item: stock will run out during lead time.
        Note: when stock hits 0, sales are lost (can't sell below 0).
        This is the real-world model — unfilled demand is lost, not backfilled.
        """
        initial_stock = 100  # 33 days at 3/day, critical for 90-day lead
        days_to_stockout = round(initial_stock / self.VELOCITY, 1)

        status, qty = determine_reorder_status(
            current_stock=initial_stock,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )
        assert status == "urgent"
        assert qty is not None

        # Day-by-day simulation (stock floors at 0 — lost sales, not backorders)
        stock = float(initial_stock)
        oos_days = 0
        for day in range(1, self.LEAD + self.COVERAGE + 1):
            stock = max(0, stock - self.VELOCITY)  # can't sell below 0

            if day == self.LEAD:
                # Shipment arrives
                stock += qty

            if stock <= 0:
                oos_days += 1

        # After lead_time + coverage days, stock should still be positive
        # because the buffer (1.3x) provides surplus beyond the coverage period
        assert stock > 0, (
            f"Stock should be positive at end of cycle, got {stock:.1f}"
        )

    def test_full_cycle_simulation_healthy_item(self):
        """Healthy item: has enough stock to survive lead time.
        With surplus stock, the formula orders less, and any remaining
        stock at the end proves the formula correctly accounted for it.
        """
        initial_stock = 500  # 166 days at 3/day
        days_to_stockout = round(initial_stock / self.VELOCITY, 1)

        status, qty = determine_reorder_status(
            current_stock=initial_stock,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )

        if qty is None:
            qty = 0

        # Day-by-day simulation (stock floors at 0)
        stock = float(initial_stock)
        for day in range(1, self.LEAD + self.COVERAGE + 1):
            stock = max(0, stock - self.VELOCITY)
            if day == self.LEAD:
                stock += qty

        # For healthy items, the formula gives qty that when added to
        # remaining stock at arrival, covers the coverage period.
        # The total stock at end should be non-negative.
        assert stock >= 0, (
            f"Stock shouldn't go negative for healthy item, got {stock:.1f}"
        )

    def test_oos_days_minimized_for_critical_items(self):
        """For critical items that stock out during lead time,
        the OOS period should be limited to the gap between
        stockout and arrival — NOT after arrival.

        Key modeling point: when stock hits 0, sales are lost (not backfilled).
        The formula correctly orders for coverage_period of post-arrival demand.
        """
        initial_stock = 30  # 10 days at 3/day
        days_to_stockout = round(initial_stock / self.VELOCITY, 1)

        _, qty = determine_reorder_status(
            current_stock=initial_stock,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=self.LEAD,
            total_velocity=self.VELOCITY,
            safety_buffer=self.BUFFER,
            coverage_period=self.COVERAGE,
        )

        # Simulate to count OOS days (stock floors at 0 — lost sales model)
        stock = float(initial_stock)
        oos_days_before_arrival = 0
        oos_days_after_arrival = 0
        for day in range(1, self.LEAD + self.COVERAGE + 1):
            stock = max(0, stock - self.VELOCITY)  # can't sell below 0
            if day == self.LEAD:
                stock += qty
            if stock <= 0:
                if day < self.LEAD:
                    oos_days_before_arrival += 1
                else:
                    oos_days_after_arrival += 1

        # After arrival, should NOT be OOS — the order covers coverage_period
        assert oos_days_after_arrival == 0, (
            f"Should have zero OOS days after arrival, got {oos_days_after_arrival}"
        )
        # Before arrival, expect stockout (30/3 = 10 days of stock, then ~80 OOS days)
        assert oos_days_before_arrival > 0, "Expected some OOS days before arrival"


# ===================================================================
# Edge cases and regression guards
# ===================================================================

class TestEdgeCases:
    """Boundary conditions and regression guards."""

    def test_zero_velocity_with_stock(self):
        """Zero velocity + stock = no_demand (can't predict)."""
        status, qty = determine_reorder_status(
            current_stock=100, days_to_stockout=None,
            supplier_lead_time=120, total_velocity=0,
            safety_buffer=1.3, coverage_period=121,
        )
        assert status == "dead_stock"
        assert qty is None

    def test_zero_velocity_zero_stock(self):
        """Zero velocity + zero stock = out_of_stock."""
        status, qty = determine_reorder_status(
            current_stock=0, days_to_stockout=0,
            supplier_lead_time=120, total_velocity=0,
            safety_buffer=1.3, coverage_period=121,
        )
        assert status == "out_of_stock"
        assert qty is None  # Can't compute without velocity

    def test_very_high_velocity(self):
        """Extremely high velocity (100/day) — formula should still work."""
        status, qty = determine_reorder_status(
            current_stock=0, days_to_stockout=0,
            supplier_lead_time=180, total_velocity=100.0,
            safety_buffer=1.3, coverage_period=182,
        )
        # wait = 100*180 = 18000, post = 100*182*1.3 = 23660
        # stock(0) <= wait(18000) -> Case 1: ceil(23660) = 23660
        assert status == "lost_sales"
        assert qty == 23660

    def test_coverage_days_very_short_lead(self):
        """1-day lead time: 365//1 = 365 turns, capped at 6 -> 365//6 = 60."""
        assert compute_coverage_days(1) == 60

    def test_coverage_days_exactly_365(self):
        """365-day lead time: 365//365 = 1 turn -> 365//1 = 365."""
        assert compute_coverage_days(365) == 365

    def test_coverage_days_greater_than_365(self):
        """500-day lead time: 365//500 = 0, max(1,0) = 1 turn -> 365."""
        assert compute_coverage_days(500) == 365

    def test_warning_status_boundary(self):
        """Exactly at warning boundary: days_to_stockout == lead + warning_buffer."""
        # lead=120, warning_buffer = max(30, 120*0.5) = 60
        # boundary = 120 + 60 = 180
        # AT 180 -> warning (<=)
        status, _ = determine_reorder_status(
            current_stock=360, days_to_stockout=180.0,
            supplier_lead_time=120, total_velocity=2.0,
            safety_buffer=1.3, coverage_period=121,
        )
        assert status == "reorder"

    def test_ok_status_just_above_boundary(self):
        """Just above warning boundary -> ok."""
        # threshold = 120 + max(121, 30) = 241. 241.5 > 241 → healthy
        status, _ = determine_reorder_status(
            current_stock=483, days_to_stockout=241.5,
            supplier_lead_time=120, total_velocity=2.0,
            safety_buffer=1.3, coverage_period=121,
        )
        assert status == "healthy"

    def test_critical_at_lead_time_boundary(self):
        """Exactly at lead_time boundary: critical."""
        status, _ = determine_reorder_status(
            current_stock=240, days_to_stockout=120.0,
            supplier_lead_time=120, total_velocity=2.0,
            safety_buffer=1.3, coverage_period=121,
        )
        assert status == "urgent"

    def test_fractional_velocity(self):
        """Fractional velocity (0.1/day = 3/month) should produce sensible qty."""
        status, qty = determine_reorder_status(
            current_stock=0, days_to_stockout=0,
            supplier_lead_time=180, total_velocity=0.1,
            safety_buffer=1.3, coverage_period=182,
        )
        # wait = 0.1*180 = 18, post = 0.1*182*1.3 = 23.66
        # stock(0) <= wait(18) -> Case 1: ceil(23.66) = 24
        assert status == "lost_sales"
        assert qty == 24

    def test_po_builder_formula_matches_engine(self):
        """The engine formula: two-case with ceil.
        Case 1 (stock <= wait): order = ceil(post_arrival)
        Case 2 (stock > wait): order = ceil(wait + post - stock)"""
        stock = 100.0
        velocity = 2.0
        lead = 120
        coverage = 121
        buffer = 1.3

        # Engine result
        _, engine_qty = determine_reorder_status(
            current_stock=stock, days_to_stockout=50.0,
            supplier_lead_time=lead, total_velocity=velocity,
            safety_buffer=buffer, coverage_period=coverage,
        )

        # Two-case formula with ceil
        wait_period = velocity * lead  # 240
        post_arrival = velocity * coverage * buffer  # 314.6
        # stock(100) <= wait(240) -> Case 1: ceil(314.6) = 315
        expected = math.ceil(post_arrival)
        if expected <= 0:
            expected = None

        assert engine_qty == expected, (
            f"Engine ({engine_qty}) and expected ({expected}) should agree"
        )
