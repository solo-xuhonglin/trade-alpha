# 模型架构简化设计

## 概述

移除适配器层抽象，将标准化器下沉到各模型模块内部。每个模型类型自闭环——自己的标准化、训练、预测逻辑都集中在自己的模块中。同时修复 LSTM 数据流问题：先构造序列，再对序列内部做 Z-score 标准化。

## 问题背景

当前架构使用适配器模式统一 XGBoost 和 LSTM 的数据处理流程。实际上两者的数据处理方式完全不同：

- **XGBoost**：截面标准化（当日所有股票的 Z-score），模型输入是单行特征向量
- **LSTM**：时间序列，模型输入是连续多天序列，标准化应该基于序列内部

适配器层并没有消除复杂度，只是把逻辑转发了一手，反而增加了理解和维护成本。每次新增逻辑都需要穿越多个层。

## 设计原则

1. **自闭环**：每个模型类型拥有完整的标准化、训练、预测、保存/加载逻辑
2. **扁平化**：去掉不必要的抽象层
3. **精确标准化**：LSTM 先构造序列再标准化，序列内部使用统一的统计量
4. **YAGNI**：只为当前存在的两个模型设计，不为未来假设的模型做抽象

## 目录结构

```
backend/src/trade_alpha/models/
├── __init__.py
├── base.py                     # 简约模型基类
├── xgboost/
│   ├── __init__.py
│   ├── classifier.py            # XGBoostClassifier（完整闭环）
│   └── normalizer.py            # CrossSectionalNormalizer
├── lstm/
│   ├── __init__.py
│   ├── classifier.py            # LSTMModel + LSTMClassifier（完整闭环）
│   └── normalizer.py            # LSTM 序列内标准化器
├── training/
│   ├── config.py                # 配置服务（不变）
│   └── trainer.py               # 分流器
└── execution/
    └── predictor.py             # 分流器
```

### 删除的目录/文件

- `models/adapters/` 整个目录
- `models/classifiers/` 整个目录
- `models/normalizers/base.py`
- `models/normalizers/sliding_window.py` → 迁移到 `lstm/normalizer.py`
- `models/normalizers/cross_sectional.py` → 迁移到 `xgboost/normalizer.py`
- `models/normalizers/__init__.py` → 移除（无 normalizer 模块）
- `models/normalizers/registry.py` → 移除

## 基类设计

简约基类，`__init__` 接收 `config` 对象，`train()` 只接收运行时数据参数。每个模型内部从 `self.config` 读取配置并完成数据加载→标准化→训练。

```python
# models/base.py
from abc import ABC, abstractmethod
from typing import Dict


class BaseClassifier(ABC):
    def __init__(self, config):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def train(self, ts_codes, start_date, end_date, task_id=None) -> Dict:
        """自闭环训练：加载数据 → 标准化 → 训练 → 返回指标。

        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            task_id: 任务 ID（用于进度更新）
        """

    @abstractmethod
    def predict(self, features, target_names) -> Dict: ...

    @abstractmethod
    def predict_proba(self, features, target_names) -> Dict: ...

    @abstractmethod
    def save(self, path: str) -> None: ...

    @abstractmethod
    def load(self, path: str) -> None: ...
```

## LSTM 模块设计

### LSTM 数据流变更（核心）

**旧流程（有问题）**：
```
原始数据 → 滑动窗口Z-score(按股票分组) → 拼接 → 构造序列(重叠窗口) → LSTM训练
    问题：同一个序列内的不同时间步使用了不同范围的滚动窗口标准化
```

**新流程（修复）**：
```
原始数据 → 按股票分组 → 构造序列(重叠窗口) → 对每条序列内部做Z-score → LSTM训练
    序列内所有时间步使用该序列自身的mean/std，统计口径一致
```

### LSTM 序列内标准化计算方法

对于一条 seq_len=60 的序列 `S = [x_1, x_2, ..., x_60]`：

```
对于每个特征 f:
  mean_f = mean(S[f])    # 该序列60天的均值
  std_f  = std(S[f])     # 该序列60天的标准差
  S[f]_norm = (S[f] - mean_f) / std_f   # 序列内标准化
```

**回测/预测时**：同样取最近 seq_len 天数据，使用该序列自身的统计量标准化。

### LSTM Normalizer

```python
# models/lstm/normalizer.py
def create_sequences(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """按 ts_code 分组 → 构造重叠序列 → 序列内标准化

    返回:
        X: (n_samples, sequence_length, n_features) - 已标准化
        y: (n_samples, n_targets) - 标签
    """
```

### LSTMClassifier

