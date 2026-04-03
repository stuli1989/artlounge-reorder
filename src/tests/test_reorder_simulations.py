"""
Day-by-day simulations that validate the reorder formula produces correct
business outcomes over full order cycles.

Each test plays out a scenario forward in time, verifying that order
quantities lead to appropriate coverage after arrival.

New formula (F15):
    wait_period  = velocity * lead_time          (no buffer)
    post_arrival = velocity * coverage * buffer  (buffer on coverage only)

    if stock <= wait_period:
        order = ceil(post_arrival)               # wait gap is sunk cost
    else:
        order = ceil(wait_period + post_arrival - stock)  # deduct surplus

Uses math.ceil instead of round. If result <= 0, returns None.
"""
import math
from engine.reorder import determine_reorder_status, compute_coverage_days


# ---------------------------------------------------------------------------
# Helper: simulate daily sales from a starting stock
# ---------------------------------------------------------------------------

def simulate_daily_sales(starting_stock: float, velocity: float, days: int) -> float:
    """Simulate selling at a constant velocity for N days.
    Stock cannot go below 0 (can't sell what you don't have).
    Returns remaining stock.
    """
    stock = starting_stock
    for _ in range(days):
        sold = min(stock, velocity)
        stock -= sold
    return round(stock, 2)


# ---------------------------------------------------------------------------
# Simulation 1: Full Order Cycle — Critical Item
# ---------------------------------------------------------------------------

def test_sim1_critical_item_full_cycle():
    """
    Day 0: stock=100, velocity=2/day, lead_time=120, coverage=180, buffer=1.3
    Stock runs out at day 50. Order arrives day 120 with suggested qty.
    Verify: arrived qty provides >= 180 days of coverage.
    """
    stock = 100
    velocity = 2.0
    lead_time = 120
    coverage = 180
    buffer = 1.3

    days_to_stockout = stock / velocity  # 50 days
    assert days_to_stockout == 50.0

    status, suggested_qty = determine_reorder_status(
        current_stock=stock,
        days_to_stockout=days_to_stockout,
        supplier_lead_time=lead_time,
        total_velocity=velocity,
        safety_buffer=buffer,
        coverage_period=coverage,
    )

    assert status == "urgent", f"Expected urgent, got {status}"
    assert suggested_qty is not None

    # Simulate: sell for 120 days (order transit period)
    stock_at_arrival = simulate_daily_sales(stock, velocity, lead_time)
    assert stock_at_arrival == 0, "Should be OOS well before arrival"

    # Order arrives
    new_stock = stock_at_arrival + suggested_qty

    # How many days of coverage does the arrived stock provide?
    days_of_coverage = new_stock / velocity
    assert days_of_coverage >= coverage, (
        f"Expected >= {coverage} days of coverage after arrival, "
        f"got {days_of_coverage:.1f} days (qty={suggested_qty})"
    )

    # New formula: stock(100) <= wait_period(240), so order = ceil(post_arrival)
    # post_arrival = velocity * coverage * buffer = 2 * 180 * 1.3 = 468
    expected_qty = math.ceil(velocity * coverage * buffer)  # 468
    assert suggested_qty == expected_qty, (
        f"Expected {expected_qty}, got {suggested_qty}"
    )


# ---------------------------------------------------------------------------
# Simulation 2: Full Order Cycle — OK Item (plenty of stock)
# ---------------------------------------------------------------------------

