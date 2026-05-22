# LSTM/XGBoost 模型架构重构设计

## 概述

本次重构旨在解决现有代码中在训练和回测部分反复判断模型类型的问题，通过引入适配器模式，实现可维护、易扩展的架构。

## 问题分析

现有代码存在以下问题：

1. `predict/training_service.py` 中包含大量 `if model_type == "xgboost"/"lstm"` 判断（第95-107行、第138-159行、第298-303行、第463-475行）
2. `execution/predictor.py` 中同样包含模型类型判断（第87-155行、第158-203行）
3. `execution/pipeline.py` 中也有类似逻辑（第62-76行）
4. 新模型类型需要修改多处代码
5. 代码可维护性差

## 解决方案

### 架构设计

```
backend/src/trade_alpha/
├── models/                          # 【重命名】原 predict/ 目录
│   ├── __init__.py
│   ├── classifiers/              # 模型分类器（保持现有逻辑）
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── xgboost.py
│   │   └── lstm.py
│   ├── normalizers/              # 标准化器（保持现有）
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── cross_sectional.py
│   │   └── sliding_window.py
│   ├── training/                 # 训练相关
│   │   ├── __init__.py
│   │   ├── trainer.py               # 简化的训练服务
│   │   └── config.py                # 配置服务（原 config_service.py）
│   └── adapters/                # 【新增】模型适配器层 ⭐
│       ├── __init__.py
│       ├── base.py                  # 适配器基类
│       ├── registry.py              # 适配器注册器
│       ├── xgboost/
│       │   ├── __init__.py
│       │   ├── trainer_adapter.py    # XGBoost训练适配器
│       │   └── executor_adapter.py   # XGBoost执行适配器
│       └── lstm/
│           ├── __init__.py
│           ├── trainer_adapter.py    # LSTM训练适配器
│           └── executor_adapter.py   # LSTM执行适配器
│
└── execution/                    # 保持
    ├── data_loader.py
    ├── pipeline.py                 # 简化，调用适配器
    ├── predictor.py                # 简化，调用适配器
    ├── schemas.py
    └── service.py
```

## 核心组件

### 1. 适配器基类 (base.py)

```python
from abc import ABC, abstractmethod
from typing import List, Optional
import pandas as pd
import numpy as np

class BaseTrainerAdapter(ABC):
    """训练适配器基类，处理模型特定的训练逻辑"""
    
    @abstractmethod
    def create_normalizer(self, config, target_names: List[str]):
        """创建适合该模型的标准化器
        
        Args:
            config: ModelConfig对象
            target_names: 目标列名列表
            
        Returns:
            标准化器实例
        """
        pass
    
    @abstractmethod
    def create_classifier(self, config):
        """创建分类器实例
        
        Args:
            config: ModelConfig对象
            
        Returns:
            分类器实例
        """
        pass
    
    @abstractmethod
    def get_total_training_stages(self, config, num_years: int, num_targets: int) -> int:
        """计算总训练阶段数，用于进度显示
        
        Args:
            config: ModelConfig对象
            num_years: 年数
            num_targets: 目标数量
            
        Returns:
            总阶段数
        """
        pass
    
    @abstractmethod
    def train_with_progress(
        self,
        classifier,
        X: np.ndarray,
        y: np.ndarray,
        target_names: List[str],
        stage_offset: int,
        total_stages: int,
        update_callback
    ):
        """训练模型，带进度回调
        
        Args:
            classifier: 分类器实例
            X: 特征数据
            y: 标签数据
            target_names: 目标列名列表
            stage_offset: 阶段偏移量
            total_stages: 总阶段数
            update_callback: 进度更新回调函数
        """
        pass


class BaseExecutorAdapter(ABC):
    """执行适配器基类，处理模型特定的回测/实时预测逻辑"""
    
    @abstractmethod
    def create_normalizer(self, config):
        """创建适合该模型的标准化器
        
        Args:
            config: ModelConfig对象
            
        Returns:
            标准化器实例
        """
        pass
    
    @abstractmethod
    async def load_prediction_data(
        self, 
        current_date: str, 
        ts_codes: List[str], 
        config, 
        data_loader
    ) -> pd.DataFrame:
        """加载预测所需的数据
        
        Args:
            current_date: 当前日期
            ts_codes: 股票代码列表
            config: ModelConfig对象
            data_loader: DataLoader实例
            
        Returns:
            加载的数据DataFrame
        """
        pass
    
    @abstractmethod
    def prepare_features(
        self, 
        df: pd.DataFrame, 
        ts_code: str, 
        config
    ) -> Optional[np.ndarray]:
        """为单只股票准备模型输入特征
        
        Args:
            df: 标准化后的数据
            ts_code: 股票代码
            config: ModelConfig对象
            
        Returns:
            特征数组，或None（如果数据不足）
        """
        pass
```

### 2. 适配器注册器 (registry.py)

