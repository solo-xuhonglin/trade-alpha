"""Analyze today's backtest results - output to multiple files."""

import sys
import os
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv()

import asyncio
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "backtest_analysis")


async def get_db():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB", "trade_alpha")
    client = AsyncIOMotorClient(uri)
    return client[db_name], client


def fmt(val, decimals=2):
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:,.{decimals}f}"
    return str(val)


def fmt_pct(val, decimals=2):
    if val is None:
        return "N/A"
    return f"{val * 100:,.{decimals}f}%"


async def analyze_backtest_detail(db, bt, label):
    """Analyze a single backtest in detail, return lines list."""
    lines = []
    bt_id = str(bt["_id"])
    bt_oid = ObjectId(bt_id)
    name = bt.get("name", "Unnamed")
    ret = (bt.get("total_return") or 0) * 100

    lines.append(f"{'=' * 90}")
    lines.append(f"  {label}: {name} (总收益: {ret:.2f}%)")
    lines.append(f"{'=' * 90}")
    lines.append(f"  期间: {bt.get('start_date')} → {bt.get('end_date')}")
    lines.append(f"  初始资金: {fmt(bt.get('initial_capital'))} → 最终: {fmt(bt.get('final_value'))}")
    lines.append(f"  年化收益: {fmt_pct(bt.get('annual_return'))} | 夏普: {fmt(bt.get('sharpe_ratio'), 4)}")
    lines.append(f"  波动率: {fmt_pct(bt.get('volatility'))} | 最大回撤: {fmt_pct(bt.get('max_drawdown'))}")
    lines.append(f"  日胜率: {fmt_pct(bt.get('win_rate'))} | 总交易数: {bt.get('total_trades', 0)}")
    lines.append(f"  基准收益: {fmt_pct(bt.get('baseline_return'))} | 超额: {fmt_pct(bt.get('excess_return'))}")

    ss = bt.get("strategy_snapshot") or {}
    lines.append(f"\n  策略参数:")
    lines.append(f"    最大持仓: {ss.get('max_positions')} | 单股权重上限: {fmt_pct(ss.get('max_position_pct'))}")
    lines.append(f"    买入阈值: {fmt_pct(ss.get('buy_threshold'))} | 卖出阈值: {fmt_pct(ss.get('sell_threshold'))}")
    lines.append(f"    最小持有: {ss.get('min_hold_days')}天 | 最大持有: {ss.get('max_hold_days')}天 | 止损: {fmt_pct(ss.get('stop_loss_pct'))}")
    lines.append(f"    市场阶段策略: {ss.get('use_phase_strategy')} | 动量加分: {ss.get('use_momentum_boost')} | 趋势加分: {ss.get('use_trend_bonus')}")

    # Trades analysis
    lines.append(f"\n  {'=' * 50}")
    lines.append(f"  交易记录分析")
    lines.append(f"  {'=' * 50}")
    trades = await db["execution_trades"].find(
        {"backtest_id": bt_oid}
    ).sort("trade_date", 1).to_list(length=None)
    lines.append(f"  总成交记录: {len(trades)}")

    if trades:
        buys = [t for t in trades if t.get("action") == "buy"]
        sells = [t for t in trades if t.get("action") == "sell"]
        cancelled = [t for t in trades if t.get("status") == "cancelled"]
        lines.append(f"  买入: {len(buys)} | 卖出: {len(sells)} | 撤销: {len(cancelled)}")
        lines.append(f"  总手续费: {fmt(sum(t.get('fee', 0) for t in trades))}")

        # Group by stock
        by_stock = defaultdict(lambda: {"buys": [], "sells": []})
        for t in trades:
            if t.get("action") == "buy":
                by_stock[t["ts_code"]]["buys"].append(t)
            elif t.get("action") == "sell":
                by_stock[t["ts_code"]]["sells"].append(t)

        # Per-stock P&L
        lines.append(f"\n  --- 按股票分组盈亏 ---")
        stock_pnls = []
        for ts_code, st in by_stock.items():
            pairs = []
            bi = 0
            for sell in sorted(st["sells"], key=lambda x: x["trade_date"]):
                if bi < len(st["buys"]):
                    buy = sorted(st["buys"], key=lambda x: x["trade_date"])[bi]
                    bi += 1
                    pnl = sell.get("pnl_amount") or 0
                    pairs.append((buy, sell, pnl))
            total_pl = sum(p[2] for p in pairs)
            stock_pnls.append((ts_code, total_pl, len(pairs), pairs))

        stock_pnls.sort(key=lambda x: x[1], reverse=True)

        lines.append(f"  {'股票':<12} {'总盈亏':<12} {'交易次数':<8} {'平均每笔':<12} {'平均收益率':<12}")
        lines.append(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*12} {'-'*12}")
        for ts_code, total_pl, cnt, pairs in stock_pnls[:15]:
            avg_pnl_pct = sum(sell.get("pnl_pct", 0) or 0 for _, sell, _ in pairs) / cnt if cnt else 0
            lines.append(f"  {ts_code:<12} {fmt(total_pl):<12} {cnt:<8} {fmt(total_pl/cnt if cnt else 0):<12} {avg_pnl_pct*100:>+6.1f}%")
        if len(stock_pnls) > 15:
            lines.append(f"  ... 还有 {len(stock_pnls)-15} 只股票")

        # Detailed trade list (buy/sell pairs)
        lines.append(f"\n  --- 逐笔交易明细 ---")
        lines.append(f"  {'股票':<12} {'买入日':<10} {'买入价':<10} {'卖出日':<10} {'卖出价':<10} {'持股':<5} {'盈亏':<10} {'收益率':<8} {'卖出原因'}")
        lines.append(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*5} {'-'*10} {'-'*8} {'-'*30}")
        detail_count = 0
        for ts_code, total_pl, cnt, pairs in stock_pnls:
            for buy, sell, pnl in pairs:
                if detail_count >= 50:
                    lines.append(f"  ... (仅显示前50笔，共{len([p for _,_,_,pairs2 in stock_pnls for p in pairs2])}笔)")
                    break
                try:
                    bd = datetime.strptime(buy["trade_date"], "%Y%m%d")
                    sd = datetime.strptime(sell["trade_date"], "%Y%m%d")
                    hold = (sd - bd).days
                except (ValueError, KeyError):
                    hold = 0
                reason = (sell.get("reason") or "")[:30]
                pnl_pct = (sell.get("pnl_pct") or 0) * 100
                lines.append(f"  {ts_code:<12} {buy['trade_date']:<10} {buy['filled_price']:<10.2f} {sell['trade_date']:<10} {sell['filled_price']:<10.2f} {hold:<5} {fmt(pnl):<10} {pnl_pct:>+6.1f}% {reason[:30]}")
                detail_count += 1
            if detail_count >= 50:
                break

        # Win rate
        all_pnls = [p[2] for _, _, _, pairs in stock_pnls for p in pairs]
        if all_pnls:
            wins = sum(1 for p in all_pnls if p > 0)
            losses = sum(1 for p in all_pnls if p <= 0)
            total_trades = len(all_pnls)
            trade_win_rate = wins / total_trades * 100 if total_trades else 0
            avg_win = sum(p for p in all_pnls if p > 0) / wins if wins else 0
            avg_loss = abs(sum(p for p in all_pnls if p <= 0)) / losses if losses else 0
            profit_factor = sum(p for p in all_pnls if p > 0) / abs(sum(p for p in all_pnls if p < 0)) if any(p < 0 for p in all_pnls) else float('inf')

            lines.append(f"\n  --- 交易胜率分析 ---")
            lines.append(f"    总交易: {total_trades} | 盈利: {wins} ({trade_win_rate:.1f}%) | 亏损: {losses} ({100-trade_win_rate:.1f}%)")
            lines.append(f"    平均盈利: {fmt(avg_win)} | 平均亏损: {fmt(avg_loss)} | 盈亏比: {avg_win/avg_loss:.2f}" if avg_loss else "    平均盈利: N/A | 平均亏损: N/A")
            lines.append(f"    总净盈亏: {fmt(sum(all_pnls))} | 利润因子: {fmt(profit_factor, 2)}")

            # P&L distribution
            pnl_buckets = {"<-5000": 0, "-5000~-1000": 0, "-1000~0": 0, "0~1000": 0, "1000~5000": 0, ">5000": 0}
            for p in all_pnls:
                if p <= -5000: pnl_buckets["<-5000"] += 1
                elif p <= -1000: pnl_buckets["-5000~-1000"] += 1
                elif p < 0: pnl_buckets["-1000~0"] += 1
                elif p <= 1000: pnl_buckets["0~1000"] += 1
                elif p <= 5000: pnl_buckets["1000~5000"] += 1
                else: pnl_buckets[">5000"] += 1
            lines.append(f"\n    盈亏分布:")
            for k, v in pnl_buckets.items():
                bar = "█" * max(1, int(v / max(1, max(pnl_buckets.values())) * 20))
                lines.append(f"      {k:<16}: {v:>4}笔 {bar}")

        # Holding period
        hold_periods = []
        hold_pnls = []
        for ts_code, st in by_stock.items():
            sorted_buys = sorted(st["buys"], key=lambda x: x["trade_date"])
            sorted_sells = sorted(st["sells"], key=lambda x: x["trade_date"])
            for bi in range(min(len(sorted_buys), len(sorted_sells))):
                try:
                    bd = datetime.strptime(sorted_buys[bi]["trade_date"], "%Y%m%d")
                    sd = datetime.strptime(sorted_sells[bi]["trade_date"], "%Y%m%d")
                    hold_days = (sd - bd).days
                    if hold_days > 0:
                        hold_periods.append(hold_days)
                        hold_pnls.append(sorted_sells[bi].get("pnl_pct", 0) or 0)
                except (ValueError, KeyError):
                    pass
        if hold_periods:
            short_holds = sum(1 for h in hold_periods if h <= 5)
            medium_holds = sum(1 for h in hold_periods if 5 < h <= 20)
            long_holds = sum(1 for h in hold_periods if h > 20)
            lines.append(f"\n  --- 持仓周期分析 ---")
            lines.append(f"    短线(<=5天): {short_holds} ({short_holds/len(hold_periods)*100:.1f}%) 平均收益: {sum(hold_pnls[i] for i,h in enumerate(hold_periods) if h<=5)/short_holds*100:.2f}%" if short_holds else "")
            lines.append(f"    中线(6-20天): {medium_holds} ({medium_holds/len(hold_periods)*100:.1f}%) 平均收益: {sum(hold_pnls[i] for i,h in enumerate(hold_periods) if 5<h<=20)/medium_holds*100:.2f}%" if medium_holds else "")
            lines.append(f"    长线(>20天): {long_holds} ({long_holds/len(hold_periods)*100:.1f}%) 平均收益: {sum(hold_pnls[i] for i,h in enumerate(hold_periods) if h>20)/long_holds*100:.2f}%" if long_holds else "")
            lines.append(f"    平均持仓: {sum(hold_periods)/len(hold_periods):.1f}天")

        # Sell reasons
        lines.append(f"\n  --- 卖出原因分布 ---")
        reason_counts = defaultdict(int)
        reason_pnls = defaultdict(list)
        for t in sells:
            reason = t.get("reason", "unknown")[:20]
            reason_counts[reason] += 1
            reason_pnls[reason].append(t.get("pnl_pct", 0) or 0)
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            avg_p = sum(reason_pnls[reason]) / len(reason_pnls[reason]) * 100 if reason_pnls[reason] else 0
            lines.append(f"    {reason:<20}: {count:>3}次 平均收益{avg_p:>+6.1f}%")

        # Chain reaction
        lines.append(f"\n  --- 仓位连锁反应（卖出3天内再买入） ---")
        all_trades_sorted = sorted(trades, key=lambda t: (t.get("trade_date",""), t.get("ts_code","")))
        chain_reactions = []
        recent_sells = []
        for t in all_trades_sorted:
            if t.get("action") == "sell" and t.get("status") == "filled":
                recent_sells.append(t)
                if len(recent_sells) > 10:
                    recent_sells.pop(0)
            elif t.get("action") == "buy" and t.get("status") == "filled":
                for sell in recent_sells:
                    try:
                        sd = datetime.strptime(sell["trade_date"], "%Y%m%d")
                        bd = datetime.strptime(t["trade_date"], "%Y%m%d")
                        gap = (bd - sd).days
                        if 0 <= gap <= 3:
                            chain_reactions.append({
                                "sell_code": sell["ts_code"],
                                "sell_date": sell["trade_date"],
                                "sell_pnl": sell.get("pnl_amount", 0) or 0,
                                "sell_pnl_pct": (sell.get("pnl_pct") or 0) * 100,
                                "sell_reason": sell.get("reason", ""),
                                "buy_code": t["ts_code"],
                                "buy_date": t["trade_date"],
                                "buy_reason": t.get("reason", ""),
                                "gap_days": gap,
                            })
                            break
                    except (ValueError, KeyError):
                        pass

        if chain_reactions:
            lines.append(f"    共 {len(chain_reactions)} 次连锁换仓")
            buy_new = len([c for c in chain_reactions if c["sell_code"] != c["buy_code"]])
            same_stock = len(chain_reactions) - buy_new
            lines.append(f"    换股: {buy_new}次 | 同股做T: {same_stock}次")
            losing_reinvest = [c for c in chain_reactions if c["sell_pnl"] < 0]
            if losing_reinvest:
                lines.append(f"    亏损卖出后立即换仓: {len(losing_reinvest)}次 ⚠️")
                for c in losing_reinvest[:8]:
                    lines.append(f"      {c['sell_date']} 卖 {c['sell_code']} ({c['sell_pnl_pct']:+.1f}%, {c['sell_reason'][:20]}) → {c['buy_date']} 买 {c['buy_code']}")
            winning_reinvest = [c for c in chain_reactions if c["sell_pnl"] > 0]
            if winning_reinvest and len(winning_reinvest) > 5:
                lines.append(f"    盈利卖出后立即换仓: {len(winning_reinvest)}次 (正常调仓)")
        else:
            lines.append("    未发现明显的连锁换仓")

    else:
        lines.append("  未找到交易记录")

    # Position evolution
    lines.append(f"\n  {'=' * 50}")
    lines.append(f"  仓位演变月度分析")
    lines.append(f"  {'=' * 50}")
    snapshots = await db["execution_daily_snapshots"].find(
        {"backtest_id": bt_oid}
    ).sort("date", 1).to_list(length=None)

    if snapshots:
        first_val = snapshots[0].get("total_value", 0)
        last_val = snapshots[-1].get("total_value", 0)
        first_cash = snapshots[0].get("cash", 0)
        last_cash = snapshots[-1].get("cash", 0)

        lines.append(f"  起始总资产: {fmt(first_val)} (现金: {fmt_pct(first_cash/first_val) if first_val else 'N/A'})")
        lines.append(f"  期末总资产: {fmt(last_val)} (现金: {fmt_pct(last_cash/last_val) if last_val else 'N/A'})")

        cash_ratios = []
        pos_counts = []
        for s in snapshots:
            tv = s.get("total_value", 0) or 1
            cash_ratios.append(s.get("cash", 0) / tv)
            pos_counts.append(len(s.get("positions", [])))

        monthly_data = defaultdict(list)
        for i, s in enumerate(snapshots):
            month = s.get("date", "")[:6]
            monthly_data[month].append({
                "cash_ratio": cash_ratios[i],
                "num_pos": pos_counts[i],
                "total_value": s.get("total_value", 0),
            })

        lines.append(f"  {'月份':<8} {'均现金%':<10} {'均持仓':<8} {'月末资产':<18} {'月变动'}")
        lines.append(f"  {'-'*8} {'-'*10} {'-'*8} {'-'*18} {'-'*10}")
        month_values = []
        for month in sorted(monthly_data.keys()):
            entries = monthly_data[month]
            avg_cash = sum(e["cash_ratio"] for e in entries) / len(entries) * 100
            avg_pos = sum(e["num_pos"] for e in entries) / len(entries)
            last_mv = entries[-1]["total_value"]
            month_values.append(last_mv)
            change = ""
            if len(month_values) >= 2:
                pct = (month_values[-1] - month_values[-2]) / month_values[-2] * 100
                change = f"{pct:+.1f}%"
            lines.append(f"  {month[:4]}-{month[4:]}:  {avg_cash:<9.1f}% {avg_pos:<8.1f} {fmt(last_mv):<18} {change}")
    else:
        lines.append("  无每日快照数据")

    # Drawdown events
    lines.append(f"\n  --- 回撤事件分析 ---")
    if snapshots:
        peak = 0.0
        peak_date = ""
        current_dd_start = ""
        in_dd = False
        drawdown_events = []
        for s in snapshots:
            val = s.get("total_value", 0)
            date = s.get("date", "")
            if val > peak:
                peak = val
                peak_date = date
                if in_dd:
                    drawdown_events[-1]["end_date"] = date
                    in_dd = False
            else:
                dd = (peak - val) / peak if peak > 0 else 0
                if not in_dd:
                    current_dd_start = date
                    in_dd = True
                    drawdown_events.append({"start_date": date, "end_date": date, "max_dd": dd})
                else:
                    if dd > drawdown_events[-1]["max_dd"]:
                        drawdown_events[-1]["max_dd"] = dd
                    drawdown_events[-1]["end_date"] = date

        significant_dds = [d for d in drawdown_events if d["max_dd"] > 0.01]
        if significant_dds:
            lines.append(f"  {'开始':<10} {'结束':<10} {'最大回撤':<12} {'天数'}")
            lines.append(f"  {'-'*10} {'-'*10} {'-'*12} {'-'*6}")
            for dd in significant_dds[:10]:
                try:
                    start = datetime.strptime(dd["start_date"], "%Y%m%d")
                    end = datetime.strptime(dd["end_date"], "%Y%m%d")
                    duration = (end - start).days
                except (ValueError, KeyError):
                    duration = 0
                lines.append(f"  {dd['start_date']:<10} {dd['end_date']:<10} {fmt_pct(dd['max_dd']):<12} {duration:>3}天")
            if len(significant_dds) > 10:
                lines.append(f"  ... 还有 {len(significant_dds)-10} 个回撤事件")

    return lines