def test_sim2_ok_item_full_cycle():
    """
    Day 0: stock=500, velocity=2/day, lead_time=120, coverage=180, buffer=1.3
    Stock survives until arrival. Verify: stock_at_arrival + order >= 180 days.
    """
    stock = 500
    velocity = 2.0
    lead_time = 120
    coverage = 180
    buffer = 1.3

    days_to_stockout = stock / velocity  # 250 days
    assert days_to_stockout == 250.0

    status, suggested_qty = determine_reorder_status(
        current_stock=stock,
        days_to_stockout=days_to_stockout,
        supplier_lead_time=lead_time,
        total_velocity=velocity,
        safety_buffer=buffer,
        coverage_period=coverage,
    )

    # dts=250 < lead_time+max(coverage,30)=300 → reorder (stock won't last full horizon)
    assert status == "reorder"
    assert suggested_qty is not None

    # Simulate: sell for 120 days
    stock_at_arrival = simulate_daily_sales(stock, velocity, lead_time)
    assert stock_at_arrival == 260.0, f"Expected 260, got {stock_at_arrival}"

    # Order arrives
    new_stock = stock_at_arrival + suggested_qty

    # Verify coverage
    days_of_coverage = new_stock / velocity
    assert days_of_coverage >= coverage, (
        f"Expected >= {coverage} days, got {days_of_coverage:.1f} "
        f"(stock_at_arrival={stock_at_arrival}, qty={suggested_qty})"
    )

    # New formula: stock(500) > wait_period(240), so deduct surplus
    # order = ceil(wait + post_arrival - stock) = ceil(240 + 468 - 500) = ceil(208) = 208
    expected = math.ceil(velocity * lead_time + velocity * coverage * buffer - stock)
    assert suggested_qty == expected, (
        f"For OK item, expected {expected}, got {suggested_qty}"
    )


# ---------------------------------------------------------------------------
# Simulation 3: Full Order Cycle — Out of Stock
# ---------------------------------------------------------------------------

def test_sim3_oos_item_not_inflated():
    """
    Day 0: stock=0, velocity=2/day, lead_time=120, coverage=180, buffer=1.3
    No sales during transit (nothing to sell).
    New formula: stock(0) <= wait_period(240), so order = ceil(post_arrival only).
    Lead-time gap is sunk cost — order only covers post-arrival period.
    """
    stock = 0
    velocity = 2.0
    lead_time = 120
    coverage = 180
    buffer = 1.3

    status, suggested_qty = determine_reorder_status(
        current_stock=stock,
        days_to_stockout=0,
        supplier_lead_time=lead_time,
        total_velocity=velocity,
        safety_buffer=buffer,
        coverage_period=coverage,
    )

    assert status == "lost_sales"
    assert suggested_qty is not None

    # Simulate: no sales during transit (stock is 0)
    stock_at_arrival = simulate_daily_sales(stock, velocity, lead_time)
    assert stock_at_arrival == 0

    # Order arrives
    new_stock = stock_at_arrival + suggested_qty
    days_of_coverage = new_stock / velocity

    # New formula: stock(0) <= wait(240) → order = ceil(velocity * coverage * buffer)
    # = ceil(2 * 180 * 1.3) = ceil(468) = 468
    expected = math.ceil(velocity * coverage * buffer)
    assert suggested_qty == expected, (
        f"OOS order should be {expected}, got {suggested_qty}"
    )

    # Coverage should be >= coverage_period (post-arrival only)
    assert days_of_coverage >= coverage, (
        f"Must cover at least {coverage} days, got {days_of_coverage:.1f}"
    )


# ---------------------------------------------------------------------------
# Simulation 4: Repeated Ordering Cycles
# ---------------------------------------------------------------------------

def test_sim4_repeated_order_cycles():
    """
    Simulate 3 consecutive order cycles for a sea freight item.
    velocity=2/day, lead_time=150, coverage=182, buffer=1.3
    Start with stock=0. The first cycle orders more (includes lead demand
    for OOS item). Subsequent cycles stabilize.
    """
    velocity = 2.0
    lead_time = 150
    coverage = 182
    buffer = 1.3

    stock = 0.0
    cycle_runways = []

    for cycle in range(3):
        # Determine order
        days_to_stockout = 0 if stock <= 0 else stock / velocity
        status, order_qty = determine_reorder_status(
            current_stock=stock,
            days_to_stockout=days_to_stockout,
            supplier_lead_time=lead_time,
            total_velocity=velocity,
            safety_buffer=buffer,
            coverage_period=coverage,
        )

        assert order_qty is not None, f"Cycle {cycle}: no order suggested"

        # Simulate lead_time days of sales while waiting
        stock_at_arrival = simulate_daily_sales(stock, velocity, lead_time)

        # Order arrives
        stock = stock_at_arrival + order_qty

        # How long does this stock last?
        runway = stock / velocity
        cycle_runways.append(runway)

        # Simulate consuming stock until critical (days_left <= lead_time)
        # i.e., consume until we'd place the next order
        days_to_consume = max(0, runway - lead_time)
        stock = simulate_daily_sales(stock, velocity, int(days_to_consume))

    # Each cycle should provide at least coverage days of runway
    for i, runway in enumerate(cycle_runways):
        assert runway >= coverage, (
            f"Cycle {i}: runway {runway:.1f} days < {coverage} day target"
        )

    # After the first cycle (which is larger due to OOS start), subsequent
    # cycles should stabilize
    stable_runways = cycle_runways[1:]
    min_runway = min(stable_runways)
    max_runway = max(stable_runways)
    assert max_runway - min_runway < 50, (
        f"Stable runway variation too large: min={min_runway:.1f}, max={max_runway:.1f}. "
        f"Runways: {[f'{r:.1f}' for r in stable_runways]}"
    )

    # NO death spiral: each post-arrival stock should NOT be near zero
    for i, runway in enumerate(cycle_runways):
        assert runway > lead_time, (
            f"Cycle {i}: death spiral detected — runway {runway:.1f} days "
            f"<= lead_time {lead_time} days. Would need immediate reorder."
        )