```python
from typing import Dict, Type
from .base import BaseTrainerAdapter, BaseExecutorAdapter

_trainer_adapters: Dict[str, Type[BaseTrainerAdapter]] = {}
_executor_adapters: Dict[str, Type[BaseExecutorAdapter]] = {}

def register_trainer_adapter(model_type: str, adapter_cls: Type[BaseTrainerAdapter]):
    """注册训练适配器"""
    _trainer_adapters[model_type] = adapter_cls

def register_executor_adapter(model_type: str, adapter_cls: Type[BaseExecutorAdapter]):
    """注册执行适配器"""
    _executor_adapters[model_type] = adapter_cls

def get_trainer_adapter(model_type: str) -> BaseTrainerAdapter:
    """获取训练适配器"""
    if model_type not in _trainer_adapters:
        raise ValueError(f"No trainer adapter for model type: {model_type}")
    return _trainer_adapters[model_type]()

def get_executor_adapter(model_type: str) -> BaseExecutorAdapter:
    """获取执行适配器"""
    if model_type not in _executor_adapters:
        raise ValueError(f"No executor adapter for model type: {model_type}")
    return _executor_adapters[model_type]()
```

## 具体适配器实现

### XGBoost 适配器

#### 训练适配器 (xgboost/trainer_adapter.py)

```python
from typing import List
import numpy as np
from ..base import BaseTrainerAdapter
from ...classifiers.xgboost import XGBoostClassifier
from ...normalizers.cross_sectional import CrossSectionalNormalizer

class XGBoostTrainerAdapter(BaseTrainerAdapter):
    """XGBoost训练适配器"""
    
    def create_normalizer(self, config, target_names: List[str]):
        output_fields = config.feature_fields + target_names + ["trade_date", "ts_code"]
        return CrossSectionalNormalizer(
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=output_fields,
        )
    
    def create_classifier(self, config):
        return XGBoostClassifier(
            n_estimators=config.xgb_n_estimators,
            max_depth=config.xgb_max_depth,
            learning_rate=config.xgb_learning_rate,
            min_child_weight=config.xgb_min_child_weight,
            subsample=config.xgb_subsample,
            colsample_bytree=config.xgb_colsample_bytree,
        )
    
    def get_total_training_stages(self, config, num_years: int, num_targets: int) -> int:
        # XGBoost: 数据加载(2*years) + 训练(1) + 评估(5) + 分析(1) + 完成(1)
        return num_years * 2 + 1 + 5 + 1 + 1
    
    def train_with_progress(
        self,
        classifier,
        X: np.ndarray,
        y: np.ndarray,
        target_names: List[str],
        stage_offset: int,
        total_stages: int,
        update_callback
    ):
        update_callback(stage_offset, "正在训练模型...")
        classifier.fit(X, y, target_names)
```

#### 执行适配器 (xgboost/executor_adapter.py)

```python
from typing import List, Optional
import pandas as pd
import numpy as np
from ..base import BaseExecutorAdapter
from ...normalizers.cross_sectional import CrossSectionalNormalizer

class XGBoostExecutorAdapter(BaseExecutorAdapter):
    """XGBoost执行适配器"""
    
    def create_normalizer(self, config):
        return CrossSectionalNormalizer(
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=config.output_fields,
        )
    
    async def load_prediction_data(
        self, 
        current_date: str, 
        ts_codes: List[str], 
        config, 
        data_loader
    ) -> pd.DataFrame:
        # XGBoost只需要单日数据
        return await data_loader.load_day_data(current_date, ts_codes)
    
    def prepare_features(
        self, 
        df: pd.DataFrame, 
        ts_code: str, 
        config
    ) -> Optional[np.ndarray]:
        stock_data = df[df['ts_code'] == ts_code]
        if stock_data.empty:
            return None
        return stock_data[config.feature_fields].values[0].reshape(1, -1)
```

#### 自动注册 (xgboost/__init__.py)

```python
from .trainer_adapter import XGBoostTrainerAdapter
from .executor_adapter import XGBoostExecutorAdapter
from ..registry import register_trainer_adapter, register_executor_adapter

register_trainer_adapter("xgboost", XGBoostTrainerAdapter)
register_executor_adapter("xgboost", XGBoostExecutorAdapter)
```

---

### LSTM 适配器

#### 训练适配器 (lstm/trainer_adapter.py)

```python
from typing import List
import numpy as np
from ..base import BaseTrainerAdapter
from ...classifiers.lstm import LSTMClassifier
from ...normalizers.sliding_window import SlidingWindowNormalizer

class LSTMTrainerAdapter(BaseTrainerAdapter):
    """LSTM训练适配器"""
    
    def create_normalizer(self, config, target_names: List[str]):
        output_fields = config.feature_fields + target_names + ["trade_date", "ts_code"]
        return SlidingWindowNormalizer(
            window_size=config.lstm_sequence_length,
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=output_fields,
        )
    
    def create_classifier(self, config):
        return LSTMClassifier(
            hidden_size=config.lstm_hidden_size,
            num_layers=config.lstm_num_layers,
            dropout=config.lstm_dropout,
            epochs=config.lstm_epochs,
            batch_size=config.lstm_batch_size,
            learning_rate=config.lstm_learning_rate,
            sequence_length=config.lstm_sequence_length,
        )
    
    def get_total_training_stages(self, config, num_years: int, num_targets: int) -> int:
        # LSTM: 数据加载(2*years) + 训练(lstm_epochs * num_targets) + 评估(5) + 分析(1) + 完成(1)
        return num_years * 2 + config.lstm_epochs * num_targets + 5 + 1 + 1
    
    def train_with_progress(
        self,
        classifier,
        X: np.ndarray,
        y: np.ndarray,
        target_names: List[str],
        stage_offset: int,
        total_stages: int,
        update_callback
    ):
        num_targets = len(target_names)
        
        def lstm_progress_callback(pct, msg):
            training_stages = int(pct / 100 * classifier.epochs * num_targets)
            update_callback(stage_offset + training_stages, msg)
        
        classifier.fit(X, y, target_names, progress_callback=lstm_progress_callback)
```

