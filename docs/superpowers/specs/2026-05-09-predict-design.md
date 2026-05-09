# 预测层设计

## 概述

基于历史行情和技术指标数据，预测股票未来价格。支持多种预测模型，当前实现线性回归。

## 设计原则

沿用 `indicators` 模块的设计原则：**计算与存储分离**。

- **预测器文件** (e.g., `linear.py`): 纯预测逻辑，无副作用
- **服务文件** (`service.py`): 编排数据流，处理 I/O

## 目录结构

```
src/trade_alpha/
├── predict/
│   ├── __init__.py
│   ├── base.py          # 预测基类
│   ├── linear.py        # 线性回归实现
│   └── service.py      # 预测服务
```

## 模块说明

### 1. base.py - 预测基类

定义统一接口，所有预测器需实现：

```python
class BasePredictor(ABC):
    @abstractmethod
    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """预测

        Args:
            features: 特征矩阵 (n_samples, n_features)
            targets: 预测目标列表 (e.g., ["open", "close"])

        Returns:
            预测结果字典 {target: value}
        """
        pass
```

### 2. linear.py - 线性回归预测器

使用 scikit-learn 的 `LinearRegression` 实现多目标回归：

- 特征：历史行情 + 技术指标
- 目标：open, close, high, low
- 训练集：指定日期范围内的数据
- 预测：根据最后一天的特征预测下一天

### 3. service.py - 预测服务

```python
def predict(
    ts_code: str,
    targets: list[str] | None = None,
    model: str = "linear",
    start_date: str | None = None,
    end_date: str | None = None
) -> dict[str, float]:
    """预测并存储结果

    Args:
        ts_code: 股票代码
        targets: 预测目标，默认 ["open", "close", "high", "low"]
        model: 模型名称，默认 "linear"
        start_date: 训练数据开始日期 (YYYYMMDD)
        end_date: 训练数据结束日期 (YYYYMMDD)

    Returns:
        预测结果
    """
```

## 数据库设计

### predictions 集合

存储预测结果。

**索引**: `{ts_code: 1, trade_date: 1, model: 1}` 联合唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 预测日期 (YYYYMMDD) |
| `model` | string | 模型名称 (e.g., "linear") |
| `target_open` | float | 预测开盘价 |
| `target_close` | float | 预测收盘价 |
| `target_high` | float | 预测最高价 |
| `target_low` | float | 预测最低价 |

## 接口设计

```python
from trade_alpha.predict import predict

result = predict(
    ts_code="000001.SZ",
    targets=["open", "close", "high", "low"],
    model="linear",
    start_date="20230101",
    end_date="20240331"
)
# result = {"open": 10.5, "close": 10.8, "high": 11.0, "low": 10.3}
```

## 扩展性

后续可扩展的预测器：

- `rf.py` - 随机森林回归
- `lstm.py` - LSTM 神经网络
- `xgb.py` - XGBoost 回归

新增预测器只需：
1. 继承 `BasePredictor`
2. 在 `service.py` 中注册模型名称
