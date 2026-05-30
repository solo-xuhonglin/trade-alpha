"""Indicators service module."""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from trade_alpha.dao import StockDaily
from trade_alpha.indicators.ma import calculate_ma
from trade_alpha.indicators.macd import calculate_macd
from trade_alpha.indicators.custom import (
    calculate_pct_chg,
    calculate_bias,
    calculate_close_position,
    calculate_vol_ratio,
    calculate_kdj,
    calculate_boll,
    calculate_rsi,
    calculate_atr,
    calculate_obv,
    calculate_candle_features,
    calculate_trend,
    calculate_weekly_basic_features,
)
from trade_alpha.logging import get_logger

logger = get_logger("indicators_service")

MAX_LOOKBACK = 90


async def _load_and_sort_records(
    ts_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """Load stock daily records with expanded date range for rolling calculations.

    When start_date is provided, the query start is pushed back by MAX_LOOKBACK
    calendar days to ensure enough history for rolling indicators (MA-60, etc.).
    """
    if start_date:
        dt = datetime.strptime(start_date, "%Y%m%d") - timedelta(days=MAX_LOOKBACK)
        expanded_start = dt.strftime("%Y%m%d")
    else:
        expanded_start = None

    if expanded_start and end_date:
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= expanded_start,
            StockDaily.trade_date <= end_date,
        ).sort(StockDaily.trade_date).to_list()
    elif expanded_start:
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= expanded_start,
        ).sort(StockDaily.trade_date).to_list()
    elif end_date:
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date <= end_date,
        ).sort(StockDaily.trade_date).to_list()
    else:
        records = await StockDaily.find(StockDaily.ts_code == ts_code).sort(StockDaily.trade_date).to_list()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([r.model_dump() for r in records])
    return df


def _in_target_range(trade_date: str, start_date: Optional[str], end_date: Optional[str]) -> bool:
    """Check if a trade_date falls within the target update range."""
    if start_date and trade_date < start_date:
        return False
    if end_date and trade_date > end_date:
        return False
    return True