#### 执行适配器 (lstm/executor_adapter.py)

```python
from typing import List, Optional
import pandas as pd
import numpy as np
from ..base import BaseExecutorAdapter
from ...normalizers.sliding_window import SlidingWindowNormalizer

class LSTMExecutorAdapter(BaseExecutorAdapter):
    """LSTM执行适配器"""
    
    def create_normalizer(self, config):
        return SlidingWindowNormalizer(
            window_size=config.lstm_sequence_length,
            standardize_fields=config.standardize_fields,
            winsorize_fields=config.winsorize_fields,
            output_fields=config.output_fields,
        )
    
    async def load_prediction_data(
        self, 
        current_date: str, 
        ts_codes: List[str], 
        config, 
        data_loader
    ) -> pd.DataFrame:
        # LSTM需要加载历史序列数据
        seq_len = config.lstm_sequence_length
        return await data_loader.load_history_data(
            current_date, ts_codes, seq_len + 10  # 加buffer
        )
    
    def prepare_features(
        self, 
        df: pd.DataFrame, 
        ts_code: str, 
        config
    ) -> Optional[np.ndarray]:
        seq_len = config.lstm_sequence_length
        stock_data = df[df['ts_code'] == ts_code].sort_values('trade_date')
        
        if len(stock_data) < seq_len:
            return None
            
        features = stock_data[config.feature_fields].values
        return features  # LSTM模型内部会取最后seq_len天
```

#### 自动注册 (lstm/__init__.py)

```python
from .trainer_adapter import LSTMTrainerAdapter
from .executor_adapter import LSTMExecutorAdapter
from ..registry import register_trainer_adapter, register_executor_adapter

register_trainer_adapter("lstm", LSTMTrainerAdapter)
register_executor_adapter("lstm", LSTMExecutorAdapter)
```

---

### 统一适配器导出 (adapters/__init__.py)

```python
# 导入所有适配器以自动注册
from . import xgboost
from . import lstm

from .registry import (
    get_trainer_adapter,
    get_executor_adapter,
    register_trainer_adapter,
    register_executor_adapter,
)

__all__ = [
    "get_trainer_adapter",
    "get_executor_adapter",
    "register_trainer_adapter",
    "register_executor_adapter",
]
```

---

## 简化后的核心服务

### 简化的训练服务 (training/trainer.py)