```python
class LSTMClassifier(BaseClassifier):
    def __init__(self, config):
        super().__init__(config)
        self.sequence_length = config.lstm_sequence_length
        ...

    async def train(self, ts_codes, start_date, end_date, task_id=None) -> Dict:
        """自闭环训练：
        1. 逐年从 MongoDB 加载日线数据（加载 seq_len+10 天冗余）
        2. 计算分类标签
        3. create_sequences() 构造序列 + 序列内标准化
        4. 训练 LSTM
        5. 返回指标
        """

    def predict(self, features, target_names) -> Dict[str, int]:
        # features 是 (seq_len, n_features) 原始数据
        # 内部做序列内标准化 → reshape(1, seq_len, -1) → 预测

    def predict_proba(self, features, target_names) -> Dict[str, List[float]]:
        # 同上，返回概率
```

注意：当前 LSTM predict() 接受的 features 是二维 `(样本数, 特征数)`，内部再取最后 seq_len 行构造序列。改为后 features 应为三维 `(1, seq_len, 特征数)`，标准化在 classifier 外部完成，classifier 直接使用。但为简化调用方逻辑，实际实现中 predict() 仍接收二维 `(seq_len, 特征数)`，在方法内部做 reshape(1, seq_len, -1)。

## XGBoost 模块设计

### XGBoost 数据流（不变）

```
原始数据 → 截面Z-score(按日期分组) → 单行特征向量 → XGBoost训练
```

### XGBoost Normalizer

```python
# models/xgboost/normalizer.py
def normalize(df, feature_fields, standardize_fields, winsorize_fields):
    """按 trade_date 分组做 Z-score 标准化"""
```

### XGBoostClassifier

```python
class XGBoostClassifier(BaseClassifier):
    def __init__(self, config):
        super().__init__(config)
        self.n_estimators = config.xgb_n_estimators
        ...

    async def train(self, ts_codes, start_date, end_date, task_id=None) -> Dict:
        """自闭环训练：
        1. 逐年从 MongoDB 加载日线数据
        2. 计算分类标签
        3. 截面标准化（按日期分组 Z-score）
        4. 堆叠成 2D → 训练 XGBoost
        5. 返回指标
        """

    def predict(self, features, target_names) -> Dict[str, int]:
        # features 是 (1, n_features) 标准化后的特征

    def predict_proba(self, features, target_names) -> Dict[str, List[float]]:
        # 同上，返回概率
```

## 训练分流器（变薄）

trainer.py 只做编排调度，不介入数据加载和标准化。创建 classifier 时传入 config，内部自己取参数。

```python
# models/training/trainer.py

async def create_training(config_id, name, ts_codes, start_date, end_date, task_id=None):
    config = await get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    if config.model_type == "xgboost":
        from trade_alpha.models.xgboost.classifier import XGBoostClassifier
        classifier = XGBoostClassifier(config)
    elif config.model_type == "lstm":
        from trade_alpha.models.lstm.classifier import LSTMClassifier
        classifier = LSTMClassifier(config)
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    metrics = await classifier.train(ts_codes, start_date, end_date, task_id)

    training = TrainingResult(...)
    await training.insert()

    model_path = f"models/{config_id}/{training.id}.pkl"
    classifier.save(model_path)
    training.model_path = model_path
    await training.save()

    return training
```

注意：LSTM `predict()` 接收 `(seq_len, n_features)` 原始数据，内部做序列内标准化。

## 预测分流器

predictor.py 按模型类型加载数据并准备特征格式，然后调用各自模型的 predict()。

```python
# execution/predictor.py

async def predict_batch_with_history(day_df, ts_codes, current_date):
    config = await get_config_by_id(training.config_id)

    if config.model_type == "xgboost":
        from trade_alpha.models.xgboost.normalizer import normalize as xgb_normalize
        df = await data_loader.load_day_data(current_date, ts_codes)
        norm = xgb_normalize(df, config.feature_fields, config.standardize_fields, config.winsorize_fields)
        for ts_code in ts_codes:
            row = norm[norm.ts_code == ts_code]
            if row.empty: continue
            features = row[config.feature_fields].values[0].reshape(1, -1)
            pred = classifier.predict(features, target_names)

    elif config.model_type == "lstm":
        df = await data_loader.load_history_data(current_date, ts_codes, seq_len + 10)
        for ts_code in ts_codes:
            stock = df[df.ts_code == ts_code].sort_values("trade_date")
            if len(stock) < seq_len: continue
            features = stock[config.feature_fields].values[-seq_len:]
            pred = classifier.predict(features, target_names)
```

## 测试要点

1. LSTM 序列内标准化后，同一序列内各时间步的统计口径一致
2. 预测时的标准化方式与训练完全一致
3. XGBoost 数据流未改变
4. 所有集成测试通过