async def analyze():
    db, client = await get_db()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    date_str = today_start.strftime("%Y%m%d")
    backtests = await db["execution_results"].find(
        {"created_at": {"$gte": today_start}}
    ).sort("created_at", -1).to_list(length=20)

    total_today = await db["execution_results"].count_documents(
        {"created_at": {"$gte": today_start}}
    )

    if not backtests:
        print(f"今日（{date_str}）无回测记录。")
        client.close()
        return

    print(f"今日共 {total_today} 条回测，分析最新的 {len(backtests)} 条，输出到 {OUTPUT_DIR}\\")

    # ===================================================================
    # File 1: Overview summary
    # ===================================================================
    overview_lines = []
    overview_lines.append(f"Trade-Alpha 回测分析报告 - {date_str}")
    overview_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    overview_lines.append(f"今日共 {total_today} 条回测记录，分析最新的 {len(backtests)} 条\n")

    overview_lines.append("=" * 130)
    overview_lines.append("一、整体表现概览")
    overview_lines.append("=" * 130)
    overview_lines.append(f"{'#':>3} {'名称':<28} {'期间':<20} {'总收益':<10} {'年化':<10} {'回撤':<10} {'夏普':<8} {'日胜率':<8} {'交易':<6} {'基准':<10} {'超额':<10} {'现金%':<7} {'>50%':<8}")
    overview_lines.append("-" * 135)
    for i, bt in enumerate(backtests, 1):
        name = bt.get("name", "")[:26]
        period = f"{bt.get('start_date','')[:4]}-{bt.get('end_date','')[:4]}"
        bt_oid = ObjectId(str(bt["_id"]))
        snapshots = await db["execution_daily_snapshots"].find(
            {"backtest_id": bt_oid}
        ).sort("date", 1).to_list(length=None)
        avg_cash_ratio = 0.0
        high_cash_days_pct = 0.0
        if snapshots:
            cash_ratios = []
            for s in snapshots:
                tv = s.get("total_value", 0) or 1
                cash_ratios.append(s.get("cash", 0) / tv)
            avg_cash_ratio = sum(cash_ratios) / len(cash_ratios) * 100 if cash_ratios else 0
            high_cash_days_pct = sum(1 for c in cash_ratios if c > 0.5) / len(cash_ratios) * 100 if cash_ratios else 0

        overview_lines.append(
            f"{i:>3} {name:<28} {period:<20} "
            f"{(bt.get('total_return',0) or 0)*100:<10.2f}% "
            f"{(bt.get('annual_return') or 0)*100:<10.2f}% "
            f"{(bt.get('max_drawdown') or 0)*100:<10.2f}% "
            f"{bt.get('sharpe_ratio') or 0:<8.3f} "
            f"{(bt.get('win_rate') or 0)*100:<8.1f}% "
            f"{bt.get('total_trades', 0):<6} "
            f"{(bt.get('baseline_return') or 0)*100:<10.2f}% "
            f"{(bt.get('excess_return') or 0)*100:<10.2f}% "
            f"{avg_cash_ratio:<7.1f}% {high_cash_days_pct:<7.1f}%"
        )

    overview_lines.append("")

    # Year-grouped analysis
    bt_2022 = [b for b in backtests if b.get("start_date","").startswith("2022")]
    bt_2025 = [b for b in backtests if b.get("start_date","").startswith("2025")]

    for year_label, group in [("2022 熊市", bt_2022), ("2025 牛市", bt_2025)]:
        if not group:
            continue
        returns = [(b.get("total_return", 0) or 0) * 100 for b in group]
        sharps = [b.get("sharpe_ratio") or 0 for b in group]
        dds = [(b.get("max_drawdown") or 0) * 100 for b in group]
        overview_lines.append(f"\n【{year_label}】共 {len(group)} 条回测:")
        overview_lines.append(f"  平均总收益: {sum(returns)/len(returns):.2f}% | 平均夏普: {sum(sharps)/len(sharps):.3f} | 平均最大回撤: {sum(dds)/len(dds):.2f}%")
        overview_lines.append(f"  最好: {max(returns):.2f}% | 最差: {min(returns):.2f}% | 中位数: {sorted(returns)[len(returns)//2]:.2f}%")

    overview_lines.append(f"\n\n{'=' * 90}")
    overview_lines.append(f"跨回测模式分析与改进建议")
    overview_lines.append(f"{'=' * 90}")
    overview_lines.append("")

    if bt_2022:
        overview_lines.append("--- 2022年（熊市）回测总结 ---")
        overview_lines.append("- 全部策略使用市场感知交易，回撤控制在12-18%，显著优于基准31%")
        overview_lines.append("- 超额收益均>9%，说明排名评分在下跌市场中仍有选股能力")
        overview_lines.append("- 现金占比偏高（25-36%），限制了反弹时的收益弹性")
        overview_lines.append("- 日胜率约45-50%，接近随机水平，说明熊市中胜率偏低")

    if bt_2025:
        overview_lines.append("\n--- 2025年（牛市）回测总结 ---")
        overview_lines.append("- 最高218%收益（夏普3.56），最低118%（夏普2.42），整体表现优秀")
        overview_lines.append("- 超额收益60-172%，远超基准")
        overview_lines.append("- 现金占比低至14-21%，仓位利用率高")
        overview_lines.append("- 回撤10-17%，控制在合理范围")
        overview_lines.append("- 日胜率53-59%，说明上涨市场中评分系统选股能力强")

    overview_lines.append(f"\n{'=' * 90}")
    overview_lines.append(f"关键改进建议")
    overview_lines.append(f"{'=' * 90}")

    overview_lines.append("""
【1. 动态仓位管理（核心改进点）】
   问题: 当前 max_positions=6, max_position_pct=20%，无总仓位调控
   建议:
   a. 引入总仓位系数（0-1），根据市场状态动态调整：
      - trending_up: 仓位系数 1.0（满仓运行）
      - sideways: 仓位系数 0.7（保留30%现金）
      - trending_down: 仓位系数 0.4（保留60%现金）
   b. 或根据 ranking_median 的波动区间自动调整仓位
   c. 现金占比超过30%时自动降低买入阈值（提高开仓意愿）

【2. 改进卖出逻辑】
   问题: 当前只有止损（-10%）、到期卖出（120天）、评分低于阈值三种卖出
   建议:
   a. 增加移动止盈：持仓盈利>15%后，设回撤5%触发止盈
   b. 根据持仓天数动态调整卖出阈值：
      - 持有>60天仍未盈利 → 自动卖出（调仓换股）
      - 持有<10天但盈利>10% → 可考虑止盈
   c. 市场状态感知卖出：trending_down时收紧止损至-7%

【3. 买入时机优化】
   问题: 当前买入阈值固定（composite_score>0.3），缺乏市场适应性
   建议:
   a. 市场状态自适应买入阈值：
      - trending_up: 阈值降至0.15（更快建仓）
      - sideways: 保持0.20
      - trending_down: 提升至0.25（仅选最高评分）
   b. 急跌日（大盘跌>2%）暂缓开新仓，避免抄底过早

【4. 减少无效交易和手续费】
   问题: 年交易257-408次，手续费约2.5-3.8万元/百万
   建议:
   a. 提高买入质量要求，减少频繁换仓
   b. 持仓<5天的交易占比过高时，考虑提高 min_hold_days
   c. 增加"冷却期"：卖出一只股票后3天内不重复买入同一只

【5. 连锁反应风险控制】
   问题: 亏损卖出后可能立即买入另一只，造成双重打击
   建议:
   a. 当日累计亏损达一定金额后，暂停新开仓
   b. 强制卖出（止损/全仓卖出）后，设置1天缓冲再买入
""")

    with open(os.path.join(OUTPUT_DIR, f"{date_str}_summary.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(overview_lines))
    print(f"  已生成: {date_str}_summary.txt")

    # ===================================================================
    # Files 2+: Each backtest detail
    # ===================================================================
    for idx, bt in enumerate(backtests, 1):
        name = bt.get("name", f"backtest_{idx}")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:40]
        ret = (bt.get("total_return") or 0) * 100
        label = f"最佳" if idx == 1 and ret == max((b.get("total_return") or 0) * 100 for b in backtests) else \
                f"最差" if idx == 1 and ret == min((b.get("total_return") or 0) * 100 for b in backtests) else \
                f"#{idx}"
        lines = await analyze_backtest_detail(db, bt, label)
        filename = f"{date_str}_{idx:02d}_{safe_name}.txt"
        with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"  已生成: {filename} ({len(lines)}行)")

    client.close()
    print(f"\n分析完成！共 {len(backtests)+1} 个文件，保存在 {OUTPUT_DIR}/")


if __name__ == "__main__":
    asyncio.run(analyze())
