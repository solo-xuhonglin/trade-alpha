# 训练阶段简化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 简化训练进度跟踪机制，使用常量替代动态计算stage

**Architecture:** 新建 Stage 常量类，定义各阶段的文本和百分比范围。移除适配器中的 stage 计算方法，简化训练服务中的进度更新逻辑。

**Tech Stack:** Python, Beanie ODM

---

## 文件变更

| 操作 | 文件路径 | 说明 |
|------|----------|------|
| 创建 | `models/training/stages.py` | 定义 Stage 常量类 |
| 修改 | `models/adapters/base.py` | 移除 stage 相关抽象方法 |
| 修改 | `models/adapters/xgboost/trainer_adapter.py` | 简化适配器 |
| 修改 | `models/adapters/lstm/trainer_adapter.py` | 简化适配器 |
| 修改 | `models/training/trainer.py` | 使用 Stage 常量 |

---

## Task 1: 创建 Stage 常量类

**Files:**
- Create: `backend/src/trade_alpha/models/training/stages.py`

- [ ] **Step 1: 创建 stages.py 文件**

```python
"""训练阶段常量定义"""

from dataclasses import dataclass


@dataclass
class Stage:
    """训练阶段定义
    
    Attributes:
        message: 阶段描述文本
        start_pct: 起始百分比
        end_pct: 结束百分比
    """
    message: str
    start_pct: float
    end_pct: float
    
    @property
    def pct(self) -> float:
        """返回起始百分比（用于进度更新）"""
        return self.start_pct


DATA_LOAD = Stage("正在加载数据...", 0, 30)
LABEL_CALC = Stage("正在计算标签...", 30, 40)
NORMALIZE = Stage("正在标准化数据...", 40, 50)
TRAINING = Stage("正在训练模型...", 50, 85)
EVALUATE = Stage("正在评估模型...", 85, 95)
ANALYSIS = Stage("正在分析数据...", 95, 98)
DONE = Stage("完成", 100, 100)
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/models/training/stages.py
git commit -m "feat: add Stage constants for training progress"
```

---

## Task 2: 简化 BaseTrainerAdapter

**Files:**
- Modify: `backend/src/trade_alpha/models/adapters/base.py:35-71`

- [ ] **Step 1: 移除 stage 相关方法**

保留以下方法：
- `create_normalizer()`
- `create_classifier()`

移除以下方法：
- `get_total_training_stages()`
- `train_with_progress()`

修改后的 `BaseTrainerAdapter`:

```python
class BaseTrainerAdapter(ABC):
    """训练适配器基类，处理模型特定的训练逻辑"""

    @abstractmethod
    def create_normalizer(self, config, target_names: List[str]):
        """创建适合该模型的标准化器"""
        pass

    @abstractmethod
    def create_classifier(self, config):
        """创建分类器实例"""
        pass

    def train(self, classifier, X: np.ndarray, y: np.ndarray, target_names: List[str], progress_callback=None):
        """训练模型（可选的进度回调）
        
        Args:
            classifier: 分类器实例
            X: 特征数据
            y: 标签数据
            target_names: 目标列名列表
            progress_callback: 可选的进度回调函数
        """
        classifier.fit(X, y, target_names)
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/models/adapters/base.py
git commit -m "refactor: simplify BaseTrainerAdapter, remove stage methods"
```

---

## Task 3: 简化 XGBoostTrainerAdapter

**Files:**
- Modify: `backend/src/trade_alpha/models/adapters/xgboost/trainer_adapter.py`

- [ ] **Step 1: 更新适配器**

```python
from typing import List
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
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/models/adapters/xgboost/trainer_adapter.py
git commit -m "refactor: simplify XGBoostTrainerAdapter"
```

---

## Task 4: 简化 LSTMTrainerAdapter

**Files:**
- Modify: `backend/src/trade_alpha/models/adapters/lstm/trainer_adapter.py`

- [ ] **Step 1: 更新适配器**

```python
from typing import List, Optional, Callable
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

    def train(self, classifier, X: np.ndarray, y: np.ndarray, target_names: List[str], progress_callback: Optional[Callable] = None):
        """训练 LSTM 模型"""
        classifier.fit(X, y, target_names, progress_callback=progress_callback)
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/models/adapters/lstm/trainer_adapter.py
git commit -m "refactor: simplify LSTMTrainerAdapter"
```

---

## Task 5: 重构训练服务

**Files:**
- Modify: `backend/src/trade_alpha/models/training/trainer.py`

- [ ] **Step 1: 更新导入和进度回调**

在文件顶部添加导入：
```python
from .stages import Stage, DATA_LOAD, LABEL_CALC, TRAINING, EVALUATE, ANALYSIS, DONE
```

修改 `create_training` 函数中的进度更新逻辑：

原代码：
```python
total_stages = adapter.get_total_training_stages(config, num_years, num_targets)

async def update(stage_num: int, msg: str):
    if progress_callback:
        if asyncio.iscoroutinefunction(progress_callback):
            await progress_callback(stage_num / total_stages * 100, msg)
        else:
            progress_callback(stage_num / total_stages * 100, msg)
```

新代码：
```python
async def update_progress(stage: Stage, detail: str = ""):
    msg = f"{stage.message}{detail}" if detail else stage.message
    if progress_callback:
        if asyncio.iscoroutinefunction(progress_callback):
            await progress_callback(stage.pct, msg)
        else:
            progress_callback(stage.pct, msg)
```

- [ ] **Step 2: 更新各阶段的进度调用**

```python
# 数据加载
await update_progress(DATA_LOAD, f"{year}年")

# 标签计算
await update_progress(LABEL_CALC, f"{year}年")

# 训练
await update_progress(TRAINING)
classifier.fit(X, y, target_names)  # 直接调用，不再通过适配器

# 评估
await update_progress(EVALUATE)

# 分析
await update_progress(ANALYSIS)

# 完成
await update_progress(DONE)
```

- [ ] **Step 3: 移除不必要的变量**

删除：
- `total_stages`
- `stage_offset` 逻辑
- `format_progress` 导入（如不再使用）

- [ ] **Step 4: 运行测试验证**

```bash
cd backend && pytest tests/trade_alpha/unit/models/ -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/src/trade_alpha/models/training/trainer.py
git commit -m "refactor: use Stage constants in training service"
```

---

## Task 6: 清理 date_utils.py

**Files:**
- Modify: `backend/src/trade_alpha/utils/date_utils.py`

- [ ] **Step 1: 检查 format_progress 是否被使用**

```bash
cd backend/src/trade_alpha && grep -r "format_progress" --include="*.py"
```

如果不再使用，可删除该函数；否则保留。

- [ ] **Step 2: 提交（如有修改）**

```bash
git add backend/src/trade_alpha/utils/date_utils.py
git commit -m "refactor: remove unused format_progress function"
```

---

## 实施检查清单

- [ ] Task 1: 创建 stages.py
- [ ] Task 2: 简化 BaseTrainerAdapter
- [ ] Task 3: 简化 XGBoostTrainerAdapter
- [ ] Task 4: 简化 LSTMTrainerAdapter
- [ ] Task 5: 重构训练服务 + 测试通过
- [ ] Task 6: 清理 date_utils（如需要）
- [ ] 运行全量测试验证
- [ ] 推送代码
