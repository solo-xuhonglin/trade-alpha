"""Tests for trend indicators."""
import pandas as pd
import numpy as np
import pytest
from trade_alpha.indicators.custom.trend import calculate_trend


def create_test_df():
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(100) * 2)
    vol = np.random.randint(1000000, 5000000, 100)
    pct_chg = pd.Series(close).pct_change() * 100
    
    df = pd.DataFrame({
        'trade_date': [d.strftime('%Y%m%d') for d in dates],
        'open': close * 0.99,
        'high': close * 1.02,
        'low': close * 0.98,
        'close': close,
        'vol': vol,
        'pct_chg': pct_chg,
    })
    
    for period in [5, 10, 20, 60]:
        df[f'ma_{period}'] = df['close'].rolling(period).mean()
    for period in [5, 10, 20, 60]:
        vol_ma = df['vol'].rolling(period).mean()
        df[f'vol_ratio_{period}'] = df['vol'] / vol_ma
    
    return df


def test_trend_arrangement():
    df = create_test_df()
    result = calculate_trend(df)
    
    assert 'trend_arrangement_5' in result.columns
    assert 'trend_arrangement_10' in result.columns
    assert 'trend_arrangement_20' in result.columns
    assert len(result) == len(df)


def test_trend_slope():
    df = create_test_df()
    result = calculate_trend(df)
    
    assert 'trend_slope_5' in result.columns
    assert 'trend_slope_10' in result.columns
    assert 'trend_slope_20' in result.columns


def test_trend_volume():
    df = create_test_df()
    result = calculate_trend(df)
    
    assert 'trend_volume_5' in result.columns
    assert 'trend_volume_10' in result.columns
    assert 'trend_volume_20' in result.columns


def test_trend_stability():
    df = create_test_df()
    result = calculate_trend(df)
    
    assert 'trend_stability_5' in result.columns
    assert 'trend_stability_10' in result.columns
    assert 'trend_stability_20' in result.columns
    assert result['trend_stability_5'].min() >= 0
    assert result['trend_stability_5'].max() <= 100