# ---------------------------------------------------------------------------
# Simulation 5: Old Formula Death Spiral
# ---------------------------------------------------------------------------

def test_sim5_old_formula_over_orders():
    """
    Demonstrate that the OLD formula (buffer on BOTH lead and coverage)
    orders more than the NEW formula (post-arrival only) for OOS items.
    """
    velocity = 2.0
    lead_time = 150
    coverage = 182
    buffer = 1.3
    stock = 0

    # New formula (current): stock(0) <= wait(300), order = ceil(post_arrival)
    status, new_qty = determine_reorder_status(
        current_stock=stock,
        days_to_stockout=0,
        supplier_lead_time=lead_time,
        total_velocity=velocity,
        safety_buffer=buffer,
        coverage_period=coverage,
    )

    # Old formula (buffer on both lead and coverage)
    old_qty = round(velocity * (lead_time + coverage) * buffer - stock)

    # New qty = ceil(velocity * coverage * buffer) = ceil(2*182*1.3) = ceil(473.2) = 474
    expected_new = math.ceil(velocity * coverage * buffer)
    assert new_qty == expected_new, f"New formula: expected {expected_new}, got {new_qty}"

    # Old qty: round(2 * (150 + 182) * 1.3) = round(863.2) = 863
    expected_old = round(velocity * (lead_time + coverage) * buffer)
    assert old_qty == expected_old

    # Quantify the excess: 863 - 474 = 389, pct = 389/474*100 = 82%
    excess_units = old_qty - new_qty
    excess_pct = (excess_units / new_qty) * 100

    assert excess_units > 0, "Old formula should order more than new"
    assert excess_pct > 10, (
        f"Old formula should be >10% more than new; got {excess_pct:.0f}%"
    )


# ---------------------------------------------------------------------------
# Simulation 6: Air vs Sea Decision Validation
# ---------------------------------------------------------------------------

