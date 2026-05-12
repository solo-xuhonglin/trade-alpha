from abc import ABC, abstractmethod
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, List


class BaseNormalizer(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def normalize(self, df: pd.DataFrame, feature_cols: List[str], 
                 training_stats: dict = None) -> Tuple[np.ndarray, dict]:
        pass

    @abstractmethod
    def inverse_transform(self, data: np.ndarray, feature_cols: List[str], 
                         stats: dict) -> np.ndarray:
        pass


class SlidingWindowNormalizer(BaseNormalizer):
    def __init__(self, window_size: int = 60):
        self._window_size = window_size

    @property
    def name(self) -> str:
        return "sliding_window"

    def normalize(self, df: pd.DataFrame, feature_cols: List[str], 
                 training_stats: dict = None) -> Tuple[np.ndarray, dict]:
        if training_stats is None:
            training_stats = {}
            
        for col in feature_cols:
            means = []
            stds = []
            for i in range(len(df)):
                start = max(0, i - self._window_size + 1)
                window = df[col].iloc[start:i+1]
                mean = float(window.mean())
                std = float(window.std())
                if np.isnan(std) or std < 1e-8:
                    std = 1e-8
                means.append(mean)
                stds.append(std)
            training_stats[col] = {"mean": means, "std": stds}
        
        normalized = df[feature_cols].values.astype(np.float64)
        for i, col in enumerate(feature_cols):
            means = training_stats[col]["mean"]
            stds = training_stats[col]["std"]
            for j in range(len(df)):
                normalized[j, i] = (normalized[j, i] - means[j]) / stds[j]
        
        return normalized, training_stats

    def inverse_transform(self, data: np.ndarray, feature_cols: List[str], 
                         stats: dict) -> np.ndarray:
        original = data.copy().astype(np.float64)
        for i, col in enumerate(feature_cols):
            means = stats[col]["mean"]
            stds = stats[col]["std"]
            for j in range(data.shape[0]):
                original[j, i] = original[j, i] * stds[j] + means[j]
        return original


class CrossSectionalNormalizer(BaseNormalizer):
    @property
    def name(self) -> str:
        return "cross_sectional"

    def normalize(self, df: pd.DataFrame, feature_cols: List[str], 
                 training_stats: dict = None) -> Tuple[np.ndarray, dict]:
        if training_stats is None:
            training_stats = {}
            for col in feature_cols:
                mean_dict = df.groupby("trade_date")[col].mean().to_dict()
                std_dict = df.groupby("trade_date")[col].std().to_dict()
                for date in mean_dict:
                    if np.isnan(std_dict[date]) or std_dict[date] < 1e-8:
                        std_dict[date] = 1e-8
                training_stats[col] = {
                    "mean": mean_dict,
                    "std": std_dict,
                }
            training_stats["_trade_dates"] = df["trade_date"].tolist()

        normalized = df.copy()
        for col in feature_cols:
            mean_dict = training_stats[col]["mean"]
            std_dict = training_stats[col]["std"]
            normalized[col] = df.apply(
                lambda row: (row[col] - mean_dict.get(row["trade_date"], 0)) / std_dict.get(row["trade_date"], 1),
                axis=1
            )

        return normalized[feature_cols].values, training_stats

    def inverse_transform(self, data: np.ndarray, feature_cols: List[str], 
                         stats: dict) -> np.ndarray:
        original = data.copy().astype(np.float64)
        trade_dates = stats.get("_trade_dates", [])
        
        for i, col in enumerate(feature_cols):
            mean_dict = stats[col]["mean"]
            std_dict = stats[col]["std"]
            for j in range(data.shape[0]):
                trade_date = trade_dates[j] if j < len(trade_dates) else ""
                mean = mean_dict.get(trade_date, 0)
                std = std_dict.get(trade_date, 1)
                original[j, i] = original[j, i] * std + mean
        return original


class NormalizerRegistry:
    _normalizers = {}

    @classmethod
    def register(cls, normalizer_class: type):
        instance = normalizer_class()
        cls._normalizers[instance.name] = normalizer_class

    @classmethod
    def get(cls, name: str) -> BaseNormalizer:
        if name not in cls._normalizers:
            raise ValueError(f"Normalizer '{name}' not found")
        return cls._normalizers[name]()

    @classmethod
    def list_normalizers(cls) -> list:
        return list(cls._normalizers.keys())


NormalizerRegistry.register(SlidingWindowNormalizer)
NormalizerRegistry.register(CrossSectionalNormalizer)


if __name__ == "__main__":
    test_df = pd.DataFrame({
        "trade_date": ["20240101", "20240101", "20240102", "20240102"],
        "close": [100, 200, 105, 210],
        "volume": [1000, 2000, 1100, 2200],
    })
    
    print("Testing CrossSectionalNormalizer...")
    cs_normalizer = CrossSectionalNormalizer()
    normalized, stats = cs_normalizer.normalize(test_df, ["close", "volume"])
    print(f"Normalized data:\n{normalized}")
    print(f"Stats:\n{stats}")
    original = cs_normalizer.inverse_transform(normalized, ["close", "volume"], stats)
    print(f"Original data:\n{original}")
    
    print("\nTesting SlidingWindowNormalizer...")
    sw_df = pd.DataFrame({
        "trade_date": ["20240101", "20240102", "20240103", "20240104"],
        "close": [100, 101, 102, 103],
    })
    sw_normalizer = SlidingWindowNormalizer(window_size=2)
    normalized, stats = sw_normalizer.normalize(sw_df, ["close"])
    print(f"Normalized data:\n{normalized}")
    print(f"Stats:\n{stats}")
    original = sw_normalizer.inverse_transform(normalized, ["close"], stats)
    print(f"Original data:\n{original}")
    
    print("\nTesting NormalizerRegistry...")
    print(f"Available normalizers: {NormalizerRegistry.list_normalizers()}")
    sw = NormalizerRegistry.get("sliding_window")
    cs = NormalizerRegistry.get("cross_sectional")
    print(f"SlidingWindowNormalizer name: {sw.name}")
    print(f"CrossSectionalNormalizer name: {cs.name}")