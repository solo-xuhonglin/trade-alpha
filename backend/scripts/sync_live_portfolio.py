"""Sync live portfolio positions to match a target set.

Usage:
    python scripts/sync_live_portfolio.py positions.json
    python scripts/sync_live_portfolio.py --dry-run positions.json

JSON format (positions.json):
    {
        "603256.SH": {"name": "\u5b8f\u548c\u79d1\u6280", "shares": 1000, "cost_price": 189.789},
        "688347.SH": {"name": "\u534e\u8679\u516c\u53f8", "shares": 900, "cost_price": 209.056}
    }

If ts_code is known, provide it as the key. If unknown, use a placeholder
and the script will search by name to fill it in.
"""

import http.client
import json
import sys
from pathlib import Path
from urllib.parse import quote

API_HOST = "localhost"
API_PORT = 8000
API_PREFIX = "/api"


def _api(method, path, body=None):
    """Make an HTTP request to the backend API."""
    c = http.client.HTTPConnection(API_HOST, API_PORT)
    headers = {"Content-Type": "application/json"} if body else {}
    payload = json.dumps(body).encode() if body else None
    c.request(method, f"{API_PREFIX}{path}", body=payload, headers=headers)
    r = c.getresponse()
    return r.status, json.loads(r.read())


def get_portfolio():
    """Fetch current portfolio from API."""
    _, data = _api("GET", "/live-portfolio/")
    return data


def search_stock(query):
    """Search stock by name or code, return first match or None."""
    _, data = _api("GET", f"/live-portfolio/stocks/search?q={quote(query)}")
    items = data.get("items", [])
    return items[0] if items else None


def delete_position(position_id, stock_name):
    """Delete a position by ID."""
    status, _ = _api("DELETE", f"/live-portfolio/positions/{position_id}")
    return status


def update_position(position_id, shares, cost_price):
    """Update shares and/or cost price of a position."""
    body = {"shares": shares, "cost_price": cost_price}
    status, _ = _api("PUT", f"/live-portfolio/positions/{position_id}", body)
    return status


def add_position(ts_code, stock_name, shares, price):
    """Add a new position."""
    body = {
        "ts_code": ts_code,
        "stock_name": stock_name,
        "shares": shares,
        "price": price,
    }
    status, _ = _api("POST", "/live-portfolio/positions", body)
    return status


def load_target(path):
    """Load target positions from a JSON file.

    Expected format:
        {"<ts_code>": {"name": "...", "shares": N, "cost_price": N}}
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sync(dry_run=False):
    """Sync portfolio to match target positions."""
    # --- Load target ---
    target_path = sys.argv[1]
    target_raw = load_target(target_path)

    # Normalise: resolve unknown ts_codes by name search
    target = {}
    for ts_code, info in target_raw.items():
        if ts_code and ts_code != "" and "." in ts_code:
            target[ts_code] = info
        else:
            # Search by name
            match = search_stock(info["name"])
            if match:
                target[match["ts_code"]] = {**info, "name": match["name"]}
                print(f"  Resolved {info['name']} → {match['ts_code']}")
            else:
                print(f"  ! WARNING: {info['name']} not found in stock list, skipping")
                continue

    # --- Get current ---
    pf = get_portfolio()
    current = {p["ts_code"]: p for p in pf["positions"]}

    print(f"\nCurrent positions: {len(current)}")
    print(f"Target positions : {len(target)}")

    # --- Compute diff ---
    to_delete = [p for ts_code, p in current.items() if ts_code not in target]
    to_update = []
    to_add = []

    for ts_code, info in target.items():
        if ts_code in current:
            p = current[ts_code]
            shares_changed = p["shares"] != info["shares"]
            cost_changed = abs(p["cost_price"] - info["cost_price"]) > 0.001
            if shares_changed or cost_changed:
                to_update.append((ts_code, info, p))
        else:
            to_add.append((ts_code, info))

    # --- Execute ---
    changes = 0

    if to_delete:
        print(f"\n--- Deleting {len(to_delete)} removed positions ---")
        for p in to_delete:
            if dry_run:
                print(f"  Would delete: {p['stock_name']} ({p['ts_code']})")
            else:
                status = delete_position(p["id"], p["stock_name"])
                print(f"  ✗ {p['stock_name']} ({p['ts_code']}) → {'OK' if status == 200 else status}")
                changes += 1

    if to_update:
        print(f"\n--- Updating {len(to_update)} changed positions ---")
        for ts_code, info, cur in to_update:
            if dry_run:
                print(f"  Would update: {info['name']} ({ts_code}) "
                      f"shares={cur['shares']}→{info['shares']}, "
                      f"cost={cur['cost_price']}→{info['cost_price']}")
            else:
                status = update_position(cur["id"], info["shares"], info["cost_price"])
                print(f"  ↻ {info['name']} ({ts_code}) shares={info['shares']} cost={info['cost_price']} → {'OK' if status == 200 else status}")
                changes += 1

    if to_add:
        print(f"\n--- Adding {len(to_add)} new positions ---")
        for ts_code, info in to_add:
            if dry_run:
                print(f"  Would add: {info['name']} ({ts_code}) shares={info['shares']} cost={info['cost_price']}")
            else:
                status = add_position(ts_code, info["name"], info["shares"], info["cost_price"])
                print(f"  + {info['name']} ({ts_code}) shares={info['shares']} cost={info['cost_price']} → {'OK' if status == 200 else status}")
                changes += 1

    if not any([to_delete, to_update, to_add]):
        print("\n✓ Portfolio already matches target, no changes needed.")
        return

    # --- Verify ---
    if not dry_run and changes > 0:
        print(f"\n--- Verification ({changes} changes made) ---")
        pf = get_portfolio()
        print(f"Portfolio now has {len(pf['positions'])} positions:")
        for p in pf["positions"]:
            print(f"  {p['stock_name']:8s} ({p['ts_code']:10s})  "
                  f"{p['shares']:>6}股  @ ¥{p['cost_price']:<10.4f}  "
                  f"总成本¥{p['total_cost']:<12.2f}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    dry_run = "--dry-run" in sys.argv
    if dry_run:
        sys.argv.remove("--dry-run")

    sync(dry_run)


if __name__ == "__main__":
    main()