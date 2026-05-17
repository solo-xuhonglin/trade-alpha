"""分析当前已实现的指标和潜在可新增的指标"""

import sys
import os


def describe_indicator(name, category, description, formula, file_path):
    """描述指标"""
    return {
        "名称": name,
        "类别": category,
        "描述": description,
        "公式": formula,
        "文件": file_path
    }


def get_existing_indicators():
    """获取当前已实现的指标列表"""
    indicators = []
    
    # 均线类
    indicators.append(describe_indicator(
        "MA（移动平均线）",
        "趋势类",
        "反映股价在一段时间内的平均成本，用于判断趋势方向",
        "MA_N = (close_1 + close_2 + ... + close_N) / N",
        "indicators/ma.py"
    ))
    
    # MACD类
    indicators.append(describe_indicator(
        "MACD（指数平滑异同移动平均线）",
        "趋势类",
        "通过短期EMA与长期EMA的差值，判断趋势强度和转折点",
        "DIF = EMA(close, 12) - EMA(close, 26)\nDEA = EMA(DIF, 9)\nMACD = DIF - DEA",
        "indicators/macd.py"
    ))
    
    # KDJ类
    indicators.append(describe_indicator(
        "KDJ（随机指标）",
        "震荡类",
        "衡量股价在一段时间内的相对位置，用于判断超买超卖",
        "RSV = (close - LLV(low, 9)) / (HHV(high, 9) - LLV(low, 9)) × 100\nK = SMA(RSV, 3)\nD = SMA(K, 3)\nJ = 3K - 2D",
        "indicators/custom/kdj.py"
    ))
    
    # BOLL类
    indicators.append(describe_indicator(
        "BOLL（布林带）",
        "趋势类",
        "通过标准差构建价格通道，判断股价波动范围和突破",
        "MID = MA(close, 20)\nUPPER = MID + 2×STD(close, 20)\nLOWER = MID - 2×STD(close, 20)",
        "indicators/custom/boll.py"
    ))
    
    # 涨跌幅
    indicators.append(describe_indicator(
        "pct_chg（日涨跌幅）",
        "基础类",
        "当日收盘价相对前一日收盘价的涨跌幅",
        "pct_chg = (close_t - close_{t-1}) / close_{t-1} × 100",
        "indicators/custom/pct_chg.py"
    ))
    
    # BIAS类
    indicators.append(describe_indicator(
        "BIAS（乖离率）",
        "震荡类",
        "衡量股价偏离均线的程度，判断超买超卖",
        "BIAS_N = (close - MA_N) / MA_N × 100",
        "indicators/custom/bias.py"
    ))
    
    # Close Pct Rank
    indicators.append(describe_indicator(
        "close_pct_rank（收盘价百分位）",
        "统计类",
        "当前收盘价在过去N天中的百分位排名",
        "pct_rank = rank(close, N) / N",
        "indicators/custom/close_pct_rank.py"
    ))
    
    # Vol Ratio
    indicators.append(describe_indicator(
        "vol_ratio（量比）",
        "量能类",
        "当前成交量与过去N日均量的比值，反映量能变化",
        "vol_ratio_N = vol / MA(vol, N)",
        "indicators/custom/vol_ratio.py"
    ))
    
    return indicators


