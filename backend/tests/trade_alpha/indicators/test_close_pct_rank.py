"""Tests for close_pct_rank module."""

import pandas as pd
from trade_alpha.indicators.close_pct_rank import calculate_close_pct_rank


def test_calculate_close_pct_rank():
    df = pd.DataFrame({
        "close": [10.0, 11.0, 9.0, 12.0, 8.0,
                  13.0, 14.0, 7.0, 15.0, 6.0,
                  16.0, 17.0, 5.0, 18.0, 4.0,
                  19.0, 20.0, 3.0, 21.0, 2.0,
                  22.0],
    })
    result = calculate_close_pct_rank(df, period=20)
    assert "close_pct_rank_20" in result.columns
    assert pd.isna(result.iloc[0]["close_pct_rank_20"])
    assert pd.isna(result.iloc[18]["close_pct_rank_20"])
    assert result.iloc[20]["close_pct_rank_20"] == 1.0