```python
"""简化后的训练服务 - 使用适配器"""

import os
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict
from beanie import PydanticObjectId
import pandas as pd
import numpy as np

from trade_alpha.dao import StockDaily, StockList, TrainingResult, PredictionResult
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.models.adapters.registry import get_trainer_adapter
from trade_alpha.utils.date_utils import get_year_months, format_progress, to_db_format
from trade_alpha.logging import get_logger

logger = get_logger("models.training.trainer")
MODELS_DIR = "models"


def _ensure_model_dir(config_id: str) -> None:
    os.makedirs(os.path.join(MODELS_DIR, config_id), exist_ok=True)


def _create_classification_labels(df: pd.DataFrame, horizons: List[int], threshold: float) -> pd.DataFrame:
    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()
        for horizon in horizons:
            future_pct = (group["close"].shift(-horizon) - group["close"]) / group["close"]
            group[f"label_{horizon}d"] = future_pct.map(
                lambda x: 1 if x > threshold else (-1 if x < -threshold else 0) if pd.notna(x) else None
            )
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)


async def _load_year_data(year: int, ts_codes: List[str], horizon: int) -> Optional[pd.DataFrame]:
    """加载指定年份数据（含未来horizon天）"""
    year_start = f"{year}0101"
    year_end = f"{year}1231"
    future_end = f"{year + (horizon + 180) // 365}1231"
    
    year_dfs = []
    for ts_code in ts_codes:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if not stock or stock.sync_status != "active":
            continue
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= year_start,
            StockDaily.trade_date <= future_end,
        ).sort(StockDaily.trade_date).to_list()
        if not records:
            continue
        df = pd.DataFrame([r.model_dump() for r in records])
        df["ts_code"] = ts_code
        year_dfs.append(df)
    
    return pd.concat(year_dfs, ignore_index=True) if year_dfs else None


def _analyze_normalized_data(all_norm_dfs: List[pd.DataFrame], feature_fields: List[str]) -> Dict[str, Any]:
    """分析标准化数据"""
    from trade_alpha.data.analysis_service import compute_field_analysis

    feature_dfs = [df[feature_fields] for df in all_norm_dfs]
    normalized_df = pd.concat(feature_dfs, ignore_index=True)
    result = compute_field_analysis(normalized_df, feature_fields)
    for field in result["statistics"]:
        result["statistics"][field]["missing_rate"] = 0.0
    for field in result["missing_data"]:
        result["missing_data"][field]["missing"] = 0
        result["missing_data"][field]["rate"] = 0.0
    return result


async def _evaluate_classifier(
    classifier,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    targets: List[str],
    n_splits: int = 5,
    progress_callback: Optional[callable] = None,
) -> Dict:
    """评估分类器性能，支持多目标"""
    from sklearn.model_selection import KFold

    metrics = {}

    async def _call_progress(pct: float, msg: str):
        if progress_callback:
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(pct, msg)
                else:
                    progress_callback(pct, msg)
            except Exception:
                pass

    await _call_progress(0, "正在计算准确率...")

    for i, target in enumerate(targets):
        y_i = y[:, i] if y.ndim > 1 else y
        
        y_pred = classifier.predict(X, [target])[target]
        accuracy = np.mean(y_pred == y_i)
        metrics.setdefault("accuracy", {})[target] = float(accuracy)

        unique, counts = np.unique(y_i, return_counts=True)
        class_dist = {str(int(k)): float(v) / len(y_i) for k, v in zip(unique, counts)}
        metrics.setdefault("class_distribution", {})[target] = class_dist

        model = classifier.models[target]
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
            importance_dict = {f: float(imp) for f, imp in zip(feature_names, importances)}
            metrics.setdefault("feature_importance", {})[target] = importance_dict

    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    is_lstm = hasattr(classifier, "sequence_length")
    
    for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X)):
        await _call_progress((fold_idx + 1) / n_splits * 100, f"交叉验证 Fold {fold_idx + 1}/{n_splits}...")
        
        X_train, X_val = X[train_idx], X[val_idx]
        
        for i, target in enumerate(targets):
            y_train, y_val = y[train_idx, i], y[val_idx, i]
            
            if is_lstm:
                y_val_pred = classifier.predict(X_val, [target]).get(target, y_val[0])
                fold_accuracy = float(np.mean(y_val_pred == y_val))
            else:
                unique_labels = sorted(set(y_train))
                label_map = {label: j for j, label in enumerate(unique_labels)}
                y_train_mapped = np.array([label_map[v] for v in y_train])
                y_val_mapped = np.array([label_map[v] for v in y_val])
                
                model_cls = classifier.models[target].__class__
                model = model_cls(**classifier.models[target].get_params())
                model.fit(X_train, y_train_mapped)
                
                y_val_pred_mapped = model.predict(X_val)
                y_val_pred = np.array([unique_labels[j] for j in y_val_pred_mapped])
                fold_accuracy = float(np.mean(y_val_pred == y_val))
            
            if target not in metrics.get("cv_scores", {}):
                metrics.setdefault("cv_scores", {})[target] = []
            metrics["cv_scores"][target].append(fold_accuracy)

    for target in targets:
        if target in metrics["cv_scores"]:
            scores = np.array(metrics["cv_scores"][target])
            metrics.setdefault("cv_mean", {})[target] = float(scores.mean())
            metrics.setdefault("cv_std", {})[target] = float(scores.std())

    return metrics


async def create_training(
    config_id: PydanticObjectId,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
    progress_callback: Optional[callable] = None,
) -> TrainingResult:
    """训练流程：逐年加载→逐年计算标签→逐年标准化→一次性训练"""
    existing = await get_training_by_name(name)
    if existing:
        raise ValueError(f"Training already exists: {name}")

    config = await get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    # 获取模型适配器
    adapter = get_trainer_adapter(config.model_type)

    year_months = get_year_months(start_date, end_date)
    years = sorted(set(y for y, _ in year_months))
    num_years = len(years)
    
    target_names = [f"label_{h}d" for h in config.classification_horizons]
    num_targets = len(target_names)
    
    total_stages = adapter.get_total_training_stages(config, num_years, num_targets)

    async def update(stage_num: int, msg: str):
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(stage_num / total_stages * 100, msg)
            else:
                progress_callback(stage_num / total_stages * 100, msg)

    stage = 0
    horizon = max(config.classification_horizons)
    all_norm_dfs = []

    # 创建标准化器
    normalizer = adapter.create_normalizer(config, target_names)

    for year_idx, year in enumerate(years):
        year_num = year_idx + 1

        stage += 1
        await update(stage, format_progress("load", year, idx=year_num, total=num_years))
        year_df = await _load_year_data(year, ts_codes, horizon)
        if year_df is None:
            continue

        stage += 1
        await update(stage, format_progress("label", year, idx=year_num, total=num_years))
        year_df = _create_classification_labels(year_df, config.classification_horizons, config.classification_threshold)

        year_norm = normalizer.normalize(year_df)
        year_norm = year_norm.dropna(subset=config.feature_fields + target_names)
        if not year_norm.empty:
            all_norm_dfs.append(year_norm)

    if not all_norm_dfs:
        raise ValueError("No available data")

    # Extract features and targets from normalized dfs
    X = np.vstack([df[config.feature_fields].values for df in all_norm_dfs])
    y = np.vstack([df[target_names].values for df in all_norm_dfs])
    sample_count = len(X)

    classifier = adapter.create_classifier(config)
    
    # 使用适配器的训练方法
    adapter.train_with_progress(
        classifier, X, y, target_names, 
        stage, total_stages, update
    )
    
    stage = total_stages - 5 - 1 - 1  # 减去评估、分析、完成的阶段

    stage += 1
    await update(stage, "正在评估模型...")
    eval_metrics = await _evaluate_classifier(
        classifier,
        X,
        y,
        config.feature_fields,
        target_names,
        n_splits=5,
        progress_callback=lambda pct, msg: update(stage + pct / 100 * 5, msg)
    )

    stage += 1
    await update(stage, "正在分析标准化数据...")
    training_normalized_analysis = _analyze_normalized_data(all_norm_dfs, config.feature_fields)

    await update(total_stages, format_progress("done", years[-1]))

    training = TrainingResult(
        config_id=config_id,
        name=name,
        ts_codes=ts_codes,
        start_date=start_date,
        end_date=end_date,
        feature_fields=config.feature_fields,
        classification_horizons=config.classification_horizons,
        model_metrics={"sample_count": sample_count, **eval_metrics},
        normalized_data_analysis=training_normalized_analysis,
        created_at=datetime.now(timezone.utc),
    )
    await training.insert()

    _ensure_model_dir(str(config_id))
    model_path = os.path.join(MODELS_DIR, str(config_id), f"{training.id}.pkl")
    classifier.save(model_path)

    training.model_path = model_path
    await training.save()

    logger.info(f"Training completed: name={name} id={training.id} samples={sample_count}")
    return training


async def get_training_by_id(training_id: PydanticObjectId) -> Optional[TrainingResult]:
    return await TrainingResult.get(training_id)


async def get_training_by_name(name: str) -> Optional[TrainingResult]:
    return await TrainingResult.find_one(TrainingResult.name == name)


async def list_trainings(config_id: PydanticObjectId = None) -> List[TrainingResult]:
    if config_id:
        return await TrainingResult.find(TrainingResult.config_id == config_id).sort(-TrainingResult.created_at).to_list()
    return await TrainingResult.find_all().sort(-TrainingResult.created_at).to_list()


async def delete_training(training_id: PydanticObjectId) -> bool:
    training = await TrainingResult.get(training_id)
    if not training:
        return False
    if training.model_path and os.path.exists(training.model_path):
        os.remove(training.model_path)
    await PredictionResult.find(PredictionResult.training_result_id == training_id).delete()
    await training.delete()
    return True


async def delete_training_by_name(name: str) -> bool:
    training = await get_training_by_name(name)
    if not training:
        return False
    return await delete_training(training.id)


async def predict_with_training(training_id: PydanticObjectId, ts_code: str) -> Dict:
    """Predict using trained model."""
    from trade_alpha.models.training.config import get_config_by_id

    training = await get_training_by_id(training_id)
    if not training:
        raise ValueError(f"Training not found: {training_id}")

    config = await get_config_by_id(training.config_id)
    if not config:
        raise ValueError(f"Config not found: {training.config_id}")

    records = await StockDaily.find(
        StockDaily.ts_code == ts_code
    ).sort(-StockDaily.trade_date).to_list()

    if not records:
        raise ValueError(f"No data for {ts_code}")

    df = pd.DataFrame([r.model_dump() for r in records])
    df = df.sort_values("trade_date")

    target_names = [f"label_{h}d" for h in training.classification_horizons]
    
    # 获取适配器并创建标准化器
    adapter = get_trainer_adapter(config.model_type)
    normalizer = adapter.create_normalizer(config, target_names)

    df_norm = normalizer.normalize(df)
    df_norm = df_norm.dropna(subset=config.feature_fields)
    if len(df_norm) == 0:
        raise ValueError("No valid data after normalization")

    # 创建并加载分类器
    classifier = adapter.create_classifier(config)
    classifier.load(training.model_path)

    # 直接使用所有可用数据，模型内部会处理
    features = df_norm[config.feature_fields].values

    predictions = classifier.predict(features, target_names)
    probabilities = classifier.predict_proba(features, target_names)

    last_date = df["trade_date"].iloc[-1]

    prediction = PredictionResult(
        training_result_id=training_id,
        ts_code=ts_code,
        trade_date=last_date,
        predictions=predictions,
        probabilities=probabilities,
        created_at=datetime.now(timezone.utc),
    )
    await prediction.insert()

    return {"predictions": predictions, "probabilities": probabilities}


async def get_prediction_by_id(prediction_id: PydanticObjectId) -> Optional[PredictionResult]:
    return await PredictionResult.get(prediction_id)


async def delete_prediction(prediction_id: PydanticObjectId) -> bool:
    prediction = await PredictionResult.get(prediction_id)
    if not prediction:
        return False
    await prediction.delete()
    return True
```

