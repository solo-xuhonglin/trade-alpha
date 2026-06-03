"""Verify all strategies."""
import requests
r = requests.get("http://localhost:8000/api/strategies")
strategies = r.json()
for s in strategies:
    print(f"  {s['name']}: max_pos={s['max_positions']}, max_pct={s['max_position_pct']}, min_order={s['min_order_value']}, min_hold={s['min_hold_days']}, buy/sell={s['buy_threshold']}/{s['sell_threshold']}")
print(f"\nTotal: {len(strategies)} strategies")