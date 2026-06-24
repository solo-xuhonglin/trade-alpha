"""Compare old vs new logic — same pool, same strategy name."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config
from collections import Counter

async def main():
    cfg = load_config()
    client = AsyncIOMotorClient(cfg.mongodb_uri)
    db = client[cfg.mongodb_db]

    pairs = [
        ("big_long 旧(无Planner)", "backtest_lstm_202606212242"),
        ("big_long 新(Planner)",   "backtest_lstm_202606241707"),
        ("live_long 旧(无Planner)","backtest_lstm_202606212243"),
        ("live_long 新(Planner)",  "backtest_lstm_202606241708"),
    ]

    for label, name in pairs:
        r = await db.execution_results.find_one({"name": name})
        if not r:
            print(f"\n{label}: NOT FOUND")
            continue
        bt_id = r["_id"]
        ss = r.get("strategy_snapshot", {})
        trades = await db.execution_trades.find({"backtest_id": bt_id}).to_list(10000)
        filled_sells = [t for t in trades if t.get("action")=="sell" and t.get("status")=="filled"]
        filled_buys = [t for t in trades if t.get("action")=="buy" and t.get("status")=="filled"]

        print(f"\n{'='*70}")
        print(f"  {label}: {name}")
        print(f"  Return: {r.get('total_return',0)*100:.1f}%  "
              f"max_pos={ss.get('max_positions')}  sell_rank_pct={ss.get('sell_rank_pct')}")
        print(f"  Filled buys: {len(filled_buys)}  sells: {len(filled_sells)}")
        
        # Buy reasons
        br = Counter(t.get("reason","") for t in filled_buys)
        print(f"  Buy reasons: {dict(br)}")

        # Avg buy price over time - split into early/late
        def _avg_price(tlist):
            return sum(t.get("filled_price",0) for t in tlist)/len(tlist) if tlist else 0
        
        # Split trades by date
        sorted_buys = sorted(filled_buys, key=lambda t: t.get("trade_date",""))
        half = len(sorted_buys)//2
        first_half = sorted_buys[:half]
        second_half = sorted_buys[half:]
        print(f"  Avg buy price: first_half={_avg_price(first_half):.2f}  "
              f"second_half={_avg_price(second_half):.2f}  "
              f"overall={_avg_price(sorted_buys):.2f}")

        # Win rate
        pnls = [t.get("pnl_pct",0) for t in filled_sells if t.get("pnl_pct") is not None]
        wins = [p for p in pnls if p>0]
        losses = [p for p in pnls if p<=0]
        print(f"  Win rate: {len(wins)/len(pnls)*100:.0f}%  "
              f"avg_win={sum(wins)/len(wins)*100:+.1f}%  avg_loss={sum(losses)/len(losses)*100:+.1f}%")
        
        # Avg hold days
        # Match buys to sells by ts_code
        sold_stocks = Counter(t.get("ts_code") for t in filled_sells)
        hold_times = []
        for ts_code in sold_stocks:
            buy_dates = sorted([t.get("trade_date","") for t in filled_buys if t["ts_code"]==ts_code])
            sell_dates = sorted([t.get("trade_date","") for t in filled_sells if t["ts_code"]==ts_code])
            if buy_dates and sell_dates:
                for bd in buy_dates:
                    matching_sells = [sd for sd in sell_dates if sd >= bd]
                    if matching_sells:
                        hold_days = (int(matching_sells[0]) - int(bd)) // 1
                        hold_times.append(hold_days)
        avg_hold = sum(hold_times)/len(hold_times) if hold_times else 0
        print(f"  Avg hold days: {avg_hold:.0f}")

        # Entry delay: for new logic, check days between recommendation and buy
        if ss.get("buy_cache_days"):
            delayed = []
            for t in filled_buys:
                bd = t.get("trade_date","")
                reason = t.get("reason","")
                delayed.append((bd, reason))
            print(f"  New logic: buy_cache_days={ss.get('buy_cache_days')}, close_weight={ss.get('buy_price_close_weight')}")
            
        # Monthly return for key months
        snaps = await db.execution_daily_snapshots.find({"backtest_id": bt_id}).sort("date").to_list(2000)
        monthly = {}
        for s in snaps:
            ym = s["date"][:6]
            if ym not in monthly:
                monthly[ym] = {"f": s["total_value"], "l": s["total_value"]}
            monthly[ym]["l"] = s["total_value"]
        
        key_months = ["202506","202507","202508","202509","202510"]
        print(f"  Monthly (key months):")
        for ym in sorted(monthly.keys()):
            if ym in key_months:
                ret = (monthly[ym]["l"]/monthly[ym]["f"]-1)*100
                print(f"    {ym}: {ret:+.1f}%", end="")
        print()

    client.close()

asyncio.run(main())
