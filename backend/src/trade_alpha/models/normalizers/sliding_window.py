"""Sliding window normalizer for time-series data."""

import pandas as pd
import numpy as np
from typing import List, Optional

from .base import BaseNormalizer


class SlidingWindowNormalizer(BaseNormalizer):
    """Sliding window normalizer for time-series data.

    Normalizes features using rolling window statistics per stock:
    1. Optional winsorization at configurable percentiles
    2. Rolling Z-Score standardization using window_size

    Input must contain 'ts_code' column for grouping by stock.
    Output is controlled by output_fields parameter.
    """

    def __init__(
        self,
        window_size: int = 60,
        standardize_fields: List[str] = None,
        winsorize_fields: Optional[List[str]] = None,
        winsorize_lower: float = 0.05,
        winsorize_upper: float = 0.95,
        output_fields: Optional[List[str]] = None,
    ):
        self.window_size = window_size
        self.standardize_fields = standardize_fields or []
        self.winsorize_fields = winsorize_fields or []
        self.winsorize_lower = winsorize_lower
        self.winsorize_upper = winsorize_upper
        self.output_fields = output_fields

    @property
    def name(self) -> str:
        return "sliding_window"

    def _winsorize_series(self, series: pd.Series) -> pd.Series:
        """Winsorize a single series."""
        lower = series.quantile(self.winsorize_lower)
        upper = series.quantile(self.winsorize_upper)
        return series.clip(lower=lower, upper=upper)

    def _normalize_group(self, group: pd.DataFrame) -> pd.DataFrame:
        """Normalize a single stock group."""
        group = group.sort_values("trade_date").copy()

        for field in self.winsorize_fields:
            if field in group.columns:
                group[field] = self._winsorize_series(group[field])

        for field in self.standardize_fields:
            if field not in group.columns:
                continue
            vals = group[field]
            rolling_mean = vals.rolling(window=self.window_size, min_periods=1).mean()
            rolling_std = vals.rolling(window=self.window_size, min_periods=1).std()
            rolling_std = rolling_std.replace(0, np.nan)
            group[field] = (vals - rolling_mean) / rolling_std

        return group

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize data using sliding window approach per stock."""
        if df.empty:
            if self.output_fields:
                return pd.DataFrame(columns=self.output_fields)
            return pd.DataFrame(columns=self.standardize_fields)

        result_parts = []
        for ts_code, group in df.groupby("ts_code"):
            group_norm = self._normalize_group(group)
            result_parts.append(group_norm)

        result_df = pd.concat(result_parts, ignore_index=True)

        output_fields = self.output_fields if self.output_fields else self.standardize_fields

        available_fields = result_df.columns.tolist()
        output_fields = [f for f in output_fields if f in available_fields]

        return result_df[output_fields]