---

### 简化的预测器 (execution/predictor.py)

```python
"""简化后的预测器 - 使用适配器"""

from typing import Dict, List, Optional, TYPE_CHECKING
import pandas as pd
import numpy as np
from beanie import PydanticObjectId
from trade_alpha.models.training.trainer import get_training_by_id, predict_with_training
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.models.adapters.registry import get_executor_adapter
from trade_alpha.logging import get_logger

if TYPE_CHECKING:
    from trade_alpha.models.normalizers.base import BaseNormalizer

logger = get_logger("execution.predictor")


class Predictor:
    """简化的批量预测器 - 使用适配器"""
    
    def __init__(self, training_id: PydanticObjectId, normalizer: Optional["BaseNormalizer"] = None, data_loader=None):
        self.training_id = training_id
        self._normalizer_override = normalizer
        self._training = None
        self._config = None
        self._classifier = None
        self._adapter = None
        self._normalizer = None
        self._data_loader = data_loader
    
    async def _ensure_model_loaded(self):
        """延迟加载模型和配置"""
        if self._classifier is not None:
            return
        
        self._training = await get_training_by_id(self.training_id)
        if not self._training:
            raise ValueError(f"Training not found: {self.training_id}")
        
        self._config = await get_config_by_id(self._training.config_id)
        if not self._config:
            raise ValueError(f"Config not found: {self._training.config_id}")
        
        # 获取适配器
        self._adapter = get_executor_adapter(self._config.model_type)
        
        # 使用适配器创建标准化器，或使用覆盖的标准化器
        if self._normalizer_override is not None:
            self._normalizer = self._normalizer_override
        else:
            self._normalizer = self._adapter.create_normalizer(self._config)
        
        # 加载分类器
        from trade_alpha.models.classifiers import CLASSIFIERS
        self._classifier = CLASSIFIERS[self._config.model_type]()
        self._classifier.load(self._training.model_path)
        
        logger.info("Model loaded successfully")
    
    async def predict_batch_with_history(
        self, 
        day_df: pd.DataFrame, 
        ts_codes: List[str],
        current_date: str
    ) -> Dict[str, Dict]:
        """使用适配器进行预测"""
        await self._ensure_model_loaded()
        
        result = {}
        
        if day_df.empty:
            return result
        
        target_names = [f"label_{h}d" for h in self._training.classification_horizons]
        
        # 使用适配器加载数据
        df = await self._adapter.load_prediction_data(
            current_date, ts_codes, self._config, self._data_loader
        )
        
        if df.empty:
            return result
        
        # 标准化
        normalizer_input = self._config.feature_fields + ['trade_date', 'ts_code']
        available_fields = [f for f in normalizer_input if f in df.columns]
        normalized = self._normalizer.normalize(df[available_fields])
        
        # 遍历每只股票预测
        for ts_code in ts_codes:
            try:
                # 使用适配器准备特征
                features = self._adapter.prepare_features(
                    normalized, ts_code, self._config
                )
                
                if features is None:
                    continue
                
                if np.isnan(features).any():
                    logger.debug(f"NaN features for {ts_code}, skipping")
                    continue
                
                # 预测
                predictions = self._classifier.predict(features, target_names)
                probabilities = self._classifier.predict_proba(features, target_names)
                
                if not predictions or not probabilities:
                    continue
                
                up_prob_3d = probabilities.get("label_3d", [0.0, 0.0, 0.0])[2] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0.0
                up_prob_5d = probabilities.get("label_5d", [0.0, 0.0, 0.0])[2] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0.0
                down_prob_3d = probabilities.get("label_3d", [0.0, 0.0, 0.0])[0] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0.0
                down_prob_5d = probabilities.get("label_5d", [0.0, 0.0, 0.0])[0] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0.0
                
                score_3d = up_prob_3d - down_prob_3d
                score_5d = up_prob_5d - down_prob_5d
                score = score_3d * 0.4 + score_5d * 0.6
                
                # 获取收盘价
                day_row = day_df[day_df['ts_code'] == ts_code]
                close = float(day_row.iloc[0]['close']) if not day_row.empty else 0
                
                result[ts_code] = {
                    "up_prob_3d": up_prob_3d,
                    "up_prob_5d": up_prob_5d,
                    "down_prob_3d": down_prob_3d,
                    "down_prob_5d": down_prob_5d,
                    "score": score,
                    "close": close,
                }
                
            except Exception as e:
                logger.warning(f"Predict failed for {ts_code}: {e}")
                continue
        
        return result

    async def predict_batch(self, df: pd.DataFrame, ts_codes: List[str]) -> Dict[str, Dict]:
        """Legacy batch prediction method (single stock, not cross-sectional)."""
        await self._ensure_model_loaded()
        
        result = {}
        for ts_code in ts_codes:
            stock_df = df[df["ts_code"] == ts_code]
            if stock_df.empty:
                continue
            try:
                pred = await self._predict_single(stock_df, ts_code)
                result[ts_code] = pred
            except Exception as e:
                logger.warning(f"Predict failed for {ts_code}: {e}")
                continue
        return result

    async def _predict_single(self, df: pd.DataFrame, ts_code: str) -> Dict:
        """Internal single stock prediction."""
        pred = await predict_with_training(self.training_id, ts_code)
        probs = pred.get("probabilities", {})
        up_prob_3d = probs.get("label_3d", [0.0, 0.0, 0.0])[2] if isinstance(probs.get("label_3d"), list) and len(probs["label_3d"]) == 3 else 0.0
        up_prob_5d = probs.get("label_5d", [0.0, 0.0, 0.0])[2] if isinstance(probs.get("label_5d"), list) and len(probs["label_5d"]) == 3 else 0.0
        down_prob_3d = probs.get("label_3d", [0.0, 0.0, 0.0])[0] if isinstance(probs.get("label_3d"), list) and len(probs["label_3d"]) == 3 else 0.0
        down_prob_5d = probs.get("label_5d", [0.0, 0.0, 0.0])[0] if isinstance(probs.get("label_5d"), list) and len(probs["label_5d"]) == 3 else 0.0
        score_3d = up_prob_3d - down_prob_3d
        score_5d = up_prob_5d - down_prob_5d
        score = score_3d * 0.4 + score_5d * 0.6
        return {
            "up_prob_3d": up_prob_3d,
            "up_prob_5d": up_prob_5d,
            "down_prob_3d": down_prob_3d,
            "down_prob_5d": down_prob_5d,
            "score": score,
            "close": float(df.iloc[-1]["close"]) if "close" in df.columns else 0,
        }

    async def predict_single(self, df: pd.DataFrame, ts_code: str) -> Dict:
        """Predict single stock."""
        stock_df = df[df["ts_code"] == ts_code]
        if stock_df.empty:
            return {"up_prob_3d": None, "up_prob_5d": None, "down_prob_3d": None, "down_prob_5d": None, "score": None}
        try:
            return await self._predict_single(stock_df, ts_code)
        except Exception as e:
            logger.warning(f"Predict single failed for {ts_code}: {e}")
            return {"up_prob_3d": 0.0, "up_prob_5d": 0.0, "score": 0.0}
```

