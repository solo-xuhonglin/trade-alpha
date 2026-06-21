"""Analyze 4 recent backtests: buy quality + sell correctness."""
import asyncio
from collections import defaultdict, Counter
from motor.motor_asyncio import AsyncIOMotorClient
from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.config import load_config


async def get_future_close(db, code: str, trade_date: str, offset_days: int = 10):
    """Get close price N trading days after trade_date."""
    future = await db.stock_daily.find_one(
        {"ts_code": code, "trade_date": {"$gt": trade_date}},
        sort=[("trade_date", 1)],
        skip=offset_days - 1,
    )
    if future and "close" in future:
        return future["close"]
    return None


async def analyze_backtest(r, db):
    name = r.get('name', '')
    total_r = r.get('total_return', 0)
    base_r = r.get('baseline_return', 0)
    trades = await db.execution_trades.find({'backtest_id': r['_id']}).sort('trade_date', 1).to_list(None)
    if not trades:
        return

    buys = [t for t in trades if t.get('action') == 'buy']
    sells = [t for t in trades if t.get('action') == 'sell']

    print(f"\n{'='*70}")
    print(f"{name}  |  ret={total_r*100:.1f}%  base={base_r*100:.1f}%")
    print(f"buys={len(buys)} sells={len(sells)}")

    # ── 1. BUY ANALYSIS: how did stocks perform after each buy? ──
    print(f"\n[1. BUY QUALITY - PnL by buy reason + group]")
    print(f"  For each buy, track the achieved PnL at corresponding sell time.")

    # Match buys to sells by ts_code + chronological order
    buy_sell_map = defaultdict(list)  # ts_code -> [(buy_trade, sell_trade)]
    for code in set(t.get('ts_code') for t in trades):
        code_trades = [t for t in trades if t.get('ts_code') == code and t.get('action') != 'cancelled']
        code_trades.sort(key=lambda x: x.get('trade_date', ''))
        buy_stack = []
        for t in code_trades:
            if t['action'] == 'buy':
                buy_stack.append(t)
            elif t['action'] == 'sell' and buy_stack:
                bt = buy_stack.pop(0)
                buy_sell_map[code].append((bt, t))

    # Group buy outcomes
    buy_results = defaultdict(list)
    for code, pairs in buy_sell_map.items():
        for bt, st in pairs:
            reason = bt.get('reason', 'unknown')
            g = bt.get('candidate_group', 'unknown')
            yr = bt.get('trade_date', '')[:4]
            pnl = st.get('pnl_pct')
            if pnl is not None:
                key = (yr, reason, g)
                buy_results[key].append(pnl)

    print(f"  {'year':5s} {'reason':25s} {'grp':8s} {'cnt':5s} {'win%':7s} {'avg_pnl':10s} {'total_pnl':10s}")
    for key in sorted(buy_results.keys()):
        yr, reason, g = key
        vals = buy_results[key]
        win = sum(1 for v in vals if v > 0)
        avg = sum(vals) / len(vals) * 100
        total = sum(vals) * 100
        print(f"  {yr:5s} {reason:25s} {g:8s} {len(vals):5d} {win/len(vals)*100:6.1f}% {avg:+9.2f}% {total:+9.2f}%")

    # ── 2. BUY: aggregate by group only ──
    buy_by_group = defaultdict(list)
    for code, pairs in buy_sell_map.items():
        for bt, st in pairs:
            g = bt.get('candidate_group', 'unknown')
            pnl = st.get('pnl_pct')
            if pnl is not None:
                buy_by_group[g].append(pnl)

    print(f"\n[2. BUY SUMMARY by group]")
    for g in ['base', 'momentum']:
        vals = buy_by_group.get(g, [])
        if vals:
            win = sum(1 for v in vals if v > 0)
            avg = sum(vals) / len(vals) * 100
            total = sum(vals) * 100
            print(f"  {g:10s}: {len(vals):4d} trades  win={win/len(vals)*100:.1f}%  avg={avg:+.2f}%  total={total:+.1f}%")

    # ── 3. SELL CORRECTNESS: check if stock continued falling after sell ──
    print(f"\n[3. SELL CORRECTNESS - what happened 10 trading days after sell]")
    print(f"  'correct'=stock fell further after sell, 'wrong'=stock rebounded")

    # Build price cache
    price_cache = {}
    sell_analysis = defaultdict(lambda: {"correct": 0, "wrong": 0, "avg_post_pnl": []})

    for t in sells:
        code = t.get('ts_code', '')
        date = t.get('trade_date', '')
        sell_price = t.get('filled_price', 0)
        reason = t.get('reason', 'unknown')
        g = t.get('candidate_group', 'unknown')

        if sell_price <= 0:
            continue

        # Get price 10 trading days later
        cache_key = (code, date)
        if cache_key not in price_cache:
            future_prices = await db.stock_daily.find(
                {"ts_code": code, "trade_date": {"$gt": date}},
                sort=[("trade_date", 1)],
                limit=15,
            ).to_list(None)
            # Find ~10th trading day
            future_close = future_prices[9]["close"] if len(future_prices) > 9 else None
            price_cache[cache_key] = future_close
        future_close = price_cache[cache_key]

        if future_close is None:
            continue

        post_pnl = (future_close - sell_price) / sell_price
        key = (reason, g)
        sell_analysis[key]["avg_post_pnl"].append(post_pnl)

        if post_pnl < 0:
            sell_analysis[key]["correct"] += 1  # sold before further decline
        else:
            sell_analysis[key]["wrong"] += 1  # missed a rebound

    print(f"  {'reason':25s} {'grp':8s} {'correct':8s} {'wrong':8s} {'correct%':9s} {'avg_post%':10s}")
    for key in sorted(sell_analysis.keys()):
        reason, g = key
        sa = sell_analysis[key]
        total = sa["correct"] + sa["wrong"]
        avg_post = sum(sa["avg_post_pnl"]) / len(sa["avg_post_pnl"]) * 100 if sa["avg_post_pnl"] else 0
        print(f"  {reason:25s} {g:8s} {sa['correct']:8d} {sa['wrong']:8d} {sa['correct']/total*100:8.1f}% {avg_post:+9.2f}%")

    # ── 4. STOP LOSS DEEP DIVE ──
    print(f"\n[4. STOP LOSS deep dive - buy reasons that led to stop loss]")
    stop_loss_sells = [t for t in sells if t.get('reason') == 'stop_loss']
    stop_loss_buy_pairs = []
    for code in set(t.get('ts_code') for t in stop_loss_sells):
        code_trades = [t for t in trades if t.get('ts_code') == code and t.get('action') != 'cancelled']
        code_trades.sort(key=lambda x: x.get('trade_date', ''))
        buy_stack = []
        for t in code_trades:
            if t['action'] == 'buy':
                buy_stack.append(t)
            elif t['action'] == 'sell' and t.get('reason') == 'stop_loss' and buy_stack:
                stop_loss_buy_pairs.append((buy_stack.pop(0), t))

    # What buy reasons caused stop losses?
    stop_loss_by_buy = defaultdict(int)
    for bt, st in stop_loss_buy_pairs:
        reason = bt.get('reason', 'unknown')
        g = bt.get('candidate_group', 'unknown')
        stop_loss_by_buy[(reason, g)] += 1

    total_sl = sum(stop_loss_by_buy.values())
    print(f"  Total stop_loss trades: {total_sl}")
    print(f"  {'buy_reason':25s} {'grp':8s} {'cnt':6s} {'pct':7s}")
    for (reason, g), cnt in sorted(stop_loss_by_buy.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason:25s} {g:8s} {cnt:6d} {cnt/total_sl*100:6.1f}%")

    # ── 5. Post-stop-loss stock performance ──
    print(f"\n[5. Post-stop-loss recovery: what happened after being stopped out]")
    sl_post = {"correct": 0, "wrong": 0, "details": []}
    for bt, st in stop_loss_buy_pairs:
        code = st.get('ts_code', '')
        date = st.get('trade_date', '')
        sell_price = st.get('filled_price', 0)
        if sell_price <= 0:
            continue
        cache_key = (code, date)
        if cache_key not in price_cache:
            future_prices = await db.stock_daily.find(
                {"ts_code": code, "trade_date": {"$gt": date}},
                sort=[("trade_date", 1)],
                limit=15,
            ).to_list(None)
            future_close = future_prices[9]["close"] if len(future_prices) > 9 else None
            price_cache[cache_key] = future_close
        future_close = price_cache[cache_key]
        if future_close is None:
            continue
        post_pnl = (future_close - sell_price) / sell_price * 100
        sl_post["details"].append((code, date, post_pnl, bt.get('candidate_group', '?')))
        if post_pnl < 0:
            sl_post["correct"] += 1
        else:
            sl_post["wrong"] += 1

    total_sl_check = sl_post["correct"] + sl_post["wrong"]
    if total_sl_check > 0:
        print(f"  Correct (saved further loss): {sl_post['correct']}/{total_sl_check} ({sl_post['correct']/total_sl_check*100:.0f}%)")
        print(f"  Wrong (missed rebound):       {sl_post['wrong']}/{total_sl_check} ({sl_post['wrong']/total_sl_check*100:.0f}%)")
        worst_wrong = sorted([d for d in sl_post["details"] if d[2] > 0], key=lambda x: -x[2])[:5]
        if worst_wrong:
            print(f"  Top 5 missed rebounds (rebounded most after stop-loss):")
            for code, date, post_pnl, g in worst_wrong:
                print(f"    {code:10s} [{g:8s}] sold {date}, 10d later: {post_pnl:+.2f}%")
        saved_from = sorted([d for d in sl_post["details"] if d[2] < 0], key=lambda x: x[2])[:5]
        if saved_from:
            print(f"  Top 5 correct saves (continued falling after stop-loss):")
            for code, date, post_pnl, g in saved_from:
                print(f"    {code:10s} [{g:8s}] sold {date}, 10d later: {post_pnl:+.2f}%")


async def main():
    settings = load_config()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]
    await init_db()

    results = await db.execution_results.find().sort('created_at', -1).limit(2).to_list(None)
    for r in results:
        await analyze_backtest(r, db)

    client.close()


asyncio.run(main())
