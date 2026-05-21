"""K线形态指标计算模块."""

import pandas as pd
from typing import Optional


def calculate_candle_features(
    df: pd.DataFrame,
    prev_close_series: Optional[pd.Series] = None
) -> pd.DataFrame:
    """计算K线形态特征.
    
    - candle_body_pct: 实体长度占振幅百分比
    - candle_upper_pct: 上影线长度占振幅百分比
    - candle_lower_pct: 下影线长度占振幅百分比
    - close_location_pct: 收盘价在当日区间的位置
    - gap_pct: 跳空幅度（正为向上，负为向下）
    - gap_fill_pct: 跳空回补程度
    
    Args:
        df: 包含 open, high, low, close 的DataFrame
        prev_close_series: 前一日收盘价序列（用于计算跳空）
    
    Returns:
        包含K线形态特征的DataFrame
    """
    result = df.copy()
    
    open_ = df["open"]
    high = df["high"]
    low = df["low"]
    close = df["close"]
    
    range_ = high - low
    range_mask = range_ > 0
    
    result["candle_body_pct"] = 0.0
    result["candle_upper_pct"] = 0.0
    result["candle_lower_pct"] = 0.0
    result["close_location_pct"] = 0.0
    
    body = abs(close - open_)
    upper_shadow = high - close.where(close > open_, open_)
    lower_shadow = open_.where(close > open_, close) - low
    
    result.loc[range_mask, "candle_body_pct"] = body / range_ * 100
    result.loc[range_mask, "candle_upper_pct"] = upper_shadow / range_ * 100
    result.loc[range_mask, "candle_lower_pct"] = lower_shadow / range_ * 100
    result.loc[range_mask, "close_location_pct"] = (close - low) / range_ * 100
    
    result["gap_pct"] = 0.0
    result["gap_fill_pct"] = 0.0
    
    if prev_close_series is not None:
        gap = open_ - prev_close_series
        
        result["gap_pct"] = gap / prev_close_series * 100
        
        gap_up_mask = gap > 0.001
        gap_down_mask = gap < -0.001
        
        gap_up_filled_mask = gap_up_mask & (low <= prev_close_series)
        gap_down_filled_mask = gap_down_mask & (high >= prev_close_series)
        result.loc[gap_up_filled_mask | gap_down_filled_mask, "gap_fill_pct"] = 100.0
        
        partial_fill_up = gap_up_mask & ~gap_up_filled_mask & (close < prev_close_series)
        partial_fill_down = gap_down_mask & ~gap_down_filled_mask & (close > prev_close_series)
        result.loc[partial_fill_up, "gap_fill_pct"] = gap / (open_ - prev_close_series) * 100
        result.loc[partial_fill_down, "gap_fill_pct"] = -gap / (prev_close_series - open_) * 100
    
    return result