"""KDJ indicator calculation module.

KDJ formulas:
  RSV(N) = (close - low_N) / (high_N - low_N) * 100
  K = SMA(RSV, M1)  —  K[t] = (RSV[t] + (M1-1) * K[t-1]) / M1
  D = SMA(K, M2)    —  D[t] = (K[t] + (M2-1) * D[t-1]) / M2
  J = 3 * K - 2 * D
"""

import pandas as pd
import numpy as np


def calculate_kdj(
    df: pd.DataFrame,
    n: int = 9,
    m1: int = 3,
    m2: int = 3,
) -> pd.DataFrame:
    result = df.copy()
    low_n = result["low"].rolling(window=n).min()
    high_n = result["high"].rolling(window=n).max()
    rsv = (result["close"] - low_n) / (high_n - low_n) * 100

    k_vals: list[float] = []
    d_vals: list[float] = []
    prev_k, prev_d = 50.0, 50.0

    for i in range(len(result)):
        if np.isnan(rsv.iloc[i]):
            k_vals.append(np.nan)
            d_vals.append(np.nan)
        else:
            k = (rsv.iloc[i] + (m1 - 1) * prev_k) / m1
            d = (k + (m2 - 1) * prev_d) / m2
            k_vals.append(k)
            d_vals.append(d)
            prev_k, prev_d = k, d

    result["kdj_k"] = k_vals
    result["kdj_d"] = d_vals
    result["kdj_j"] = 3 * result["kdj_k"] - 2 * result["kdj_d"]
    return result