---

## 顶层导出 (models/__init__.py)

```python
# 导出主要接口
from .adapters import get_trainer_adapter, get_executor_adapter
from .training.trainer import (
    create_training,
    get_training_by_id,
    get_training_by_name,
    list_trainings,
    delete_training,
    delete_training_by_name,
    predict_with_training,
    get_prediction_by_id,
    delete_prediction,
)
from .training.config import (
    create_config,
    get_config_by_id,
    get_config_by_name,
    list_configs,
    update_config,
    delete_config,
)

__all__ = [
    "get_trainer_adapter",
    "get_executor_adapter",
    "create_training",
    "get_training_by_id",
    "get_training_by_name",
    "list_trainings",
    "delete_training",
    "delete_training_by_name",
    "predict_with_training",
    "get_prediction_by_id",
    "delete_prediction",
    "create_config",
    "get_config_by_id",
    "get_config_by_name",
    "list_configs",
    "update_config",
    "delete_config",
]
```

---

## 架构图

```
┌─────────────────────────────────────────────────────────┐
│                     外部调用 (API / Pipeline)                 │
└──────────────┬───────────────────────────────┬─────────────┘
           │                           │
           ▼                           ▼
┌──────────────────┐        ┌──────────────────┐
│  training/trainer.py │        │ execution/    │
│  (简化)           │        │ predictor.py   │
└────────┬─────────┘        └──────┬───────────┘
         │                   │
         └────────┬────────────┘
                  │
                  ▼
┌─────────────────────────────────┐
│   models/adapters/registry.py  │
│   (按模型类型查找适配器)         │
└────────┬────────────────┘
         │
    ┌────┴────────────────┐
    ▼                 ▼
┌──────────┐     ┌──────────┐
│ XGBoost │     │  LSTM   │
│ Adapter │     │ Adapter │
└────┬─────┘     └────┬─────┘
     │              │
     ▼              ▼
┌─────────────────────────────────┐
│   classifiers/, normalizers/    │
│   (可复用核心组件)            │
└─────────────────────────────────┘
```

