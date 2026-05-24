"""Tests for LSTM sequence normalizer."""

import pandas as pd
import numpy as np
from trade_alpha.models.lstm.normalizer import create_sequences


def test_create_sequences_basic():
    df = pd.DataFrame({
        "ts_code": ["000001.SZ"] * 10,
        "trade_date": [f"2024-01-{i+1:02d}" for i in range(10)],
        "close": list(range(10, 20)),
        "label_3d": [1] * 10,
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
        "ts_code": ["A"] * 10 + ["B"] * 10,
        "trade_date": [f"2024-01-{i+1:02d}" for i in range(10)] * 2,
        "close": list(range(10, 20)) + list(range(20, 30)),
        "label_3d": [1] * 20,
    })
    X, y = create_sequences(df, ["close"], ["label_3d"], sequence_length=3)
    assert X.shape[0] == 14


def test_create_sequences_normalization():
    """Verify each sequence is Z-score normalized internally."""
    df = pd.DataFrame({
        "ts_code": ["A"] * 10,
        "trade_date": [f"2024-01-{i+1:02d}" for i in range(10)],
        "close": list(range(10, 20)),
        "label_3d": [1] * 10,
    })
    X, y = create_sequences(df, ["close"], ["label_3d"], sequence_length=3)
    for seq in X:
        assert abs(seq[:, 0].mean()) < 1e-6
        assert abs(seq[:, 0].std() - 1.0) < 1e-6
