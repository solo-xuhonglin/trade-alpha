"""Tests for LSTM sequence normalizer."""

import pandas as pd
import numpy as np
from trade_alpha.models.lstm.normalizer import create_sequences


def test_create_sequences_basic():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ"] * 60,
        "trade_date": [f"2024-01-{i+1:02d}" for i in range(60)],
        "close": list(range(10, 70)),
        "label_3d": [1] * 60,
    })
    X, y = create_sequences(df, ["close"], ["label_3d"], sequence_length=3)
    assert X.shape[0] > 0
    assert X.shape[1] == 3
    assert X.shape[2] == 1
    assert len(y) == X.shape[0]


def test_create_sequences_insufficient_data():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ"] * 2,
        "trade_date": ["2024-01-01", "2024-01-02"],
        "close": [10.0, 12.0],
        "label_3d": [1, 1],
    })
    X, y = create_sequences(df, ["close"], ["label_3d"], sequence_length=5)
    assert len(X) == 0


def test_create_sequences_empty():
    df = pd.DataFrame(columns=["ts_code", "trade_date", "close"])
    X, y = create_sequences(df, ["close"], ["label_3d"], sequence_length=3)
    assert len(X) == 0


def test_create_sequences_multiple_stocks():
    df = pd.DataFrame({
        "ts_code": ["A"] * 60 + ["B"] * 60,
        "trade_date": [f"2024-01-{i+1:02d}" for i in range(60)] * 2,
        "close": list(range(10, 70)) + list(range(20, 80)),
        "label_3d": [1] * 120,
    })
    X, y = create_sequences(df, ["close"], ["label_3d"], sequence_length=3)
    assert X.shape[0] == 2


def test_create_sequences_normalization():
    """Verify each sequence is Z-score normalized using normalization_window."""
    df = pd.DataFrame({
        "ts_code": ["A"] * 60,
        "trade_date": [f"2024-01-{i+1:02d}" for i in range(60)],
        "close": list(range(10, 70)),
        "label_3d": [1] * 60,
    })
    X, y = create_sequences(df, ["close"], ["label_3d"], sequence_length=3)
    # Only one sequence produced (at i=59)
    assert X.shape[0] == 1
    # Full window is values[0:60] = [10..69], mean=39.5, std=sqrt(42000/60)=sqrt(700)≈26.46
    # Last 3 values [67,68,69] normalized: (67-39.5)/std, (68-39.5)/std, (69-39.5)/std
    expected_mean = 39.5
    expected_std = np.std(np.arange(10, 70), ddof=0)
    expected_seq = (np.array([67, 68, 69], dtype=np.float64) - expected_mean) / expected_std
    np.testing.assert_array_almost_equal(X[0, :, 0], expected_seq)


def test_create_sequences_with_normalization_window():
    """Verify normalization_window > sequence_length works."""
    n_stocks = 3
    n_dates = 50
    n_features = 3
    rows = []
    for stock_idx in range(n_stocks):
        ts_code = f"{stock_idx:06d}.SZ"
        for date_idx in range(n_dates):
            rows.append({
                "ts_code": ts_code,
                "trade_date": f"2024{(date_idx+1):03d}",
                "f1": np.random.randn(),
                "f2": np.random.randn(),
                "f3": np.random.randn(),
                "label_3d": np.random.choice([-1, 0, 1]),
                "label_5d": np.random.choice([-1, 0, 1]),
            })
    df = pd.DataFrame(rows)
    X, y = create_sequences(
        df, ["f1", "f2", "f3"], ["label_3d", "label_5d"],
        sequence_length=10, normalization_window=30,
    )
    assert X.shape[0] > 0
    assert X.shape[1] == 10
    assert X.shape[2] == 3
    assert y.shape[0] == X.shape[0]
    assert y.shape[1] == 2
    assert not np.isnan(X).any()
    assert not np.isnan(y).any()
