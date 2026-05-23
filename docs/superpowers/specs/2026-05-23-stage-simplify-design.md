# 训练阶段简化设计

## 背景

当前训练流程使用复杂的 stage 计数机制，各模型适配器需要计算总阶段数，导致代码冗余且难以维护。

## 设计目标

简化训练进度跟踪机制，使用常量替代动态计算。

## 方案

### 定义阶段常量

```python
# trade_alpha/models/training/stages.py

class Stage:
    DATA_LOAD = ("正在加载数据...", 0, 30)
    LABEL_CALC = ("正在计算标签...", 30, 40)
    NORMALIZE = ("正在标准化数据...", 40, 50)
    TRAINING = ("正在训练模型...", 50, 85)
    EVALUATE = ("正在评估模型...", 85, 95)
    ANALYSIS = ("正在分析数据...", 95, 98)
    DONE = ("完成", 100, 100)
```

元组格式：`(描述文本, 起始百分比, 结束百分比)`

### 进度更新回调

```python
def update_progress(stage: tuple, detail: str = ""):
    """更新进度

    Args:
        stage: Stage 常量，如 Stage.DATA_LOAD
        detail: 附加详情，如 "2024年" 或 "Fold 1/5"
    """
    msg = f"{stage[0]}{detail}" if detail else stage[0]
    pct = stage[1]  # 使用起始百分比
    # 更新任务进度
```

### 使用示例

```python
# 训练流程中
await update_progress(Stage.DATA_LOAD, "2024年")
# 显示：正在加载数据... 2024年，进度：0%

await update_progress(Stage.TRAINING)
# 显示：正在训练模型...，进度：50%
```

## 修改文件

| 文件 | 修改内容 |
|------|---------|
| `models/training/stages.py` | 新建，定义 Stage 常量 |
| `models/adapters/base.py` | 移除 `get_total_training_stages` 方法 |
| `models/adapters/xgboost/trainer_adapter.py` | 移除 stage 相关方法 |
| `models/adapters/lstm/trainer_adapter.py` | 移除 stage 相关方法 |
| `models/training/trainer.py` | 使用 Stage 常量简化进度更新 |
| `utils/date_utils.py` | 可移除 `format_progress` 函数（如不再使用） |

## 阶段占比

| 阶段 | 占比 |
|------|------|
| 数据加载 | 0-30% |
| 标签计算 | 30-40% |
| 标准化 | 40-50% |
| 训练 | 50-85% |
| 评估 | 85-95% |
| 分析 | 95-98% |
| 完成 | 100% |
