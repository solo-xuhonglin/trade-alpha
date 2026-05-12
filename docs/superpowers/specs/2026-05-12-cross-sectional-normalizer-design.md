# 截面标准化设计文档

## 概述

为 `CrossSectionalNormalizer` 实现截面标准化逻辑。以时间截面为维度（按天分组），对同一日期下所有股票的指定特征字段进行缩尾和 Z-Score 标准化。

## 输入/输出

| 项目 | 说明 |
|------|------|
| 输入 | 多只股票某时间段的 Daily 数据 DataFrame |
| 输出 | 纯特征矩阵（仅含标准化后的字段），无 `ts_code`、`trade_date` 列 |
| 缺失值 | NaN 保持不变，仅用有值样本计算统计量 |

## 配置参数

```python
class CrossSectionalNormalizer(BaseNormalizer):
    def __init__(
        self,
        standardize_fields: list[str],               # 需要 Z-Score 标准化的字段
        winsorize_fields: Optional[list[str]] = None, # 需缩尾的字段（standardize_fields 的子集）
        winsorize_lower: float = 0.01,               # 下分位，默认 1%
        winsorize_upper: float = 0.95,               # 上分位，默认 95%
    ):
```

## 处理流程

```
输入 DataFrame(ts_code, trade_date, standardize_fields...)
         │
         ▼
按 trade_date 分组
         │
         ▼
对每一天的截面：
  1. winsorize 缩尾（如有配置）
     - 对每个需要缩尾的字段，用该天有值的样本计算下/上分位阈值
     - 超过下阈值的值缩尾到下阈值，超过上阈值的值缩尾到上阈值
     - NaN 保持不变，不参与分位计算
  2. Z-Score 标准化
     - 对 standardize_fields 中每个字段，用该天有值的样本计算均值、标准差
     - 每个值减去均值后除以标准差
     - NaN 保持不变，不参与均值/标准差计算
         │
         ▼
去除 ts_code, trade_date 列
         │
         ▼
输出纯特征 DataFrame（仅含 standardize_fields，无股票代码、无日期）
```

> **注**：XGBoost 可处理 NaN 值，输出保留 NaN 无需填充。

## 接口设计

### fit

```python
def fit(self, X: pd.DataFrame) -> CrossSectionalNormalizer:
```

校验输入，验证必需字段和配置。返回 self。（每组样本独立，fit 实际只做验证）

### transform

```python
def transform(self, X: pd.DataFrame) -> pd.DataFrame:
```

执行完整处理流程：分组 → 缩尾 → Z-Score → 去除标识列 → 返回。

### fit_transform

```python
def fit_transform(self, X: pd.DataFrame) -> pd.DataFrame:
```

等价于 `fit(X).transform(X)`。

## 依赖

- pandas, numpy（数据处理）
- 无外部机器学习依赖
