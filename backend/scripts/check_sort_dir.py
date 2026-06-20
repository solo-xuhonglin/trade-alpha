"""Check momentum sort direction."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config

MOMENTUM_FIELDS = [
    "trend_slope_20", "trend_arrangement_20",
    "close_position_20", "close_position_60",
    "bias_20", "bias_60",
]

async def main():
    settings = load_config()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]
    resolved = "20240902"
    universe = await db.stock_list_history.find(
        {"trade_date": resolved, "total_mv": {"$ne": None}}
    ).sort("total_mv", -1).limit(500).to_list()
    universe_codes = [r["ts_code"] for r in universe]
    mv_top100 = set(universe_codes[:100])

    records = await db.stock_daily.find({
        "trade_date": resolved,
        "ts_code": {"$in": universe_codes},
        "trend_slope_20": {"$ne": None},
    }).to_list()

    # Sample extreme bias values
    bias_vals = [(r.get("bias_20", 0) or 0, r.get("bias_60", 0) or 0,
                  r.get("close_position_20", 0) or 0, r.get("trend_slope_20", 0) or 0,
                  r["ts_code"]) for r in records]
    bias_vals.sort(key=lambda x: x[0])
    print("=== Bottom 5 by bias_20 (most NEGATIVE) ===")
    for v in bias_vals[:5]:
        print(f"  {v[4]}: bias20={v[0]:.4f} bias60={v[1]:.4f} cpos20={v[2]:.4f} slope20={v[3]:.4f}")
    print("\n=== Top 5 by bias_20 (most POSITIVE) ===")
    for v in bias_vals[-5:]:
        print(f"  {v[4]}: bias20={v[0]:.4f} bias60={v[1]:.4f} cpos20={v[2]:.4f} slope20={v[3]:.4f}")

    stock_values = {}
    for r in records:
        vals = [r.get(f) for f in MOMENTUM_FIELDS]
        if all(v is not None for v in vals):
            stock_values[r["ts_code"]] = vals
    n_fields = len(MOMENTUM_FIELDS)

    # Current: ASCENDING sort (rank 0 = lowest value)
    composite_asc = {ts: 0 for ts in stock_values}
    for fi in range(n_fields):
        ranked = sorted(stock_values.items(), key=lambda x: x[1][fi])
        for rank, (ts, _) in enumerate(ranked):
            composite_asc[ts] += rank
    sorted_asc = sorted(composite_asc.items(), key=lambda x: x[1])

    print("\n=== Current ASCENDING sort - Top 10 ===")
    for i, (code, score) in enumerate(sorted_asc[:10]):
        doc = next(r for r in records if r["ts_code"] == code)
        in_mv = " (市值)" if code in mv_top100 else ""
        print(f"  {i+1}. {code}{in_mv}: bias20={doc.get('bias_20',0):.4f} bias60={doc.get('bias_60',0):.4f} cpos20={doc.get('close_position_20',0):.4f} slope20={doc.get('trend_slope_20',0):.4f}")

    # DESCENDING sort (rank 0 = highest value)
    composite_desc = {ts: 0 for ts in stock_values}
    for fi in range(n_fields):
        ranked = sorted(stock_values.items(), key=lambda x: -x[1][fi])
        for rank, (ts, _) in enumerate(ranked):
            composite_desc[ts] += rank
    sorted_desc = sorted(composite_desc.items(), key=lambda x: x[1])

    print("\n=== DESCENDING sort - Top 10 ===")
    for i, (code, score) in enumerate(sorted_desc[:10]):
        doc = next(r for r in records if r["ts_code"] == code)
        in_mv = " (市值)" if code in mv_top100 else ""
        print(f"  {i+1}. {code}{in_mv}: bias20={doc.get('bias_20',0):.4f} bias60={doc.get('bias_60',0):.4f} cpos20={doc.get('close_position_20',0):.4f} slope20={doc.get('trend_slope_20',0):.4f}")

    client.close()

asyncio.run(main())
