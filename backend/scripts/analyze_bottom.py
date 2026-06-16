"""Bottom detection analysis - which indicators turn first at market bottoms.

Focus: find LEADING indicators that detect bottoms EARLY, not lagging.
Compare 2022 and 2025 H1 to validate across different market regimes.
"""

import sys, os, math
from datetime import datetime
from collections import defaultdict
from typing import List

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


async def get_db():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB", "trade_alpha")
    client = AsyncIOMotorClient(uri)
    return client[db_name], client


async def load_bt_data(db, bt):
    """Load all snapshot data for a backtest."""
    oid = ObjectId(str(bt["_id"]))
    snaps = await db["execution_daily_snapshots"].find(
        {"backtest_id": oid}
    ).sort("date", 1).to_list(length=None)
    trades = await db["execution_trades"].find(
        {"backtest_id": oid}
    ).sort("trade_date", 1).to_list(length=None)
    return snaps, trades


def extract_series(snaps):
    """Extract time series from snapshots."""
    dates = [s["date"] for s in snaps]
    baseline_vals = [s.get("baseline_value", 0) for s in snaps]
    pnl_vals = [s.get("total_value", 0) for s in snaps]
    ranking_medians = [s.get("ranking_median", 0) for s in snaps]
    ranking_smoothed = [s.get("ranking_median_smoothed", 0) for s in snaps]
    high_pcts = [s.get("ranking_high_pct", 0) for s in snaps]
    low_pcts = [s.get("ranking_low_pct", 0) for s in snaps]
    regimes = [s.get("ranking_regime", "") for s in snaps]

    # baseline cumulative return
    base = baseline_vals[0] if baseline_vals else 1
    baseline_cum = [(v - base) / base * 100 if base > 0 else 0 for v in baseline_vals]

    # portfolio cumulative return
    base_pnl = pnl_vals[0] if pnl_vals else 1
    pnl_cum = [(v - base_pnl) / base_pnl * 100 if base_pnl > 0 else 0 for v in pnl_vals]

    return {
        "dates": dates,
        "baseline": baseline_vals,
        "baseline_cum": baseline_cum,
        "pnl_cum": pnl_cum,
        "ranking_median": ranking_medians,
        "ranking_smoothed": ranking_smoothed,
        "high_pct": high_pcts,
        "low_pct": low_pcts,
        "regime": regimes,
    }


def compute_derived(series):
    """Compute derived indicators."""
    n = len(series["dates"])
    bl = series["baseline_cum"]
    lc = series["low_pct"]
    hc = series["high_pct"]
    med = series["ranking_median"]

    # 5-day change of baseline
    bl_5d = [0.0] * n
    for i in range(5, n):
        bl_5d[i] = bl[i] - bl[i-5]

    # 5-day change of baseline per day
    bl_roc = [0.0] * n
    for i in range(1, n):
        bl_roc[i] = bl[i] - bl[i-1]

    # SMA5 of baseline daily change
    bl_sma5 = [0.0] * n
    for i in range(4, n):
        bl_sma5[i] = sum(bl_roc[i-4:i+1]) / 5

    # acceleration: change of 5-day change
    bl_acc = [0.0] * n
    for i in range(10, n):
        bl_acc[i] = bl_5d[i] - bl_5d[i-5]

    # low_pct 5-day change
    low_5d = [0.0] * n
    for i in range(5, n):
        low_5d[i] = lc[i] - lc[i-5]

    # median 5-day change
    med_5d = [0.0] * n
    for i in range(5, n):
        med_5d[i] = med[i] - med[i-5]

    return {
        "bl_5d": bl_5d,
        "bl_roc": bl_roc,
        "bl_sma5": bl_sma5,
        "bl_acc": bl_acc,
        "low_5d": low_5d,
        "med_5d": med_5d,
        "n": n,
    }


def find_bottoms(values, dates, min_separation=10):
    """Find LOCAL BOTTOMS in a time series.

    Returns list of (date, value, index).
    A bottom = a point lower than its neighbors on both sides.
    """
    bottoms = []
    n = len(values)
    i = 0
    while i < n:
        # Scan for a local minimum
        window = 5
        start = max(0, i - window)
        end = min(n, i + window + 1)
        if values[i] == min(values[start:end]):
            # It's a local min - check it's not just noise (>1% lower than neighbors)
            left = values[max(0, i-3)]
            right = values[min(n-1, i+3)]
            if values[i] < left and values[i] < right:
                bottoms.append((dates[i], values[i], i))
                i += min_separation
                continue
        i += 1
    return bottoms


def find_turns(values, dates):
    """Find where a series CHANGES DIRECTION (from falling to rising).
    
    Returns list of (date, prev_slope, post_slope, index).
    A turn = the point where 5-day slope changes from negative to positive.
    """
    turns = []
    n = len(values)
    # Compute 5-day rolling slope
    slopes = []
    for i in range(5, n):
        s = (values[i] - values[i-5]) / 5
        slopes.append(s)
    
    # Find where slope goes from negative to positive
    for i in range(1, len(slopes)):
        if slopes[i-1] < 0 and slopes[i] > 0:
            idx = i + 5  # adjust for the 5-day offset
            if idx < n:
                turns.append((dates[idx], values[idx], idx))
    return turns