def test_sim6_air_vs_sea():
    """
    velocity=5/day, stock=20 (4 days left):
    Compare sea freight (long lead, big order) vs air freight (fast, small order).
    """
    velocity = 5.0
    stock = 20
    buffer = 1.3
    days_to_stockout = stock / velocity  # 4 days

    # --- Sea freight ---
    sea_lead = 150
    sea_coverage = 182

    sea_status, sea_qty = determine_reorder_status(
        current_stock=stock,
        days_to_stockout=days_to_stockout,
        supplier_lead_time=sea_lead,
        total_velocity=velocity,
        safety_buffer=buffer,
        coverage_period=sea_coverage,
    )

    assert sea_status == "urgent"
    assert sea_qty is not None

    # Simulate sea: OOS by day 4, nothing to sell for 146 days
    sea_stock_at_arrival = simulate_daily_sales(stock, velocity, sea_lead)
    assert sea_stock_at_arrival == 0

    sea_post_arrival = sea_stock_at_arrival + sea_qty
    sea_runway = sea_post_arrival / velocity

    # Sea order should provide >= 182 days
    assert sea_runway >= sea_coverage, (
        f"Sea: {sea_runway:.0f} days coverage, need {sea_coverage}"
    )

    # --- Air freight ---
    air_lead = 30
    air_coverage = 60

    air_status, air_qty = determine_reorder_status(
        current_stock=stock,
        days_to_stockout=days_to_stockout,
        supplier_lead_time=air_lead,
        total_velocity=velocity,
        safety_buffer=buffer,
        coverage_period=air_coverage,
    )

    assert air_status == "urgent"
    assert air_qty is not None

    # Simulate air: OOS by day 4, nothing to sell for 26 days
    air_stock_at_arrival = simulate_daily_sales(stock, velocity, air_lead)
    assert air_stock_at_arrival == 0

    air_post_arrival = air_stock_at_arrival + air_qty
    air_runway = air_post_arrival / velocity

    # Air order should provide >= 60 days
    assert air_runway >= air_coverage, (
        f"Air: {air_runway:.0f} days coverage, need {air_coverage}"
    )

    # Air order is MUCH smaller than sea (less working capital locked)
    assert air_qty < sea_qty, (
        f"Air qty ({air_qty}) should be << sea qty ({sea_qty})"
    )
    ratio = sea_qty / air_qty
    assert ratio > 2.5, (
        f"Sea/air ratio only {ratio:.1f}x — expected >2.5x"
    )

    # New formula: stock(20) <= wait_period for both sea(750) and air(150)
    # So order = ceil(post_arrival) for both
    # Sea: ceil(5 * 182 * 1.3) = ceil(1183) = 1183
    # Air: ceil(5 * 60 * 1.3) = ceil(390) = 390
    expected_sea = math.ceil(velocity * sea_coverage * buffer)
    expected_air = math.ceil(velocity * air_coverage * buffer)
    assert sea_qty == expected_sea, f"Sea: expected {expected_sea}, got {sea_qty}"
    assert air_qty == expected_air, f"Air: expected {expected_air}, got {air_qty}"


# ---------------------------------------------------------------------------
# Simulation 7: Buffer Protects Against Demand Spike
# ---------------------------------------------------------------------------

def test_sim7_buffer_protects_against_spike():
    """
    With buffer=1.3, a 25% demand spike during lead time is partially
    mitigated. Buffer on coverage provides more stock, but since lead-time
    demand has no buffer, a 25% spike still shortens coverage. However,
    the buffered version provides significantly more coverage than unbuffered.
    """
    base_velocity = 2.0
    spike_velocity = 2.5  # 25% spike
    stock = 400
    lead_time = 120
    coverage = 180

    # --- WITH buffer=1.3 ---
    buffer = 1.3
    days_to_stockout = stock / base_velocity  # 200 days

    status_buffered, qty_buffered = determine_reorder_status(
        current_stock=stock,
        days_to_stockout=days_to_stockout,
        supplier_lead_time=lead_time,
        total_velocity=base_velocity,
        safety_buffer=buffer,
        coverage_period=coverage,
    )

    # Verify formula math: stock(400) > wait(240), so deduct surplus
    # demand_during_lead = 2 * 120 = 240  (NO buffer)
    # order_for_coverage = 2 * 180 * 1.3 = 468
    # suggested = ceil(240 + 468 - 400) = 308
    assert qty_buffered == 308, f"Expected 308, got {qty_buffered}"

    # But ACTUAL demand is 2.5/day during lead time
    real_stock_at_arrival = simulate_daily_sales(stock, spike_velocity, lead_time)
    assert real_stock_at_arrival == 100.0, (
        f"Expected 100 (400-2.5*120), got {real_stock_at_arrival}"
    )

    # After order arrives
    post_arrival_buffered = real_stock_at_arrival + qty_buffered
    # Coverage at spike velocity
    buffered_coverage = post_arrival_buffered / spike_velocity

    # --- WITHOUT buffer (buffer=1.0) ---
    status_unbuffered, qty_unbuffered = determine_reorder_status(
        current_stock=stock,
        days_to_stockout=days_to_stockout,
        supplier_lead_time=lead_time,
        total_velocity=base_velocity,
        safety_buffer=1.0,
        coverage_period=coverage,
    )

    # demand_during_lead = 2*120 = 240, cov = 2*180*1.0 = 360
    # stock(400) > wait(240), so ceil(240 + 360 - 400) = 200
    assert qty_unbuffered == 200, f"Expected 200, got {qty_unbuffered}"

    # Same spike scenario
    post_arrival_unbuffered = real_stock_at_arrival + qty_unbuffered
    unbuffered_coverage = post_arrival_unbuffered / spike_velocity

    # Buffer provides better coverage than no buffer
    assert buffered_coverage > unbuffered_coverage, (
        f"Buffered coverage ({buffered_coverage:.1f}) should exceed "
        f"unbuffered ({unbuffered_coverage:.1f})"
    )

    # Quantify the improvement
    improvement = buffered_coverage - unbuffered_coverage
    assert improvement > 30, (
        f"Buffer should provide >30 days improvement, got {improvement:.1f}"
    )


