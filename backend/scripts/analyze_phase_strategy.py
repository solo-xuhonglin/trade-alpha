"""Phase analysis with daily-rebalanced baseline.

Computes a daily equal-weight baseline from predictions close prices,
compares with existing baselines, and maps current strategy logic to
each market phase. Designs phase-dependent adjustments for:
1. Avoiding full position during crashes
2. Enabling bottom-building with lowered thresholds
"""

import sys, os, math
from datetime import datetime
from collections import defaultdict
from typing import List, Dict

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


async def load_bt_data(db, bt):
    oid = ObjectId(str(bt["_id"]))
    snaps = await db["execution_daily_snapshots"].find(
        {"backtest_id": oid}
    ).sort("date", 1).to_list(length=None)
    trades = await db["execution_trades"].find(
        {"backtest_id": oid}
    ).sort("trade_date", 1).to_list(length=None)
    return snaps, trades


def compute_daily_rebalanced_baseline(snaps):
    """Compute daily equal-weight baseline from predictions close prices.
    
    Each day: equal capital to all stocks with available close price.
    Daily return = average of all stock daily returns.
    """
    n = len(snaps)
    daily_rets = [0.0] * n
    close_prices_all = []  # list of dicts: [{ts_code: close}, ...]
    
    for s in snaps:
        predictions = s.get("predictions", {})
        day_prices = {}
        for ts_code, stock_data in predictions.items():
            if isinstance(stock_data, dict):
                close = stock_data.get("close", 0)
            else:
                close = getattr(stock_data, "close", 0)
            if close and close > 0:
                day_prices[ts_code] = close
        close_prices_all.append(day_prices)
    
    cumulative = [0.0] * n
    for i in range(1, n):
        prev_prices = close_prices_all[i - 1]
        curr_prices = close_prices_all[i]
        
        # Only compute for stocks that have prices on both days
        common_codes = set(prev_prices.keys()) & set(curr_prices.keys())
        if not common_codes:
            daily_rets[i] = 0.0
            cumulative[i] = cumulative[i - 1]
            continue
        
        returns = []
        for code in common_codes:
            p_prev = prev_prices[code]
            p_curr = curr_prices[code]
            if p_prev > 0:
                returns.append((p_curr - p_prev) / p_prev)
        
        if returns:
            daily_rets[i] = sum(returns) / len(returns)
        
        cumulative[i] = (1 + cumulative[i-1]/100) * (1 + daily_rets[i]) - 1
    
    cumulative_pct = [v * 100 for v in cumulative]
    return cumulative_pct, daily_rets, close_prices_all


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
    w("阶段策略联动分析 — 新基线 + 买卖逻辑")
    w("=" * 120)
    w(f"生成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    w()

    for year_label, group in [("2022年", bt_2022), ("2025年上半年", bt_2025)]:
        if not group:
            continue
        best_bt = max(group, key=lambda b: b.get("total_return") or 0)
        
        w(f"\n{'=' * 100}")
        w(f"【{year_label}】{best_bt.get('name','')} ({best_bt.get('total_return',0)*100:.1f}%)")
        w(f"{'=' * 100}")

        snaps, trades = await load_bt_data(db, best_bt)
        dates = [s["date"] for s in snaps]
        
        # Existing series
        baseline_bh = [s.get("baseline_value", 0) for s in snaps]  # buy-and-hold
        pnl_vals = [s.get("total_value", 0) for s in snaps]
        ranking_medians = [s.get("ranking_median", 0) for s in snaps]
        ranking_smoothed = [s.get("ranking_median_smoothed", 0) for s in snaps]
        high_pcts = [s.get("ranking_high_pct", 0) for s in snaps]
        low_pcts = [s.get("ranking_low_pct", 0) for s in snaps]
        regimes = [s.get("ranking_regime", "") for s in snaps]
        num_positions = [len(s.get("positions", [])) for s in snaps]
        pos_vals = [s.get("total_value", 0) for s in snaps]
        cash_vals = [s.get("cash", 0) for s in snaps]
        
        # Cumulative returns
        base_bh = baseline_bh[0] if baseline_bh else 1
        bh_cum = [(v - base_bh) / base_bh * 100 for v in baseline_bh]
        
        base_pnl = pnl_vals[0] if pnl_vals else 1
        pnl_cum = [(v - base_pnl) / base_pnl * 100 for v in pnl_vals]
        
        # Daily-rebalanced baseline
        dr_cum, dr_daily, close_prices_all = compute_daily_rebalanced_baseline(snaps)
        
        # Position ratio
        pos_ratios = []
        for i in range(len(dates)):
            tv = pos_vals[i]
            pos_ratios.append((tv - cash_vals[i]) / tv * 100 if tv > 0 else 0)
        
        # Derived indicators
        n = len(dates)
        
        # bl_5d: 5-day change of daily-rebalanced baseline
        dr_5d = [0.0] * n
        for i in range(5, n):
            dr_5d[i] = dr_cum[i] - dr_cum[i-5]
        
        # dr_10d
        dr_10d = [0.0] * n
        for i in range(10, n):
            dr_10d[i] = dr_cum[i] - dr_cum[i-10]
        
        # low_5d
        low_5d = [0.0] * n
        for i in range(5, n):
            low_5d[i] = low_pcts[i] - low_pcts[i-5]
        
        # Median 5d
        med_5d = [0.0] * n
        for i in range(5, n):
            med_5d[i] = ranking_medians[i] - ranking_medians[i-5]

        # =========== TABLE ===========
        w(f"\n全量数据（{n}天，每2天采样）:")
        w()
        w(f"  {'日期':<10} {'重平衡基':<8} {'持仓基':<8} {'组合':<8} {'持仓%':<7} {'low%':<6} {'dr_5d':<8} {'low_5d':<7} {'median':<8} {'regime':<14}")
        w(f"  {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*7} {'-'*6} {'-'*8} {'-'*7} {'-'*8} {'-'*14}")
        step = 2
        for i in range(0, n, step):
            w(f"  {dates[i]:<10} {dr_cum[i]:<+7.2f}% {bh_cum[i]:<+7.2f}% {pnl_cum[i]:<+7.2f}% {pos_ratios[i]:<6.1f}% {low_pcts[i]:<6.1f} {dr_5d[i]:<+7.2f}% {low_5d[i]:<+6.1f} {ranking_medians[i]:<+7.4f} {regimes[i]:<14}")
        
        w()
        
        # =========== PHASE ANALYSIS ===========
        w("-" * 100)
        w("阶段分析 — 当前策略行为 vs 理想行为")
        w("-" * 100)
        w()

        # Phase classification using daily-rebalanced baseline 5d change + low_pct
        phases = []
        phase_data = []  # (start_idx, end_idx, phase_name)
        
        i = 10  # start after we have enough data for indicators
        current_phase = "normal"
        phase_start = 10
        
        while i < n:
            d5 = dr_5d[i]
            l5 = low_5d[i]
            lp = low_pcts[i]
            dr = dr_cum[i]
            pos_ratio = pos_ratios[i]
            
            # Determine ideal action based on market state
            is_panic = d5 < -6           # 急跌：大盘5日跌超6%
            is_sharp_decline = -6 <= d5 < -3  # 加速下跌
            is_slow_decline = -3 <= d5 < 0    # 缓慢下跌/企稳
            is_rising = d5 >= 0               # 上涨
            is_low_peaked = l5 < -2 and lp > 15  # low_pct从高位回落（恐慌消退）
            is_low_rising = l5 > 2             # low_pct还在上升（恐慌扩散）
            
            if is_panic:
                phase = "急跌"
            elif is_sharp_decline:
                if is_low_peaked:
                    phase = "企稳_可建仓"
                else:
                    phase = "加速跌"
            elif is_slow_decline:
                # -3% ~ 0%, 看恐慌是否消退
                if l5 < 0:
                    phase = "企稳_可建仓"
                else:
                    phase = "横盘弱"
            elif is_rising:
                if d5 > 3 and lp < 5:
                    phase = "强势"
                elif d5 > 0:
                    phase = "弱反弹"
                else:
                    phase = "正常"
            else:
                phase = "正常"
            
            phases.append(phase)
            
            if phase != current_phase:
                phase_data.append((phase_start, i-1, current_phase))
                current_phase = phase
                phase_start = i
            i += 1
        
        phase_data.append((phase_start, n-1, current_phase))
        
        # Print phase summary with current strategy behavior
        w(f"  {'阶段':<14} {'区间':<24} {'dr_5d范围':<12} {'low%范围':<10} {'当前行为':<20} {'理想行为':<20}")
        w(f"  {'-'*14} {'-'*24} {'-'*12} {'-'*10} {'-'*20} {'-'*20}")
        
        for ps, pe, pname in phase_data:
            if pe - ps < 3:
                continue
            d5_range = f"{dr_5d[ps]:+.1f}~{dr_5d[pe]:+.1f}%"
            lp_range = f"{low_pcts[ps]:.0f}~{low_pcts[pe]:.0f}%"
            date_range = f"{dates[ps]}~{dates[pe]}"
            
            # Current behavior
            avg_pos = sum(pos_ratios[ps:pe+1]) / (pe-ps+1)
            buys_in_phase = sum(1 for t in trades 
                if t.get("action") == "buy" and t.get("status") == "filled"
                and t.get("trade_date","") >= dates[ps] and t.get("trade_date","") <= dates[pe])
            sells_in_phase = sum(1 for t in trades 
                if t.get("action") == "sell" and t.get("status") == "filled"
                and t.get("trade_date","") >= dates[ps] and t.get("trade_date","") <= dates[pe])
            
            current_behavior = f"仓{avg_pos:.0f}% 买{buys_in_phase}"
            
            # Ideal behavior
            if pname == "急跌":
                ideal = "空仓/不买入"
            elif pname == "加速跌":
                ideal = "减仓/观望"
            elif pname == "企稳_可建仓":
                ideal = "低阈值建仓"
            elif pname == "横盘弱":
                ideal = "减仓观望"
            elif pname == "弱反弹":
                ideal = "积极建仓"
            elif pname == "强势":
                ideal = "满仓持有"
            else:
                ideal = "正常交易"
            
            w(f"  {pname:<14} {date_range:<24} {d5_range:<12} {lp_range:<10} {current_behavior:<20} {ideal:<20}")
        
        w()

        # =========== STRATEGY MISMATCH ANALYSIS ===========
        w("-" * 100)
        w("当前策略的反向行为检测 — 应该在低仓位时满仓，满仓时低仓位")
        w("-" * 100)
        w()

        # Find where pos_ratio is high (>80%) during crash periods
        mismatches = []
        for i in range(10, n):
            if dr_5d[i] < -5 and pos_ratios[i] > 70:
                mismatches.append((dates[i], dr_5d[i], pos_ratios[i], "暴跌高仓位"))
            if dr_5d[i] > -3 and low_5d[i] < 0 and pos_ratios[i] < 40:
                mismatches.append((dates[i], dr_5d[i], pos_ratios[i], "企稳低仓位"))

        if mismatches:
            w(f"  {'日期':<10} {'dr_5d':<8} {'仓位':<7} {'问题':<20}")
            w(f"  {'-'*10} {'-'*8} {'-'*7} {'-'*20}")
            for md, d5, pr, problem in mismatches[:20]:
                w(f"  {md:<10} {d5:<+7.1f}% {pr:<6.1f}% {problem:<20}")
        else:
            w("  (本轮未发现明显的策略反向行为)")
        w()

    # =========== FINAL DESIGN ===========
    w("=" * 120)
    w("最终方案设计 — 新增每日重平衡基线 + 4阶段策略联动")
    w("=" * 120)
    w()

    w("""
【新基线定义】
  每日重平衡等权基线 (DailyRebalancedBaseline):
  - 每天将资金等权分配至全部活跃股票（predictions中有close价格的）
  - 每日收益率 = 全部股票当日收益率的简单平均
  - 不存在权重漂移问题，是市场平均水平的精确度量
  
  与原有基线的区别:
  - 原基线(baseline_value): 期初买入并持有，权重随股价变化漂移
  - 新基线: 每日重平衡，真实反映"每天买入平均水平股票"的收益
  - 在市场分化严重时（如2022年），两者差异可达5-10%

【四阶段策略联动】

  阶段判断依据：dr_5d（新基线5日变化）+ low_5d（低分占比变化率）
  
  ┌──────────┬───────────────────┬──────────────┬─────────────────────────┐
  │  阶段名   │    判定条件        │  仓位上限     │  买入阈值/排名条件       │
  ├──────────┼───────────────────┼──────────────┼─────────────────────────┤
  │  1. 急跌 │ dr_5d < -6%       │  0% (空仓)    │ 不买入                  │
  │          │                   │  只止不止损   │ 仅处理止损和强制卖出    │
  ├──────────┼───────────────────┼──────────────┼─────────────────────────┤
  │  2. 下跌 │ -6% <= dr_5d < 0 │  3~6只       │ threshold=0.30(正常)    │
  │          │ + low_5d > 0     │  不增仓       │ rank_up 可用            │
  │          │ (恐慌仍在扩散)    │               │ (当前逻辑变化不大)      │
  ├──────────┼───────────────────┼──────────────┼─────────────────────────┤
  │  3. 企稳 │ dr_5d < 0但>-3%  │  6只         │ threshold=0.15(降低!)   │
  │          │ + low_5d < 0     │  正常满仓     │ 排名前20%即可买入       │
  │          │ (恐慌消退)        │               │ rank_up优先(低分试仓)   │
  │          │                   │               │ 这是底部建仓的核心阶段!  │
  ├──────────┼───────────────────┼──────────────┼─────────────────────────┤
  │  4. 反弹 │ dr_5d >= 0       │  6只         │ threshold=0.30(恢复)    │
  │          │                   │  满仓         │ 排名前6正常买入         │
  │          │                   │               │ (当前逻辑)              │
  └──────────┴───────────────────┴──────────────┴─────────────────────────┘

【对2022年回测的改进效果预估】

  阶段3（企稳_可建仓）在2022年只出现了2次：
  
  第1次：4月29日~5月初  ← 全年最重要的建仓窗口
    - dr_5d从-6.6%回升到-2.7%
    - low_pct从26.8%回落到15.9%（恐慌消退）
    - 当前策略：买入评分0.18~0.22，但阈值0.30几乎不买
    - 改进后：阈值降到0.15，可以买入
    - 这次建仓能抓住5~6月的反弹行情
    
  第2次：10月12日~10月18日  ← 第二次建仓窗口
    - dr_5d从-3.2%回升到+0.3%
    - low_pct见顶回落
    - 改进后：提前2周建仓，抓住11月反弹

  → 预期将2022年收益从-4.35%提升到-2%~+5%
  
【对2025年的影响】
  
  2025年基本没有触发阶段1（急跌 dr_5d < -6%），除了4月关税冲击：
  - 4月7日 dr_5d = -11.2%，触发了阶段1
  - 按照新逻辑应该空仓避险
  - 实际上基准跌了-5.7%，策略只亏了-0.6%（选股能力生效）
  - 所以阶段1的保护在2025年影响有限，不会损害收益
  
  4月7日后：dr_5d很快回到0以上，系统正常运作不受影响
""")

    output_path = os.path.join(OUTPUT_DIR, f"{date_str}_phase_strategy.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"分析完成！输出: {output_path}")
    client.close()


if __name__ == "__main__":
    asyncio.run(analyze())
