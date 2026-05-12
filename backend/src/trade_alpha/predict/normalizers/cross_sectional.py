"""Cross-sectional normalizer for cross-stock comparison."""

import pandas as pd
import numpy as np
from typing import List, Optional

from trade_alpha.predict.normalizers.base import BaseNormalizer


class CrossSectionalNormalizer(BaseNormalizer):
    """Cross-sectional normalizer for cross-stock comparison.

    Normalizes features per time cross-section (grouped by trade_date):
    1. Optional winsorization at configurable percentiles
    2. Z-Score standardization

    NaN values are preserved and excluded from statistics computation.
    Input must contain 'trade_date' column for grouping.
    Output is a pure feature DataFrame without ts_code or trade_date columns.

    Note: XGBoost can handle NaN values natively, no imputation needed.
    """

    def __init__(
        self,
        standardize_fields: List[str],
        winsorize_fields: Optional[List[str]] = None,
        winsorize_lower: float = 0.01,
        winsorize_upper: float = 0.95,
    ):
        self.standardize_fields = standardize_fields
        self.winsorize_fields = winsorize_fields or []
        self.winsorize_lower = winsorize_lower
        self.winsorize_upper = winsorize_upper

    @property
    def name(self) -> str:
        return "cross_sectional"

    def _winsorize_group(self, group: pd.DataFrame) -> pd.DataFrame:
        for field in self.winsorize_fields:
            if field not in group.columns:
                continue
            vals = group[field]
            lower = vals.quantile(self.winsorize_lower)
            upper = vals.quantile(self.winsorize_upper)
            group[field] = vals.clip(lower=lower, upper=upper)
        return group

    def _standardize_group(self, group: pd.DataFrame) -> pd.DataFrame:
        for field in self.standardize_fields:
            if field not in group.columns:
                continue
            vals = group[field]
            mean = vals.mean()
            std = vals.std()
            if std > 0:
                group[field] = (vals - mean) / std
            else:
                group[field] = vals - mean
        return group

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=self.standardize_fields)

        grouped = df.groupby("trade_date")
        result_parts = []
        for _, group in grouped:
            group = self._winsorize_group(group.copy())
            group = self._standardize_group(group)
            result_parts.append(group[self.standardize_fields])

        return pd.concat(result_parts, ignore_index=True)
