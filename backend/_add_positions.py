"""Temporary script to add all positions from screenshot."""
import http.client
import json


def add_position(ts_code, stock_name, shares, price):
    c = http.client.HTTPConnection("localhost", 8000)
    body = json.dumps({
        "ts_code": ts_code,
        "stock_name": stock_name,
        "shares": shares,
        "price": price,
    })
    c.request(
        "POST", "/api/live-portfolio/positions",
        body=body.encode(),
        headers={"Content-Type": "application/json"},
    )
    r = c.getresponse()
    result = json.loads(r.read())
    positions = result.get("positions", [])
    pid = positions[-1]["id"][:8] if positions else "N/A"
    print(f"  ✓ {stock_name} ({ts_code}): shares={shares}, cost={price} → id={pid}")
    return result


# Stock data from user's screenshot
stocks = [
    ("603256.SH", "宏和科技", 1000, 189.843),
    ("688347.SH", "华虹公司", 900, 209.056),
    ("000725.SZ", "京东方Ａ", 31100, 6.428),
    ("002463.SZ", "沪电股份", 1500, 125.781),
    ("300394.SZ", "天孚通信", 400, 430.633),
]

print("Adding positions:")
for ts_code, name, shares, price in stocks:
    add_position(ts_code, name, shares, price)

print("\nAll done! Verifying...")

# Verify
c = http.client.HTTPConnection("localhost", 8000)
c.request("GET", "/api/live-portfolio/")
r = c.getresponse()
pf = json.loads(r.read())
print(f"\nPortfolio now has {len(pf['positions'])} positions:")
for p in pf["positions"]:
    print(f"  {p['stock_name']:8s} ({p['ts_code']:10s})  {p['shares']:>6}股  @ ¥{p['cost_price']:<10.4f}  总成本¥{p['total_cost']:<12.2f}")