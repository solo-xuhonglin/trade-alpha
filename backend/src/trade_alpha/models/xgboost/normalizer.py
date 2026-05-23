"""Cross-sectional normalizer for XGBoost."""

import pandas as pd
import numpy as np
from typing import List, Optional


def normalize(
    df: pd.DataFrame,
    feature_fields: List[str],
    standardize_fields: List[str],
    winsorize_fields: Optional[List[str]] = None,
    winsorize_lower: float = 0.05,
    winsorize_upper: float = 0.95,
) -> pd.DataFrame:
    """Z-score normalize by trade_date group (cross-sectional)."""
    if df.empty:
        return pd.DataFrame(columns=feature_fields)

    winsorize_fields = winsorize_fields or []
    result_parts = []

    for _, group in df.groupby("trade_date"):
        group = group.copy()
        for field in winsorize_fields:
            if field not in group.columns:
                continue
            lower = group[field].quantile(winsorize_lower)
            upper = group[field].quantile(winsorize_upper)
            group[field] = group[field].clip(lower=lower, upper=upper)
        for field in standardize_fields:
            if field not in group.columns:
                continue
            vals = group[field]
            mean, std = vals.mean(), vals.std()
            group[field] = (vals - mean) / std if std > 0 else vals - mean
        result_parts.append(group)

    result_df = pd.concat(result_parts, ignore_index=True)
    available = [f for f in feature_fields if f in result_df.columns]
    return result_df[available]