# ---------------------------------------------------------------------------
# Simulation 8: Negative Stock Handling
# ---------------------------------------------------------------------------

def test_sim8_negative_stock():
    """
    stock=-50 (Tally rename artifact), velocity=2, lead_time=120, coverage=180.
    Should be treated as stocked_out. New formula: stock(-50) <= wait(240),
    so order = ceil(post_arrival) only. Negative stock does NOT inflate the
    order anymore — the sunk-cost rule means we only order post-arrival stock.
    """
    stock = -50
    velocity = 2.0
    lead_time = 120
    coverage = 180
    buffer = 1.3

    status, suggested_qty = determine_reorder_status(
        current_stock=stock,
        days_to_stockout=0,
        supplier_lead_time=lead_time,
        total_velocity=velocity,
        safety_buffer=buffer,
        coverage_period=coverage,
    )

    assert status == "lost_sales"
    assert suggested_qty is not None

    # New formula: stock(-50) <= wait(240) → order = ceil(post_arrival)
    # = ceil(2 * 180 * 1.3) = ceil(468) = 468
    expected = math.ceil(velocity * coverage * buffer)
    assert suggested_qty == expected, (
        f"Negative stock order: expected {expected}, got {suggested_qty}"
    )

    # Scenario A: -50 is real backlog
    stock_if_real = stock + suggested_qty  # -50 + 468 = 418
    coverage_if_real = stock_if_real / velocity  # 209 days
    assert coverage_if_real >= coverage, (
        f"Even with real backlog: {coverage_if_real:.0f} days < {coverage} target"
    )

    # Scenario B: -50 is data artifact, real stock is 0
    stock_if_artifact = 0 + suggested_qty  # 468
    coverage_if_artifact = stock_if_artifact / velocity  # 234 days
    assert coverage_if_artifact >= coverage, (
        f"As artifact: {coverage_if_artifact:.0f} days < {coverage} target"
    )


# ---------------------------------------------------------------------------
# Simulation 9 (bonus): Coverage period auto-calculation integration
# ---------------------------------------------------------------------------

def test_sim9_auto_coverage_integration():
    """
    End-to-end: use compute_coverage_days to get coverage, then run the
    reorder formula, and simulate the cycle.
    """
    velocity = 3.0
    stock = 0
    lead_time = 120
    buffer = 1.3

    # Auto-calculate coverage from lead time
    coverage = compute_coverage_days(lead_time=lead_time)
    # 365 // 120 = 3 turns, 365 // 3 = 121 days
    assert coverage == 121

    status, qty = determine_reorder_status(
        current_stock=stock,
        days_to_stockout=0,
        supplier_lead_time=lead_time,
        total_velocity=velocity,
        safety_buffer=buffer,
        coverage_period=coverage,
    )

    assert status == "lost_sales"
    assert qty is not None

    # Order arrives after lead_time days (no sales during OOS)
    post_arrival = qty  # 0 stock + order
    runway = post_arrival / velocity

    assert runway >= coverage, (
        f"Auto-coverage {coverage} days, but runway is only {runway:.1f}"
    )

    # New formula: stock(0) <= wait(360) → order = ceil(post_arrival)
    # = ceil(3 * 121 * 1.3) = ceil(471.9) = 472
    expected = math.ceil(velocity * coverage * buffer)
    assert qty == expected, f"Expected {expected}, got {qty}"
