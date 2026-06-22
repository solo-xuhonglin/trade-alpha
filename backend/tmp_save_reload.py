"""Simulate frontend save-then-reload flow."""
import requests

base = "http://localhost:8000/api/strategies"

# 1. Get current value
items = requests.get(base, timeout=5).json()
s = items[0]
sid = s["id"]
old_val = s.get("stop_loss_pct")
print(f"1. BEFORE: stop_loss_pct = {old_val}")

# 2. Update to different value  
new_val = -0.15 if old_val != -0.15 else -0.12
r = requests.put(f"{base}/{sid}", json={"stop_loss_pct": new_val}, timeout=5)
updated = r.json().get("stop_loss_pct")
print(f"2. UPDATE response: stop_loss_pct = {updated}")

# 3. Reload list (same as frontend loadStrategies)
items2 = requests.get(base, timeout=5).json()
s2 = items2[0]
reloaded_val = s2.get("stop_loss_pct")
print(f"3. AFTER RELOAD LIST: stop_loss_pct = {reloaded_val}")

# Verdict
if reloaded_val == new_val:
    print(">> MATCH: save + reload works correctly")
else:
    print(f">> MISMATCH: expected {new_val}, got {reloaded_val}")

# Restore
requests.put(f"{base}/{sid}", json={"stop_loss_pct": old_val}, timeout=5)

# Also test sell_rank_pct for completeness
print()
r2 = requests.put(f"{base}/{sid}", json={"sell_rank_pct": 0.5}, timeout=5)
print(f"sell_rank_pct update: {r2.json().get('sell_rank_pct')} (expect 0.5)")
items3 = requests.get(base, timeout=5).json()
print(f"sell_rank_pct reload: {items3[0].get('sell_rank_pct')} (expect 0.5)")
requests.put(f"{base}/{sid}", json={"sell_rank_pct": 0.30}, timeout=5)