---

## 实施计划

### 阶段 1: 准备阶段 - 创建目录结构和适配器基础设施

**目标**: 建立新的目录结构和适配器基类

**任务**:
1. 创建 `models/` 新目录结构
   - `models/classifiers/`
   - `models/normalizers/`
   - `models/training/`
   - `models/adapters/xgboost/`
   - `models/adapters/lstm/`

2. 移动现有文件到新位置
   - 移动 `predict/models/*` → `models/classifiers/`
   - 移动 `predict/normalizers/*` → `models/normalizers/`
   - 更新相关文件的导入路径

3. 实现适配器基类 (`models/adapters/base.py`)
   - 定义 `BaseTrainerAdapter` 抽象基类
   - 定义 `BaseExecutorAdapter` 抽象基类

4. 实现适配器注册器 (`models/adapters/registry.py`)
   - 实现 `register_trainer_adapter`
   - 实现 `register_executor_adapter`
   - 实现 `get_trainer_adapter`
   - 实现 `get_executor_adapter`

5. 创建 XGBoost 和 LSTM 适配器的空架子
   - 创建空的 `xgboost/__init__.py`, `xgboost/trainer_adapter.py`, `xgboost/executor_adapter.py`
   - 创建空的 `lstm/__init__.py`, `lstm/trainer_adapter.py`, `lstm/executor_adapter.py`

