# T10: Velocity Calculation

## Prerequisites
- T09 completed (daily stock positions exist)

## Objective
Implement the velocity calculation: total outward units during in-stock periods / total in-stock days, separated by channel.

## File to Create

### `engine/velocity.py`

#### Main Function: `calculate_velocity(stock_item_name: str, daily_positions: list[dict]) -> dict`

**Core principle:** Velocity = demand during in-stock days only / count of in-stock days only.

Days where stock was zero or negative are excluded entirely — sales on those days are backorders and don't represent normal demand patterns.

```python
def calculate_velocity(stock_item_name, daily_positions):
    in_stock_days = [p for p in daily_positions if p['is_in_stock']]

    if not in_stock_days:
        return {
            'wholesale_velocity': 0,
            'online_velocity': 0,
            'total_velocity': 0,
            'total_in_stock_days': 0,
            'velocity_start_date': None,
            'velocity_end_date': None,
        }

    total_wholesale_out = sum(p['wholesale_out'] for p in in_stock_days)
    total_online_out = sum(p['online_out'] for p in in_stock_days)
    num_days = len(in_stock_days)

    wholesale_v = total_wholesale_out / num_days
    online_v = total_online_out / num_days

    return {
        'wholesale_velocity': round(wholesale_v, 4),
        'online_velocity': round(online_v, 4),
        'total_velocity': round(wholesale_v + online_v, 4),
        'total_in_stock_days': num_days,
        'velocity_start_date': in_stock_days[0]['position_date'],
        'velocity_end_date': in_stock_days[-1]['position_date'],
    }
```

## Test Case: Speedball Sealer

Expected values (approximate):
- In-stock days: 159 (68 in Period 1 + 91 in Period 2)
- Wholesale outward during in-stock days: ~253 units
- Online outward during in-stock days: ~32 units
- Wholesale velocity: ~1.6 units/day (~48/month)
- Online velocity: ~0.2 units/day (~6/month)
- Total velocity: ~1.8 units/day (~54/month)

Key: the out-of-stock period (Jun 8 - Nov 25, 171 days) is completely excluded from both numerator and denominator.

## Display Format Note
The dashboard displays velocities as "/month" (multiply by 30). The stored value is units/day.

## Acceptance Criteria
- [ ] Only in-stock days (closing_qty > 0) are used
- [ ] Wholesale and online velocities calculated separately
- [ ] Returns 0 for all velocities if no in-stock days
- [ ] Values rounded to 4 decimal places
- [ ] Start/end dates track the range of in-stock days used
