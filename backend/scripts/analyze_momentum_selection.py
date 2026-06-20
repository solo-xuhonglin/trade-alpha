"""Analyze momentum stock selection: selected stocks' future 2-month performance.

Usage: python scripts/analyze_momentum_selection.py
"""
import asyncio, json
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao import TradeCalendar, StockListHistory
from trade_alpha.dao.stock_daily import StockDaily

# Replicate provider logic
MOMENTUM_FIELDS = [
    "trend_slope_20", "trend_arrangement_20",
    "close_position_20", "close_position_60",
    "bias_20", "bias_60",
]
TOP_N = 100      # base group size
RANGE_N = 300    # universe size
MOMENTUM_N = 20  # momentum group size
LOOKAHEAD_MONTHS = 2  # months to track after selection


def next_trade_date(date_str: str, calendar_dates: List[str]) -> Optional[str]:
    """Get next trading day after date_str."""
    for d in sorted(calendar_dates):
        if d > date_str:
            return d
    return None


async def main():
    await init_db()

    # Get calendar
    all_cal = await TradeCalendar.find(
        TradeCalendar.is_open == 1,
    ).sort(TradeCalendar.cal_date).to_list()
    cal_dates = [c.cal_date for c in all_cal]

    # Select 4 sample months across different market conditions
    sample_months = ["202307", "202310", "202401", "202407"]

    for month_key in sample_months:
        # Find first trading day of the month
        first_dates = [d for d in cal_dates if d.startswith(month_key)]
        if not first_dates:
            continue
        trade_date = first_dates[0]
        print(f"\n{'='*80}")
        print(f"=== 筛选月份: {month_key} (交易日: {trade_date}) ===")

        # --- Step 1: Query universe (top 300 by MV) ---
        universe_records = await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            StockListHistory.total_mv != None,
        ).sort(-StockListHistory.total_mv).limit(RANGE_N).to_list()
        universe_codes = [r.ts_code for r in universe_records]
        mv_group = universe_codes[:TOP_N]

        # --- Step 2: Momentum selection (same logic as provider) ---
        records = await StockDaily.find(
            StockDaily.trade_date == trade_date,
            In(StockDaily.ts_code, universe_codes),
            StockDaily.trend_slope_20 != None,
            StockDaily.trend_arrangement_20 != None,
            StockDaily.close_position_20 != None,
            StockDaily.close_position_60 != None,
            StockDaily.bias_20 != None,
            StockDaily.bias_60 != None,
        ).to_list()

        stock_values: Dict[str, List[float]] = {}
        stock_details: Dict[str, dict] = {}
        for r in records:
            vals = [getattr(r, f) for f in MOMENTUM_FIELDS]
            if all(v is not None for v in vals):
                stock_values[r.ts_code] = vals
                stock_details[r.ts_code] = {f: getattr(r, f) for f in MOMENTUM_FIELDS +
                    ["close", "pct_chg", "ma_20", "ma_60", "vol_ratio_20", "rsi_12"]}

        # Compute momentum scores
        n_fields = len(MOMENTUM_FIELDS)
        composite: Dict[str, int] = {ts: 0 for ts in stock_values}
        for fi in range(n_fields):
            ranked = sorted(stock_values.items(), key=lambda x: x[1][fi])
            for rank, (ts, _) in enumerate(ranked):
                composite[ts] += rank
        sorted_momentum = sorted(composite.items(), key=lambda x: x[1], reverse=True)
        momentum_selected = [ts for ts, _ in sorted_momentum[:MOMENTUM_N]]

        # --- Step 3: Analyze selected stocks ---
        # Stocks in base group
        base_set = set(mv_group)
        momentum_in_base = [s for s in momentum_selected if s in base_set]
        momentum_not_in_base = [s for s in momentum_selected if s not in base_set]

        print(f"  范围池(300): {len(universe_codes)} 只")
        print(f"  基础池(100): {len(mv_group)} 只")
        print(f"  动量池(20): {len(momentum_selected)} 只")
        print(f"    其中已在基础池: {len(momentum_in_base)} 只")
        print(f"    其中不在基础池: {len(momentum_not_in_base)} 只")

        # Show top 10 momentum stocks with their indicators
        print(f"\n  动量前10详细指标:")
        print(f"  {'股票':<12} {'排名分':>5} {'close':>8} {'slope_20':>8} {'arrange20':>9} {'pos20':>6} {'pos60':>6} {'bias20':>7} {'bias60':>7} {'rsi12':>6}")
        for ts, score in sorted_momentum[:10]:
            d = stock_details.get(ts, {})
            print(f"  {ts:<12} {score:>5} {d.get('close',0):>8.2f} {d.get('trend_slope_20',0):>8.4f} {d.get('trend_arrangement_20',0):>9.4f} {d.get('close_position_20',0):>6.1f} {d.get('close_position_60',0):>6.1f} {d.get('bias_20',0):>7.2f} {d.get('bias_60',0):>7.2f} {d.get('rsi_12',0):>6.1f}")

        # --- Step 4: Check 2-month future performance ---
        # Find trading days ~2 months ahead
        month_dt = datetime.strptime(trade_date, "%Y%m%d")
        future_start = month_dt + timedelta(days=30)
        future_end = month_dt + timedelta(days=70)
        future_dates = [d for d in cal_dates if future_start.strftime("%Y%m%d") <= d <= future_end.strftime("%Y%m%d")]

        if len(future_dates) >= 2:
            check_date = future_dates[-1]  # ~2 months later
            # Get close prices on selection day and future day
            sel_records = {r.ts_code: r for r in records}
            fut_records_list = await StockDaily.find(
                StockDaily.trade_date == check_date,
                In(StockDaily.ts_code, momentum_selected + mv_group),
            ).to_list()
            fut_map = {r.ts_code: r for r in fut_records_list}

            # Calculate returns for momentum group
            print(f"\n  未来2个月表现 ({trade_date} → {check_date}):")
            print(f"  {'股票':<12} {'选时价':>8} {'未来价':>8} {'收益%':>7} {'方向':>4}")

            momentum_returns = []
            for ts in momentum_selected:
                sel_r = sel_records.get(ts)
                fut_r = fut_map.get(ts)
                if sel_r and fut_r and hasattr(sel_r, 'close') and hasattr(fut_r, 'close'):
                    sel_close = sel_r.close
                    fut_close = fut_r.close
                    if sel_close and fut_close and sel_close > 0:
                        ret = (fut_close - sel_close) / sel_close * 100
                        direction = "↑" if ret > 0 else "↓"
                        momentum_returns.append(ret)
                        if len([r for r in momentum_returns if len(momentum_returns) <= 10]):
                            print(f"  {ts:<12} {sel_close:>8.2f} {fut_close:>8.2f} {ret:>7.2f} {direction:>4}")

            if momentum_returns:
                avg_ret = sum(momentum_returns) / len(momentum_returns)
                win_rate = sum(1 for r in momentum_returns if r > 0) / len(momentum_returns) * 100
                print(f"  动量组平均收益: {avg_ret:+.2f}%  胜率: {win_rate:.0f}%")

            # Calculate returns for base group
            base_returns = []
            for ts in mv_group:
                sel_r = sel_records.get(ts)
                fut_r = fut_map.get(ts)
                if sel_r and fut_r and hasattr(sel_r, 'close') and hasattr(fut_r, 'close'):
                    sel_close = sel_r.close
                    fut_close = fut_r.close
                    if sel_close and fut_close and sel_close > 0:
                        ret = (fut_close - sel_close) / sel_close * 100
                        base_returns.append(ret)

            if base_returns:
                avg_base = sum(base_returns) / len(base_returns)
                win_base = sum(1 for r in base_returns if r > 0) / len(base_returns) * 100
                print(f"  基础组平均收益: {avg_base:+.2f}%  胜率: {win_base:.0f}%")
                print(f"  动量vs基础差异: {avg_ret - avg_base:+.2f}%" if momentum_returns else "")
        else:
            print(f"  (未来2个月数据不足)")


    # --- Step 5: Summary across months ---
    print(f"\n{'='*80}")
    print("=== 总结 ===")
    print("动量选股使用6指标排名法(排名和越低越好):")
    for f in MOMENTUM_FIELDS:
        print(f"  - {f}")
    print(f"\n参数: range_n={RANGE_N}, top_n={TOP_N}, momentum_n={MOMENTUM_N}")
    print("注意: 动量组和基础组有重叠（部分动量股已在基础池中）")
    print("最终候选池 = dedup(基础组 ∪ 动量组 + 上月留存)")


asyncio.run(main())