**验证**:
- 检查目录结构创建成功
- 确保文件移动后导入路径暂时保持兼容（先不修改使用方）
- 运行现有测试 `pytest tests/unit/predict/ -v` 确保基本功能正常

---

### 阶段 2: 实现 XGBoost 适配器

**目标**: 实现完整的 XGBoost 训练和执行适配器

**任务**:
1. 实现 `XGBoostTrainerAdapter` (`models/adapters/xgboost/trainer_adapter.py`)
   - `create_normalizer` 方法
   - `create_classifier` 方法
   - `get_total_training_stages` 方法
   - `train_with_progress` 方法

2. 实现 `XGBoostExecutorAdapter` (`models/adapters/xgboost/executor_adapter.py`)
   - `create_normalizer` 方法
   - `load_prediction_data` 方法
   - `prepare_features` 方法

3. 创建适配器自动注册 (`models/adapters/xgboost/__init__.py`)

4. 编写适配器的单元测试 (`tests/unit/models/adapters/test_xgboost_adapter.py`)

**验证**:
- 运行单元测试 `pytest tests/unit/models/adapters/test_xgboost_adapter.py -v`
- 暂时保持现有代码不变，确保系统仍可运行

---

### 阶段 3: 实现 LSTM 适配器

**目标**: 实现完整的 LSTM 训练和执行适配器

**任务**:
1. 实现 `LSTMTrainerAdapter` (`models/adapters/lstm/trainer_adapter.py`)
   - `create_normalizer` 方法
   - `create_classifier` 方法
   - `get_total_training_stages` 方法
   - `train_with_progress` 方法

2. 实现 `LSTMExecutorAdapter` (`models/adapters/lstm/executor_adapter.py`)
   - `create_normalizer` 方法
   - `load_prediction_data` 方法
   - `prepare_features` 方法

3. 创建适配器自动注册 (`models/adapters/lstm/__init__.py`)

4. 编写适配器的单元测试 (`tests/unit/models/adapters/test_lstm_adapter.py`)

**验证**:
- 运行单元测试 `pytest tests/unit/models/adapters/test_lstm_adapter.py -v`

---

### 阶段 4: 重构训练服务

**目标**: 迁移 `training_service.py` 到 `models/training/trainer.py`，使用适配器

**任务**:
1. 创建 `models/training/trainer.py`
   - 复制原 `predict/training_service.py` 的所有代码
   - 修改导入路径使用新的适配器架构
   - 移除所有 `if model_type == "xgboost"/"lstm"` 判断
   - 用适配器替换原有的模型特定逻辑

2. 迁移 `config_service.py` 到 `models/training/config.py`
   - 复制原 `predict/config_service.py`
   - 更新导入路径

3. 更新 `models/__init__.py` 导出接口

4. 更新 API 层的导入路径
   - 更新 `api/routers/model_configs.py`
   - 更新 `api/routers/trainings.py`
   - 更新 `api/routers/predict.py`

5. 更新单元测试的导入路径

**验证**:
- 运行集成测试 `pytest tests/integration/test_51_training_xgboost.py -v`
- 运行集成测试 `pytest tests/integration/test_53_training_lstm.py -v`
- 确保训练功能完全正常

---

### 阶段 5: 重构预测器和执行管道

**目标**: 重构 `execution/predictor.py` 和 `execution/pipeline.py`

**任务**:
1. 重构 `execution/predictor.py`
   - 移除所有 `if model_type == "xgboost"/"lstm"` 判断
   - 使用适配器替换原有的模型特定逻辑
   - 更新 `_ensure_model_loaded` 方法
   - 更新 `predict_batch_with_history` 方法

2. 更新 `execution/pipeline.py`
   - 移除模型类型判断逻辑
   - 使用适配器创建标准化器

3. 更新所有相关的导入路径

**验证**:
- 运行集成测试 `pytest tests/integration/test_52_predict_xgboost.py -v`
- 运行集成测试 `pytest tests/integration/test_54_predict_lstm.py -v`
- 运行回测相关的集成测试

---

### 阶段 6: 清理和收尾

**目标**: 移除旧代码，完善文档

**任务**:
1. 删除旧的 `predict/` 目录

2. 更新顶层 `__init__.py` 和相关模块导入

3. 更新所有相关文档
   - 更新 `docs/system-design.md`
   - 更新其他相关文档

4. 运行完整测试套件

**验证**:
- 运行完整测试套件 `pytest tests/ -v`
- 确保所有测试通过

---

## 验收标准

- 所有现有集成测试通过
- 没有模型类型判断的 if 语句
- 代码可维护性提升
- 易于扩展新模型类型
