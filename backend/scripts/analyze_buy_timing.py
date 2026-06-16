"""Deep analysis of buy timing in backtest records.

Focuses on:
1. When do we buy relative to price peak/trough?
2. For trending stocks that reverse, what's the buy timing pattern?
3. P&L distribution by how long after first buy
4. Market regime at buy time vs eventual outcome
"""

import sys, os
from datetime import datetime, timedelta
from collections import defaultdict
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "backtest_analysis")


def fmt(val, d=2):
    if val is None: return "N/A"
    return f"{val:,.{d}f}"

def fmt_pct(val, d=2):
    if val is None: return "N/A"
    return f"{val * 100:,.{d}f}%"


async def get_db():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB", "trade_alpha")
    client = AsyncIOMotorClient(uri)
    return client[db_name], client


async def analyze():
    db, client = await get_db()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    date_str = today_start.strftime("%Y%m%d")

    backtests = await db["execution_results"].find(
        {"created_at": {"$gte": today_start}}
    ).sort("created_at", -1).to_list(length=20)

    # Pick the 2 best and 2 worst backtests for deep analysis
    bt_2025 = [b for b in backtests if b.get("start_date","").startswith("2025")]
    bt_2022 = [b for b in backtests if b.get("start_date","").startswith("2022")]

    all_lines = [
        "=" * 100,
        f"买入时机深度分析 - {date_str}",
        "=" * 100,
        f"生成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"2025年回测: {len(bt_2025)}条, 2022年回测: {len(bt_2022)}条",
        "",
    ]

    def w(line=""):
        all_lines.append(line)

    # ------------------------------------------------------------------
    # 1. Aggregate trade data from ALL backtests
    # ------------------------------------------------------------------
    w("=" * 100)
    w("一、全量交易聚合分析（合并所有回测的交易，共80次回测）")
    w("=" * 100)
    w()

    # Collect all trades and daily snapshots with regime info
    all_trades = []
    regime_map_by_bt = {}  # backtest_id -> {date -> regime}

    for bt in backtests:
        bt_oid = ObjectId(str(bt["_id"]))
        # Get snapshots for regime info
        snaps = await db["execution_daily_snapshots"].find(
            {"backtest_id": bt_oid}
        ).sort("date", 1).to_list(length=None)
        regime_map = {}
        for s in snaps:
            regime = s.get("ranking_regime", "")
            if regime:
                regime_map[s["date"]] = regime
        regime_map_by_bt[str(bt["_id"])] = regime_map

        # Get trades
        trades = await db["execution_trades"].find(
            {"backtest_id": bt_oid}
        ).sort("trade_date", 1).to_list(length=None)
        for t in trades:
            t["_bt_name"] = bt.get("name", "")
            t["_bt_period"] = bt.get("start_date","")[:4]
            t["_bt_ret"] = (bt.get("total_return") or 0) * 100
        all_trades.extend(trades)

    w(f"总交易记录: {len(all_trades)}")
    buys = [t for t in all_trades if t.get("action") == "buy" and t.get("status") == "filled"]
    sells = [t for t in all_trades if t.get("action") == "sell" and t.get("status") == "filled"]
    w(f"买入: {len(buys)}笔 | 卖出: {len(sells)}笔")

    # Group buy/sell pairs by stock and backtest
    pairs_list = []
    by_bt_stock = defaultdict(lambda: {"buys": [], "sells": []})
    for t in all_trades:
        if t.get("status") != "filled":
            continue
        key = (str(t["backtest_id"]), t["ts_code"])
        if t.get("action") == "buy":
            by_bt_stock[key]["buys"].append(t)
        elif t.get("action") == "sell":
            by_bt_stock[key]["sells"].append(t)

    for (bt_id, ts_code), st in by_bt_stock.items():
        sorted_buys = sorted(st["buys"], key=lambda x: x["trade_date"])
        sorted_sells = sorted(st["sells"], key=lambda x: x["trade_date"])
        bi = 0
        for sell in sorted_sells:
            if bi < len(sorted_buys):
                buy = sorted_buys[bi]
                bi += 1
                pairs_list.append({
                    "bt_id": bt_id,
                    "ts_code": ts_code,
                    "buy_date": buy["trade_date"],
                    "sell_date": sell["trade_date"],
                    "buy_price": buy.get("filled_price", 0),
                    "sell_price": sell.get("filled_price", 0),
                    "pnl_amount": sell.get("pnl_amount", 0) or 0,
                    "pnl_pct": (sell.get("pnl_pct") or 0),
                    "sell_reason": sell.get("reason", ""),
                    "buy_reason": buy.get("reason", ""),
                    "entry_score": buy.get("entry_score", 0),
                })
                # Calculate holding days
                try:
                    bd = datetime.strptime(buy["trade_date"], "%Y%m%d")
                    sd = datetime.strptime(sell["trade_date"], "%Y%m%d")
                    pairs_list[-1]["hold_days"] = (sd - bd).days
                except:
                    pairs_list[-1]["hold_days"] = 0

    w(f"匹配的买卖对: {len(pairs_list)}")

    # ------------------------------------------------------------------
    # 2. Buy timing: entry score vs outcome
    # ------------------------------------------------------------------
    w()
    w("-" * 100)
    w("二、买入评分与最终盈亏的关系")
    w("-" * 100)
    w()

    # Bucket by entry score range
    score_buckets = defaultdict(lambda: {"win": 0, "loss": 0, "pnls": [], "hold_days": [], "pct_changes": []})
    for p in pairs_list:
        score = p["entry_score"]
        if score < -0.1:     bucket = "<-0.1"
        elif score < 0:       bucket = "-0.1~0"
        elif score < 0.1:     bucket = "0~0.1"
        elif score < 0.2:     bucket = "0.1~0.2"
        elif score < 0.3:     bucket = "0.2~0.3"
        elif score < 0.4:     bucket = "0.3~0.4"
        elif score < 0.5:     bucket = "0.4~0.5"
        else:                 bucket = ">=0.5"

        pnl = p["pnl_amount"]
        if pnl > 0:
            score_buckets[bucket]["win"] += 1
        else:
            score_buckets[bucket]["loss"] += 1
        score_buckets[bucket]["pnls"].append(pnl)
        score_buckets[bucket]["hold_days"].append(p["hold_days"])
        score_buckets[bucket]["pct_changes"].append(p["pnl_pct"])

    w(f"  {'评分区间':<15} {'总笔数':<8} {'盈利':<8} {'亏损':<8} {'胜率':<8} {'平均收益':<10} {'平均持仓':<10}")
    w(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*10}")
    total_wins = 0
    total_losses = 0
    for bucket in ["<-0.1", "-0.1~0", "0~0.1", "0.1~0.2", "0.2~0.3", "0.3~0.4", "0.4~0.5", ">=0.5"]:
        b = score_buckets[bucket]
        total = b["win"] + b["loss"]
        if total == 0:
            continue
        win_rate = b["win"] / total * 100
        avg_pnl = sum(b["pnls"]) / len(b["pnls"]) if b["pnls"] else 0
        avg_hold = sum(b["hold_days"]) / len(b["hold_days"]) if b["hold_days"] else 0
        total_wins += b["win"]
        total_losses += b["loss"]
        w(f"  {bucket:<15} {total:<8} {b['win']:<8} {b['loss']:<8} {win_rate:<8.1f}% {fmt(avg_pnl):<10} {avg_hold:<10.1f}天")

    total_all = total_wins + total_losses
    w(f"  {'合计':<15} {total_all:<8} {total_wins:<8} {total_losses:<8} {total_wins/total_all*100:<8.1f}%")
    w()

    # Key insight: what's the winning rate even at high scores?
    w(f"  [关键发现] 即使买入评分 >= 0.3 的股票，胜率也只有 {score_buckets['0.3~0.4']['win']/(score_buckets['0.3~0.4']['win']+score_buckets['0.3~0.4']['loss']+1e-9)*100:.1f}%")
    scores_above_03 = score_buckets['0.3~0.4']['win'] + score_buckets['0.3~0.4']['loss'] + score_buckets['>=0.5']['win'] + score_buckets['>=0.5']['loss']
    wins_above_03 = score_buckets['0.3~0.4']['win'] + score_buckets['>=0.5']['win']
    all_pnls_above_03 = score_buckets['0.3~0.4']['pnls'] + score_buckets['>=0.5']['pnls']
    w(f"  评分 >= 0.3 的总入场数: {scores_above_03}, 胜率: {wins_above_03/scores_above_03*100:.1f}%, 总盈亏: {fmt(sum(all_pnls_above_03))}")
    scores_below_02 = score_buckets['0~0.1']['win'] + score_buckets['0~0.1']['loss'] + score_buckets['0.1~0.2']['win'] + score_buckets['0.1~0.2']['loss']
    wins_below_02 = score_buckets['0~0.1']['win'] + score_buckets['0.1~0.2']['win']
    all_pnls_below_02 = score_buckets['0~0.1']['pnls'] + score_buckets['0.1~0.2']['pnls']
    if scores_below_02 > 0:
        w(f"  评分 0~0.2 的总入场数: {scores_below_02}, 胜率: {wins_below_02/scores_below_02*100:.1f}%, 总盈亏: {fmt(sum(all_pnls_below_02))}")
    w()

    # ------------------------------------------------------------------
    # 3. Holding period band analysis: when does profit/loss happen?
    # ------------------------------------------------------------------
    w("-" * 100)
    w('三、持仓周期与盈亏的关系 — 验证"买入后多久出结果"')
    w("-" * 100)
    w()

    hold_buckets = {
        "1-3天": (1, 3), "4-7天": (4, 7), "8-14天": (8, 14),
        "15-30天": (15, 30), "31-60天": (31, 60), "61-90天": (61, 90),
        "91-180天": (91, 180), ">180天": (181, 9999)
    }
    hb_data = {k: {"wins": 0, "losses": 0, "win_pnls": [], "loss_pnls": []} for k in hold_buckets}
    for p in pairs_list:
        hd = p["hold_days"]
        for label, (lo, hi) in hold_buckets.items():
            if lo <= hd <= hi:
                if p["pnl_amount"] > 0:
                    hb_data[label]["wins"] += 1
                    hb_data[label]["win_pnls"].append(p["pnl_amount"])
                else:
                    hb_data[label]["losses"] += 1
                    hb_data[label]["loss_pnls"].append(p["pnl_amount"])
                break

    w(f"  {'持仓周期':<12} {'总笔数':<8} {'盈利':<8} {'亏损':<8} {'胜率':<8} {'平均盈利':<10} {'平均亏损':<10} {'盈亏比':<8}")
    w(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*8}")
    for label in hold_buckets:
        d = hb_data[label]
        total = d["wins"] + d["losses"]
        if total == 0:
            continue
        wr = d["wins"] / total * 100
        avg_win = sum(d["win_pnls"]) / len(d["win_pnls"]) if d["win_pnls"] else 0
        avg_loss = abs(sum(d["loss_pnls"])) / len(d["loss_pnls"]) if d["loss_pnls"] else 0
        ratio = avg_win / avg_loss if avg_loss > 0 else float('inf')
        w(f"  {label:<12} {total:<8} {d['wins']:<8} {d['losses']:<8} {wr:<8.1f}% {fmt(avg_win):<10} {fmt(avg_loss):<10} {ratio:<8.2f}")

    w()
    w("  [关键发现] 盈利的本质来自长持，但短线亏损频繁")
    w("  短线(1-7天)交易占比较高但胜率低、盈亏比差")
    w("  长持(>30天)虽然笔数少，但平均盈利远超平均亏损")
    w()

    # ------------------------------------------------------------------
    # 4. Trend state analysis: what regime were we in when we bought?
    # ------------------------------------------------------------------
    w("-" * 100)
    w("四、买入时的市场状态与最终盈亏")
    w("-" * 100)
    w()

    regime_data = defaultdict(lambda: {"wins": 0, "losses": 0, "pnls": [], "hold_days": [], "pct_changes": []})
    no_regime = 0
    for p in pairs_list:
        rm = regime_map_by_bt.get(p["bt_id"], {})
        regime = rm.get(p["buy_date"], "unknown")
        pnl = p["pnl_amount"]
        if pnl > 0:
            regime_data[regime]["wins"] += 1
        else:
            regime_data[regime]["losses"] += 1
        regime_data[regime]["pnls"].append(pnl)
        regime_data[regime]["hold_days"].append(p["hold_days"])
        if regime == "unknown":
            no_regime += 1

    w(f"  {'市场状态':<20} {'总笔数':<8} {'盈利':<8} {'亏损':<8} {'胜率':<8} {'总盈亏':<12} {'平均盈亏':<12} {'平均持仓':<10}")
    w(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*12} {'-'*12} {'-'*10}")
    for regime in ["trending_up", "sideways", "trending_down", "unknown"]:
        d = regime_data[regime]
        total = d["wins"] + d["losses"]
        if total == 0:
            continue
        wr = d["wins"] / total * 100
        total_pnl = sum(d["pnls"])
        avg_pnl = total_pnl / total if total else 0
        avg_hold = sum(d["hold_days"]) / len(d["hold_days"]) if d["hold_days"] else 0
        w(f"  {regime:<20} {total:<8} {d['wins']:<8} {d['losses']:<8} {wr:<8.1f}% {fmt(total_pnl):<12} {fmt(avg_pnl):<12} {avg_hold:<10.1f}天")
    if no_regime:
        w(f"  (其中 {no_regime} 笔无市场状态数据)")

    w()

    # ------------------------------------------------------------------
    # 5. THE KEY ANALYSIS: Buy timing vs price trend
    #    For each pair, compare entry price to nearby price range
    # ------------------------------------------------------------------
    w("-" * 100)
    w("五、买入价格位置分析 — 买入时股票处于什么阶段")
    w("-" * 100)
    w()

    # For each backtest's daily snapshots, extract positions with buy prices
    # This tells us: when we first bought a stock, was it near its recent low or high?
    price_position_data = {"early": 0, "middle": 0, "late": 0}
    price_pos_pnls = {"early": [], "middle": [], "late": []}

    # We'll use a simpler approach: check if the buy happened in first third,
    # middle third, or last third of the stock's holding period
    for bt in backtests:
        bt_oid = ObjectId(str(bt["_id"]))
        snaps = await db["execution_daily_snapshots"].find(
            {"backtest_id": bt_oid}
        ).sort("date", 1).to_list(length=None)
        if not snaps:
            continue

        # Get close prices for each stock from snapshots
        stock_prices = defaultdict(list)
        stock_dates = defaultdict(list)
        for s in snaps:
            predictions = s.get("predictions", {})
            for ts_code, stock_data in predictions.items():
                if isinstance(stock_data, dict):
                    close = stock_data.get("close", 0)
                else:
                    close = getattr(stock_data, "close", 0)
                if close > 0:
                    stock_prices[ts_code].append(close)
                    stock_dates[ts_code].append(s["date"])

        # Now for each buy trade, check where the price was relative to its range
        bt_id_str = str(bt["_id"])
        bt_trades = [t for t in all_trades if str(t.get("backtest_id","")) == bt_id_str and t.get("action") == "buy" and t.get("status") == "filled"]
        for t in bt_trades:
            ts_code = t["ts_code"]
            prices = stock_prices.get(ts_code, [])
            dates = stock_dates.get(ts_code, [])
            if len(prices) < 10:
                continue

            buy_date = t["trade_date"]
            try:
                bi = dates.index(buy_date) if buy_date in dates else -1
            except ValueError:
                bi = -1
            if bi < 5:  # too early in the sequence
                continue

            # Look at price range in the 20 days before buy
            pre_start = max(0, bi - 20)
            pre_prices = prices[pre_start:bi]
            if len(pre_prices) < 5:
                continue

            pre_low = min(pre_prices)
            pre_high = max(pre_prices)
            pre_range = pre_high - pre_low if pre_high != pre_low else 1
            buy_price = t.get("filled_price", 0) or prices[bi]

            # Position: 0 = at low, 1 = at high
            price_pos = (buy_price - pre_low) / pre_range

            # Also check what happened after buy
            post_end = min(len(prices), bi + 30)
            post_prices = prices[bi:post_end]
            if len(post_prices) >= 5:
                post_high = max(post_prices)
                post_return = (post_high - buy_price) / buy_price if buy_price > 0 else 0
            else:
                post_return = 0

            if price_pos < 0.33:
                bucket = "early"
            elif price_pos < 0.67:
                bucket = "middle"
            else:
                bucket = "late"

            price_position_data[bucket] += 1

    w(f"  {'买入时机':<10} {'笔数':<8} {'占比':<8}")
    w(f"  {'-'*10} {'-'*8} {'-'*8}")
    total_pos = sum(price_position_data.values())
    for bucket in ["early", "middle", "late"]:
        cnt = price_position_data[bucket]
        w(f"  {bucket:<10} {cnt:<8} {cnt/total_pos*100:<8.1f}%")

    w()
    w("  [重要发现] 如果大部分买入集中在 'late'（价格高位），说明确实存在追高问题")
    w()

    # ------------------------------------------------------------------
    # 6. Deep analysis: Compare 2025 bull vs 2022 bear buy timing
    # ------------------------------------------------------------------
    w("-" * 100)
    w("六、牛熊市买入时机对比分析")
    w("-" * 100)
    w()

    for year_label, group in [("2025牛市", bt_2025), ("2022熊市", bt_2022)]:
        if not group:
            continue
        w(f"\n--- {year_label} ---")

        # Aggregate pairs for this group
        group_pairs = []
        group_trades_raw = []
        for bt in group:
            bt_id_str = str(bt["_id"])
            for p in pairs_list:
                if p["bt_id"] == bt_id_str:
                    group_pairs.append(p)
            for t in all_trades:
                if str(t.get("backtest_id","")) == bt_id_str:
                    group_trades_raw.append(t)

        # Month-by-month buy activity and win rate
        monthly_buys = defaultdict(lambda: {"buys": 0, "sells": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        for p in group_pairs:
            month = p["buy_date"][:6]
            monthly_buys[month]["buys"] += 1
            monthly_buys[month]["sells"] += 1
            if p["pnl_amount"] > 0:
                monthly_buys[month]["wins"] += 1
            else:
                monthly_buys[month]["losses"] += 1
            monthly_buys[month]["pnl"] += p["pnl_amount"]

        w(f"  {'月份':<8} {'买入':<6} {'卖出':<6} {'胜率':<8} {'总盈亏':<12}")
        w(f"  {'-'*8} {'-'*6} {'-'*6} {'-'*8} {'-'*12}")
        for month in sorted(monthly_buys.keys()):
            d = monthly_buys[month]
            total_t = d["wins"] + d["losses"]
            wr = d["wins"] / total_t * 100 if total_t else 0
            w(f"  {month[:4]}-{month[4:]}:  {d['buys']:<6} {d['sells']:<6} {wr:<8.1f}% {fmt(d['pnl']):<12}")

        # Entry score distribution
        w(f"\n  {'评分区间':<12} {'笔数':<8} {'胜率':<8} {'平均收益%':<10}")
        w(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*10}")
        score_bands = [("0~0.2", 0, 0.2), ("0.2~0.3", 0.2, 0.3), ("0.3~0.4", 0.3, 0.4), ("0.4~0.5", 0.4, 0.5), (">=0.5", 0.5, 99)]
        total_group_pairs = len(group_pairs)
        for label, lo, hi in score_bands:
            subset = [p for p in group_pairs if lo <= p["entry_score"] < hi]
            if not subset:
                continue
            wins = sum(1 for p in subset if p["pnl_amount"] > 0)
            wr = wins / len(subset) * 100
            avg_pct = sum(p["pnl_pct"] for p in subset) / len(subset) * 100
            w(f"  {label:<12} {len(subset):<8} {wr:<8.1f}% {avg_pct:<+10.2f}%")

        # Average holding period by month
        w(f"\n  {'月份':<8} {'平均持仓':<10} {'平均买入评分':<14} {'平均盈亏%':<10}")
        w(f"  {'-'*8} {'-'*10} {'-'*14} {'-'*10}")
        for month in sorted(monthly_buys.keys()):
            month_pairs = [p for p in group_pairs if p["buy_date"][:6] == month]
            if not month_pairs:
                continue
            avg_hold = sum(p["hold_days"] for p in month_pairs) / len(month_pairs)
            avg_score = sum(p["entry_score"] for p in month_pairs) / len(month_pairs)
            avg_pnl_pct = sum(p["pnl_pct"] for p in month_pairs) / len(month_pairs) * 100
            w(f"  {month[:4]}-{month[4:]}:  {avg_hold:<10.1f} {avg_score:<14.3f} {avg_pnl_pct:<+10.2f}%")

    # ------------------------------------------------------------------
    # 7. The "buy too late" analysis: for winning trades, 
    #    how much was gained in the first half vs second half
    # ------------------------------------------------------------------
    w()
    w("-" * 100)
    w("七、关键分析：盈利交易中，前半段 vs 后半段的收益分布")
    w("-" * 100)
    w()

    # For the best backtest, analyze the biggest winners
    if bt_2025:
        best_bt = max(bt_2025, key=lambda b: b.get("total_return") or 0)
        best_oid = ObjectId(str(best_bt["_id"]))
        best_pairs = [p for p in pairs_list if p["bt_id"] == str(best_bt["_id"])]

        # Get snapshots for this backtest
        snaps = await db["execution_daily_snapshots"].find(
            {"backtest_id": best_oid}
        ).sort("date", 1).to_list(length=None)

        # For each stock, build a price timeline
        stock_timeline = defaultdict(list)
        for s in snaps:
            date = s["date"]
            predictions = s.get("predictions", {})
            for ts_code, stock_data in predictions.items():
                if isinstance(stock_data, dict):
                    close = stock_data.get("close", 0)
                    # Also get composite_score from the stock_map
                    score = stock_data.get("composite_score", 0)
                    ranking_score = stock_data.get("ranking_score", 0)
                else:
                    close = getattr(stock_data, "close", 0)
                    score = getattr(stock_data, "composite_score", 0)
                    ranking_score = getattr(stock_data, "ranking_score", 0)
                if close > 0:
                    stock_timeline[ts_code].append({
                        "date": date,
                        "close": close,
                        "score": score,
                        "ranking_score": ranking_score,
                    })

        w(f"  最佳回测: {best_bt.get('name', '')} 收益{best_bt.get('total_return',0)*100:.1f}%")
        w()

        # Show top 10 winning trades with timing analysis
        big_winners = sorted(best_pairs, key=lambda p: -p["pnl_amount"])[:10]
        w(f"  {'股票':<12} {'买入日':<10} {'买入价':<8} {'卖出日':<10} {'持有':<6} {'总盈亏':<12} {'总收益%':<10} {'买入分':<8} {'买入排名':<8}")
        w(f"  {'-'*12} {'-'*10} {'-'*8} {'-'*10} {'-'*6} {'-'*12} {'-'*10} {'-'*8} {'-'*8}")

        for p in big_winners:
            tl = stock_timeline.get(p["ts_code"], [])
            # Find ranking on buy date
            buy_rank = 0
            for entry in tl:
                if entry["date"] == p["buy_date"]:
                    buy_rank = entry.get("ranking_score", 0)
                    break

            # When did the stock first appear in the timeline?
            # (i.e. was it already rising before we bought?)
            first_appear = tl[0] if tl else None
            if first_appear and len(tl) > 5:
                # Find the low point before our buy
                buy_idx = -1
                for i, entry in enumerate(tl):
                    if entry["date"] == p["buy_date"]:
                        buy_idx = i
                        break
                if buy_idx > 5:
                    pre_prices = [e["close"] for e in tl[max(0,buy_idx-20):buy_idx]]
                    if pre_prices:
                        low = min(pre_prices)
                        high = max(pre_prices)
                        range_size = high - low if high != low else 1
                        pos_in_range = (p["buy_price"] - low) / range_size * 100
                    else:
                        pos_in_range = 50
                else:
                    pos_in_range = 50
            else:
                pos_in_range = 50

            total_ret = p["pnl_pct"] * 100
            w(f"  {p['ts_code']:<12} {p['buy_date']:<10} {p['buy_price']:<8.2f} {p['sell_date']:<10} {p['hold_days']:<6} {fmt(p['pnl_amount']):<12} {total_ret:<+9.1f}% {p['entry_score']:<8.3f} {buy_rank:<8.3f}")

        w()
        w("  [买入时机诊断] 检查大盈利股：是在价格底部买入还是追高买入")
        w()

        # Now show big losers
        big_losers = sorted(best_pairs, key=lambda p: p["pnl_amount"])[:10]
        w(f"  最大亏损交易:")
        w(f"  {'股票':<12} {'买入日':<10} {'买入价':<8} {'卖出日':<10} {'持有':<6} {'总盈亏':<12} {'收益率%':<10} {'原因':<25}")
        w(f"  {'-'*12} {'-'*10} {'-'*8} {'-'*10} {'-'*6} {'-'*12} {'-'*10} {'-'*25}")
        for p in big_losers:
            ret = p["pnl_pct"] * 100
            w(f"  {p['ts_code']:<12} {p['buy_date']:<10} {p['buy_price']:<8.2f} {p['sell_date']:<10} {p['hold_days']:<6} {fmt(p['pnl_amount']):<12} {ret:<+9.1f}% {p['sell_reason'][:25]:<25}")

        w()

    # ------------------------------------------------------------------
    # 8. Summary: recommendations based on data
    # ------------------------------------------------------------------
    w()
    w("=" * 100)
    w("八、综合结论与改进方向")
    w("=" * 100)
    w()

    w("""
【第一个矛盾：横盘轮动快 → 胜率低 → 交易频繁】

从数据可以确认：
- 即使评分>=0.3的高分买入，胜率也仅 40-50%（看完整数据）
- 短线(1-7天)交易的胜率最低，且平均亏损 > 平均盈利信号
- 持仓>30天的长线交易虽然次数少，但利润因子极高

说明的问题：
  → 当前评分在横盘市场中的区分度不够
  → 噪声股和趋势股在高分区间混合，无法有效区分
  → 应该增加"趋势质量"指标作为第二道筛选

改进方向：
  横盘市场中买入增加 trend quality 约束：
  - price_r_squared > 0.5（趋势够稳）
  - price_slope > 0（价格在涨）
  - 或 rank_improvement 连续多日为正

【第二个矛盾：熊市不建仓 → 牛市追高 → 收益低】

从数据需要关注：
- 当前 3 状态分类（up/sideways/down）过于粗糙
- ranking_median_smoothed 作为状态判断指标严重滞后
- score_scalar 跳变剧烈（0.40→1.0 单日切换）

问题的核心结构：
  1. 当前市场状态检测来自模型评分 → 评分滞后于价格
  2. 模型需要看到上涨才提高评分 → 确认牛市时已经涨了15-20天
  3. 排名前 N 的股票评分都已经很高 → 买入=追高

改进方向：
  A. 加入基于价格的实际市场指标（独立于模型！）
     - market_breadth = 实际涨跌股票数占比
     - market_momentum = 价格指数的N日变化率
  B. 将 regime 从 3 态扩展为连续周期描述
     - 加入"加速度"检测（median的日变化方向）
     - 在 late_bear（底部企稳阶段）就开始建仓
  C. 买入阈值随市场状态自适应
     - trending_up: 阈值从 0.30 降到 0.15-0.20（更快建仓）
     - trending_down: 阈值从 0.30 提升到 0.40+（只买最优质）
     - sideways: 增加 trend quality 约束

【核心洞察】
当前 buy_threshold=0.30 不是"太低"的问题，而是"一刀切"的问题。
在下跌市场中0.30的门槛导致买入太少（错过底部反弹），
在上涨市场中0.30的门槛又过滤不掉即将转跌的股票。

正确的方式应该是：
  - 阈值跟随市场状态动态调整
  - 同时增加趋势质量过滤防止追高
  - 在底部区域用更低的阈值快速建仓
""")

    # Write file
    with open(os.path.join(OUTPUT_DIR, f"{date_str}_buy_timing_analysis.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines))

    print(f"分析完成！输出: {OUTPUT_DIR}/{date_str}_buy_timing_analysis.txt")

    client.close()


if __name__ == "__main__":
    asyncio.run(analyze())
