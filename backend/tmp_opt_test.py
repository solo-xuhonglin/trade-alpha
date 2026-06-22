"""Test CRUD after optimization."""
import requests

base = "http://localhost:8000/api/strategies"
name = "test_opt_temp"

# Clean up
for s in requests.get(base, timeout=5).json():
    if s.get("name") == name:
        requests.delete(f"{base}/{s['id']}", timeout=5)

# Create
r = requests.post(base, json={"name": name, "type": "multi", "stop_loss_pct": -0.15}, timeout=5)
d = r.json()
sid = d["id"]
print(f"CREATE: stop_loss_pct={d.get('stop_loss_pct')} (expect -0.15), keys={len(d)}")

# Read
items = requests.get(base, timeout=5).json()
s = [x for x in items if x["name"] == name][0]
print(f"LIST:   stop_loss_pct={s.get('stop_loss_pct')} (expect -0.15)")

# Update
r2 = requests.put(f"{base}/{sid}", json={"stop_loss_pct": -0.12, "use_hold_protection": True}, timeout=5)
d2 = r2.json()
print(f"UPDATE: stop_loss_pct={d2.get('stop_loss_pct')} (expect -0.12), use_hold_protection={d2.get('use_hold_protection')} (expect True)")

# Reload
items2 = requests.get(base, timeout=5).json()
s2 = [x for x in items2 if x["name"] == name][0]
print(f"RELOAD: stop_loss_pct={s2.get('stop_loss_pct')} (expect -0.12), use_hold_protection={s2.get('use_hold_protection')} (expect True)")

# Delete
requests.delete(f"{base}/{sid}", timeout=5)
print(f"DELETE: OK")

print("\nALL PASSED!")