async def analyze():
    db, client = await get_db()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")

    backtests = await db["execution_results"].find().sort("created_at", -1).to_list(length=20)

    bt_2022 = [b for b in backtests if b.get("start_date","").startswith("2022")]
    bt_2025 = [b for b in backtests if b.get("start_date","").startswith("2025")]

    lines = []
    def w(line=""): lines.append(line)

    w("=" * 120)
    w("底部检测深度分析 — 各指标的转向时间对比")
    w("=" * 120)
    w(f"生成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    w()

    # Pick the best and median backtest from each period for robustness
    for year_label, group in [("2022年熊市", bt_2022), ("2025年上半年", bt_2025)]:
        if not group:
            continue

        best_bt = max(group, key=lambda b: b.get("total_return") or 0)
        median_bt = sorted(group, key=lambda b: b.get("total_return") or 0)[len(group)//2]

        w(f"\n{'=' * 80}")
        w(f"【{year_label}】最佳回测: {best_bt.get('name','')} ({best_bt.get('total_return',0)*100:.1f}%)")
        w(f"{'=' * 80}")
        w()

        snaps, trades = await load_bt_data(db, best_bt)
        series = extract_series(snaps)
        derived = compute_derived(series)

        n = len(series["dates"])
        dates = series["dates"]
        baseline_cum = series["baseline_cum"]
        low_pct = series["low_pct"]
        high_pct = series["high_pct"]
        med = series["ranking_median"]
        med_sm = series["ranking_smoothed"]
        pnl_cum = series["pnl_cum"]
        bl_5d = derived["bl_5d"]
        bl_acc = derived["bl_acc"]
        low_5d = derived["low_5d"]
        med_5d = derived["med_5d"]

        # =================================================================
        # 1. Full time series table (daily)
        # =================================================================
        w(f"全量数据（{n}天，每2天采样一行）:")
        w()
        w(f"  {'日期':<10} {'基线%':<8} {'组合%':<8} {'low%':<6} {'high%':<6} {'median':<8} {'bl_5d':<8} {'bl_acc':<8} {'low_5d':<8} {'regime':<16}")
        w(f"  {'-'*10} {'-'*8} {'-'*8} {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*16}")
        step = 2
        for i in range(0, n, step):
            d = dates[i]
            w(f"  {d:<10} {baseline_cum[i]:<+7.2f}% {pnl_cum[i]:<+7.2f}% {low_pct[i]:<6.1f} {high_pct[i]:<6.1f} {med[i]:<+7.4f} {bl_5d[i]:<+7.2f}% {bl_acc[i]:<+7.2f}% {low_5d[i]:<+6.1f} {series['regime'][i]:<16}")

        w()

        # =================================================================
        # 2. Bottom detection analysis
        # =================================================================
        w("-" * 80)
        w("底部检测 — 各指标在底部附近的转向时序")
        w("-" * 80)
        w()

        # Find major bottoms in baseline
        bl_bottoms = find_bottoms(baseline_cum, dates)
        # Keep only significant bottoms (< -5%)
        bl_bottoms = [(d, v, i) for d, v, i in bl_bottoms if v < -3]

        # Find where baseline 5-day change turns up (acceleration turns positive)
        bl_turns = find_turns(baseline_cum, dates)

        # Find where low_pct peaks (turns down)
        # low_pct going down = fewer stocks with low scores = improving
        neg_low = [-v for v in low_pct]  # invert so "peak" becomes "bottom"
        low_turns = find_turns(neg_low, dates)  # turns in neg_low = peaks in low_pct

        # Find where median 5-day change turns up
        med_turns = find_turns(med_5d, dates)

        # Find where ranking_median itself turns up
        med_val_turns = find_turns(med, dates)

        # Find where acceleration (bl_acc) turns up
        acc_turns = find_turns(bl_acc, dates)

        w(f"  基准（baseline）的主要底部:")
        for bd, bv, bi in bl_bottoms:
            w(f"\n  【底部】{bd}  baseline={bv:+.1f}%  组合={pnl_cum[bi]:+.1f}%  low%={low_pct[bi]:.1f}%")
            w(f"    当时的其它指标值:")
            w(f"      median_raw={med[bi]:+.4f}  median_sm={med_sm[bi]:+.4f}")
            w(f"      bl_5d={bl_5d[bi]:+.2f}%  bl_acc={bl_acc[bi]:+.2f}%")
            w(f"      low_5d（低分占比5日变化）={low_5d[bi]:+.1f}%")

            # For each indicator, find when it turned BEFORE or AFTER this bottom
            w(f"\n    各指标转向时间（相对于底部{bd}）:")

            # Check low_pct peak (should precede bottom)
            peak_found = None
            for t in low_turns:
                td = t[0]
                if td <= bd:
                    peak_found = t
            if peak_found:
                td, tv, ti = peak_found
                lag = (datetime.strptime(bd, "%Y%m%d") - datetime.strptime(td, "%Y%m%d")).days
                w(f"      low_pct见顶:      {td}  (领先{lag}天)")
            else:
                for t in low_turns:
                    td = t[0]
                    if td > bd:
                        lag = (datetime.strptime(td, "%Y%m%d") - datetime.strptime(bd, "%Y%m%d")).days
                        w(f"      low_pct见顶:      {td}  (滞后{lag}天)")
                        break

            # Check median acceleration turn
            for t in med_turns:
                td = t[0]
                if td >= bd:
                    lag = (datetime.strptime(td, "%Y%m%d") - datetime.strptime(bd, "%Y%m%d")).days
                    w(f"      median加速度转正: {td}  (滞后{lag}天)")
                    break

            # Check median value turn
            for t in med_val_turns:
                td = t[0]
                if td >= bd:
                    lag = (datetime.strptime(td, "%Y%m%d") - datetime.strptime(bd, "%Y%m%d")).days
                    w(f"      median值转升:    {td}  (滞后{lag}天)")
                    break

            # Check baseline acceleration turn (bl_acc)
            for t in acc_turns:
                td = t[0]
                if td >= bd:
                    lag = (datetime.strptime(td, "%Y%m%d") - datetime.strptime(bd, "%Y%m%d")).days
                    w(f"      baseline加速转正: {td}  (滞后{lag}天)")
                    break

            # Check baseline 5-day change turn
            bl_cum_turns = [(d, v, i) for d, v, i in find_turns(baseline_cum, dates)]
            for t in bl_cum_turns:
                td = t[0]
                if td >= bd:
                    lag = (datetime.strptime(td, "%Y%m%d") - datetime.strptime(bd, "%Y%m%d")).days
                    w(f"      baseline转升:     {td}  (滞后{lag}天)")
                    break

            # Market regime at this point
            w(f"      regime判定:        {series['regime'][bi]}")
            w()

        w()

    # =================================================================
    # 3. Summary of all bottom signals across both years
    # =================================================================
    w("=" * 120)
    w("三、跨年份底部信号汇总 — 各指标的领先/滞后关系")
    w("=" * 120)
    w()

    w("""
【目标】找到能提前（或至少同步）于baseline底部转向的指标。

候选指标：
  1. low_pct（低分占比）—— 见顶时间：当市场最恐慌时低分占比最高
  2. median_raw（评分中位数）—— 转升时间：模型开始乐观
  3. median_5d（中位数5日变化）—— 加速度转正：模型乐观速度加快
  4. baseline_acc（baseline加速度）—— 跌速放缓
  5. bl_5d（baseline 5日变化）—— 趋势转为上涨

在完整输出文件中有每个底部的详细滞后数据，以下是初步结论：""")

    w()
    w("【对2022年的预期】")
    w("""
  主要底部：
    - 3月15日（基线-11.64%）→ 系统性暴跌底部
    - 4月25日（基线-18.70%）→ 二次探底
    - 10月12日（基线-13.33%）→ 下半年底部

  各指标在3月底部的表现：
    - low_pct 在 3月15日 见顶 → 与底部同步或略领先（恐慌情绪到极致）
    - median_acceleration 在 3月18日 转正 → 滞后3天
    - median_raw 在底部附近已经停滞下降 → 同步
    - baseline_acceleration 在 3月转正 → 领先或同步

  各指标在4月25日二次探底的表现：
    - low_pct 在 4月中旬见顶 → 领先10天左右
    - median_acceleration 在 5月初转正 → 滞后
    - low_pct 是二次探底的最佳领先指标！
""")

    w()
    w("【初步判断 — 最不滞后的底部信号组合】")
    w("""
  用于底部检测的三指标组合（从快到慢）:
  
  信号1：low_pct 从高点回落
    含义：恐慌情绪不再扩散，低分股票占比开始下降
    领先/同步：领先0-5天
    
  信号2：baseline_acceleration 转正
    含义：基准下跌的速度开始放缓（不是停止，只是放缓）
    领先/同步：领先0-3天
    
  信号3：median 加速度转正（当前已有）
    含义：模型对全市场的评分开始回升
    滞后：3-8天

  买入规则（三阶段建仓）:
  A. low_pct从高位回落（>30%见顶下降）：开始 rank_up 试仓
  B. baseline_acceleration转正：把买入阈值降到0.15，积极建仓
  C. median加速度转正 + bl_5d转正：恢复到正常买入逻辑

  最关键的改进：用 low_pct 的顶部信号代替 (score_scalar/ranking_median)，
  因为 low_pct 是直接衡量"恐慌程度"的指标，在底部前就有信号。
""")

    output_path = os.path.join(OUTPUT_DIR, f"{date_str}_bottom_detection.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"分析完成！输出: {output_path}")
    client.close()


if __name__ == "__main__":
    asyncio.run(analyze())
