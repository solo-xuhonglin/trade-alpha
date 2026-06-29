"""Check running backtest for planner_candidates data."""
import sys, os, requests

bt_name = "backtest_lstm_202606292254"
try:
    r = requests.get(f"http://localhost:8000/api/backtests", timeout=10)
    items = r.json().get("items", [])
    bt = next((b for b in items if b.get("name") == bt_name), None)
    if not bt:
        print(f"{bt_name}: NOT FOUND in backtest list")
    else:
        bt_id = bt.get("id") or bt.get("_id", "")
        print(f"Found: {bt_name} id={bt_id}")
        print(f"  status: {bt.get('status', '?')}")
        print(f"  days: {bt.get('total_days', '?')}")

        # Check daily details
        r2 = requests.get(f"http://localhost:8000/api/backtests/{bt_id}/daily-details", timeout=30)
        data = r2.json()
        print(f"  daily details: {len(data.get('items', []))} days")
        if data.get("items"):
            day = data["items"][0]
            print(f"  fields in first day: {list(day.keys())}")
            has_plan = day.get("planner_candidates")
            print(f"  has planner_candidates: {has_plan is not None and len(has_plan) > 0}")
            if has_plan:
                print(f"  first candidate: {has_plan[0]}")
            else:
                print(f"  planner_candidates: {has_plan}")
except Exception as e:
    print(f"Error: {e}")