async def calculate_and_store_ma(
    ts_code: str,
    periods: list[int] | None = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """Calculate MA for a stock and store to database.

    Args:
        ts_code: Stock code
        periods: List of MA periods (default [5, 10, 20, 40, 60])
        start_date: Only update records on or after this date (YYYYMMDD)
        end_date: Only update records on or before this date (YYYYMMDD)

    Returns:
        Number of records updated
    """
    logger.info(f"Calculating MA for {ts_code} with periods {periods}")
    if periods is None:
        periods = [5, 10, 20, 40, 60]

    df = await _load_and_sort_records(ts_code, start_date, end_date)
    if df.empty:
        logger.warning(f"No data found for {ts_code}")
        return 0

    df = calculate_ma(df, periods)

    updated_count = 0
    for _, row in df.iterrows():
        if not _in_target_range(row["trade_date"], start_date, end_date):
            continue
        update_data = {f"ma_{p}": row[f"ma_{p}"] for p in periods if f"ma_{p}" in row}
        if update_data:
            await StockDaily.find_one(
                StockDaily.ts_code == ts_code,
                StockDaily.trade_date == row["trade_date"]
            ).update({"$set": update_data})
            updated_count += 1

    logger.info(f"Successfully calculated and stored MA for {ts_code}: {updated_count} records updated")
    return updated_count


async def calculate_and_store_macd(
    ts_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """Calculate MACD for a stock and store to database.

    Args:
        ts_code: Stock code
        start_date: Only update records on or after this date (YYYYMMDD)
        end_date: Only update records on or before this date (YYYYMMDD)

    Returns:
        Number of records updated
    """
    logger.info(f"Calculating MACD for {ts_code}")

    df = await _load_and_sort_records(ts_code, start_date, end_date)
    if df.empty:
        logger.warning(f"No data found for {ts_code}")
        return 0

    df = calculate_macd(df)

    updated_count = 0
    for _, row in df.iterrows():
        if not _in_target_range(row["trade_date"], start_date, end_date):
            continue
        update_data = {
            "macd": row.get("macd"),
            "macd_signal": row.get("macd_signal"),
            "macd_hist": row.get("macd_hist"),
        }
        await StockDaily.find_one(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date == row["trade_date"]
        ).update({"$set": update_data})
        updated_count += 1

    logger.info(f"Successfully calculated and stored MACD for {ts_code}: {updated_count} records updated")
    return updated_count


async def calculate_all_indicators(
    ts_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, int]:
    """Calculate all indicators for a stock and store to database.

    This is the unified interface for calculating all indicators (MA, MACD, and custom indicators).

    Args:
        ts_code: Stock code
        start_date: Only update records on or after this date (YYYYMMDD)
        end_date: Only update records on or before this date (YYYYMMDD)

    Returns:
        Dictionary with counts of updated records for each indicator type
    """
    ma_count = await calculate_and_store_ma(ts_code, start_date=start_date, end_date=end_date)
    macd_count = await calculate_and_store_macd(ts_code, start_date=start_date, end_date=end_date)
    custom_count = await calculate_and_store_custom_indicators(ts_code, start_date=start_date, end_date=end_date)
    return {
        "ma": ma_count,
        "macd": macd_count,
        "custom": custom_count,
    }


async def calculate_and_store_custom_indicators(
    ts_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """Calculate additional indicators (pct_chg, bias, pct_rank, vol_ratio, kdj, boll, rsi, atr, obv).

    Args:
        ts_code: Stock code
        start_date: Only update records on or after this date (YYYYMMDD)
        end_date: Only update records on or before this date (YYYYMMDD)

    Returns:
        Number of records updated
    """
    logger.info(f"Calculating additional indicators for {ts_code}")

    df = await _load_and_sort_records(ts_code, start_date, end_date)
    if df.empty:
        logger.warning(f"No data found for {ts_code}")
        return 0

    df = calculate_pct_chg(df)
    df = calculate_bias(df, periods=[5, 10, 20, 60])
    df = calculate_close_position(df)
    df = calculate_vol_ratio(df)
    df = calculate_kdj(df)
    df = calculate_boll(df)
    df = calculate_rsi(df)
    df = calculate_atr(df)
    df = calculate_obv(df)
    
    prev_close_series = df["close"].shift(1)
    df = calculate_candle_features(df, prev_close_series)
    df = calculate_trend(df)
    df = calculate_weekly_basic_features(df)

    updated_count = 0
    for _, row in df.iterrows():
        if not _in_target_range(row["trade_date"], start_date, end_date):
            continue
        update_data = {
            "pct_chg": row.get("pct_chg"),
            "bias_5": row.get("bias_5"),
            "bias_10": row.get("bias_10"),
            "bias_20": row.get("bias_20"),
            "bias_60": row.get("bias_60"),
            "close_position_5": row.get("close_position_5"),
            "close_position_10": row.get("close_position_10"),
            "close_position_20": row.get("close_position_20"),
            "close_position_60": row.get("close_position_60"),
            "vol_ratio_5": row.get("vol_ratio_5"),
            "vol_ratio_10": row.get("vol_ratio_10"),
            "vol_ratio_20": row.get("vol_ratio_20"),
            "vol_ratio_60": row.get("vol_ratio_60"),
            "kdj_k": row.get("kdj_k"),
            "kdj_d": row.get("kdj_d"),
            "kdj_j": row.get("kdj_j"),
            "boll_upper": row.get("boll_upper"),
            "boll_middle": row.get("boll_middle"),
            "boll_lower": row.get("boll_lower"),
            "boll_position": row.get("boll_position"),
            "rsi_6": row.get("rsi_6"),
            "rsi_12": row.get("rsi_12"),
            "trend_arrangement_5": row.get("trend_arrangement_5"),
            "trend_arrangement_10": row.get("trend_arrangement_10"),
            "trend_arrangement_20": row.get("trend_arrangement_20"),
            "trend_slope_5": row.get("trend_slope_5"),
            "trend_slope_10": row.get("trend_slope_10"),
            "trend_slope_20": row.get("trend_slope_20"),
            "trend_volume_5": row.get("trend_volume_5"),
            "trend_volume_10": row.get("trend_volume_10"),
            "trend_volume_20": row.get("trend_volume_20"),
            "trend_stability_5": row.get("trend_stability_5"),
            "trend_stability_10": row.get("trend_stability_10"),
            "trend_stability_20": row.get("trend_stability_20"),
            "obv": row.get("obv"),
            "obv_chg_5": row.get("obv_chg_5"),
            "obv_chg_10": row.get("obv_chg_10"),
            "obv_chg_20": row.get("obv_chg_20"),
            "candle_body_pct": row.get("candle_body_pct"),
            "candle_upper_pct": row.get("candle_upper_pct"),
            "candle_lower_pct": row.get("candle_lower_pct"),
            "close_location_pct": row.get("close_location_pct"),
            "gap_pct": row.get("gap_pct"),
            "gap_fill_pct": row.get("gap_fill_pct"),
            "week_open": row.get("week_open"),
            "week_high": row.get("week_high"),
            "week_low": row.get("week_low"),
            "week_close": row.get("week_close"),
            "week_vol_avg": row.get("week_vol_avg"),
            "week_amount_avg": row.get("week_amount_avg"),
        }
        await StockDaily.find_one(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date == row["trade_date"]
        ).update({"$set": update_data})
        updated_count += 1

    logger.info(f"Successfully stored additional indicators for {ts_code}: {updated_count} records")
    return updated_count


ALL_INDICATOR_FIELDS = [
    "ma_5", "ma_10", "ma_20", "ma_40", "ma_60",
    "macd", "macd_signal", "macd_hist",
    "pct_chg",
    "bias_5", "bias_10", "bias_20", "bias_60",
    "close_position_5", "close_position_10", "close_position_20", "close_position_60",
    "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60",
    "kdj_k", "kdj_d", "kdj_j",
    "boll_upper", "boll_middle", "boll_lower", "boll_position",
    "rsi_6", "rsi_12",
    "trend_arrangement_5", "trend_arrangement_10", "trend_arrangement_20",
    "trend_slope_5", "trend_slope_10", "trend_slope_20",
    "trend_volume_5", "trend_volume_10", "trend_volume_20",
    "trend_stability_5", "trend_stability_10", "trend_stability_20",
    "obv", "obv_chg_5", "obv_chg_10", "obv_chg_20",
    "candle_body_pct", "candle_upper_pct", "candle_lower_pct",
    "close_location_pct", "gap_pct", "gap_fill_pct",
]