def get_potential_indicators():
    """获取基于现有日线数据可新增的指标"""
    potential = []
    
    # 动量指标
    potential.append(describe_indicator(
        "RSI（相对强弱指数）",
        "震荡类",
        "衡量股价上涨和下跌的相对强度，判断超买超卖",
        "RS = average_gain / average_loss\nRSI = 100 - (100 / (1 + RS))",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "CCI（顺势指标）",
        "震荡类",
        "衡量股价偏离其平均价格的程度",
        "CCI = (TP - MA(TP, 20)) / (0.015 × MD)\nTP = (high + low + close) / 3",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "ATR（平均真实波动）",
        "波动率类",
        "衡量股价的波动性",
        "TR = max(high-low, |high-close_prev|, |low-close_prev|)\nATR = MA(TR, 14)",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "ROC（变动率指标）",
        "动量类",
        "衡量股价变化的速率",
        "ROC_N = (close_t / close_{t-N} - 1) × 100",
        "可新增"
    ))
    
    # 量能指标
    potential.append(describe_indicator(
        "OBV（能量潮）",
        "量能类",
        "通过成交量判断资金流向",
        "OBV_t = OBV_{t-1} + vol_t (if close_t > close_{t-1})\nOBV_t = OBV_{t-1} - vol_t (if close_t < close_{t-1})",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "VWAP（成交量加权平均价）",
        "量能类",
        "反映当日平均成交成本",
        "VWAP = Σ(price × volume) / Σvolume",
        "可新增（需要日内数据，日线可用简单近似）"
    ))
    
    # 趋势指标
    potential.append(describe_indicator(
        "SAR（停损转向指标）",
        "趋势类",
        "判断趋势反转点",
        "SAR = SAR_prev + AF × (EP - SAR_prev)",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "DMI（动向指标）",
        "趋势类",
        "衡量趋势强度和方向",
        "+DM = high_t - high_{t-1}\n-DM = low_{t-1} - low_t\nADX = MA(DI+, DI-, 14)",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "EMA（指数移动平均）",
        "趋势类",
        "对近期数据赋予更高权重",
        "EMA_N = α×close_t + (1-α)×EMA_{t-1}, α=2/(N+1)",
        "可新增"
    ))
    
    # 统计指标
    potential.append(describe_indicator(
        "STD（标准差）",
        "统计类",
        "衡量股价波动程度",
        "STD_N = sqrt(Σ(close - μ)² / N)",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "Skewness（偏度）",
        "统计类",
        "衡量收益率分布的不对称性",
        "skew = E[(x - μ)³] / σ³",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "Kurtosis（峰度）",
        "统计类",
        "衡量收益率分布的尖峰程度",
        "kurt = E[(x - μ)⁴] / σ⁴ - 3",
        "可新增"
    ))
    
    # 波动性指标
    potential.append(describe_indicator(
        "Historical Volatility（历史波动率）",
        "波动率类",
        "衡量股价的历史波动水平",
        "HV = std(daily_returns) × sqrt(252)",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "ATR Ratio（ATR比率）",
        "波动率类",
        "当前ATR与历史ATR的比值",
        "ATR_ratio = ATR_t / MA(ATR, N)",
        "可新增"
    ))
    
    # 价格模式
    potential.append(describe_indicator(
        "High/Low Range（高低区间）",
        "价格模式",
        "当日波动范围",
        "range = high - low",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "Close Position（收盘位置）",
        "价格模式",
        "收盘价在当日波动区间中的位置",
        "position = (close - low) / (high - low)",
        "可新增"
    ))
    
    potential.append(describe_indicator(
        "Gap（跳空缺口）",
        "价格模式",
        "当日开盘价与前一日收盘价的差距",
        "gap_up = open_t - close_{t-1}\ngap_down = close_{t-1} - open_t",
        "可新增"
    ))
    
    return potential


def main():
    print("=" * 80)
    print("TRADE-ALPHA 指标分析报告")
    print("=" * 80)
    print()
    
    # 已实现指标
    print("一、当前已实现的指标")
    print("-" * 80)
    
    existing = get_existing_indicators()
    for i, ind in enumerate(existing, 1):
        print(f"\n{i}. {ind['名称']}")
        print(f"   类别: {ind['类别']}")
        print(f"   描述: {ind['描述']}")
        print(f"   公式:")
        for line in ind['公式'].split('\n'):
            print(f"         {line}")
        print(f"   文件: {ind['文件']}")
    
    # 可新增指标
    print("\n" + "=" * 80)
    print("二、基于日线数据可新增的指标")
    print("-" * 80)
    
    potential = get_potential_indicators()
    
    # 按类别分组
    categories = {}
    for ind in potential:
        cat = ind['类别']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(ind)
    
    for cat, inds in categories.items():
        print(f"\n【{cat}】")
        for ind in inds:
            print(f"  - {ind['名称']}: {ind['描述']}")
    
    # 统计
    print("\n" + "=" * 80)
    print("三、指标统计")
    print("-" * 80)
    print(f"当前已实现指标数量: {len(existing)}")
    print(f"可新增指标数量: {len(potential)}")
    print(f"现有指标类别分布:")
    
    cat_counts = {}
    for ind in existing:
        cat = ind['类别']
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    
    for cat, cnt in cat_counts.items():
        print(f"  - {cat}: {cnt} 个")
    
    print("\n建议优先新增的指标（按优先级）:")
    print("  1. RSI（相对强弱指数）- 最常用的震荡指标")
    print("  2. ATR（平均真实波动）- 衡量波动性")
    print("  3. OBV（能量潮）- 量价关系")
    print("  4. EMA（指数移动平均）- 对近期数据更敏感")
    print("  5. ROC（变动率指标）- 动量判断")


if __name__ == "__main__":
    main()
