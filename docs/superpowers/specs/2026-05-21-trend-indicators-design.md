# 趋势指标设计方案

## 1. 概述

新增 4 类趋势指标，覆盖 3 个时间周期（5、10、20天），共 12 个指标字段。

**设计原则**：全部使用连续值，避免离散分类

## 2. 指标定义

| 指标类型 | 指标名 | 说明 | 取值范围 |
|---------|--------|------|---------|
| **均线排列** | `trend_arrangement_5/10/20` | 短期均线相对长期均线的偏离程度 | (-∞, +∞) |
| **均线斜率** | `trend_slope_5/10/20` | 均线变化速度 | (-∞, +∞) |
| **价量配合** | `trend_volume_5/10/20` | 涨跌幅与成交量的相关程度 | [-100, 100] |
| **趋势稳定** | `trend_stability_5/10/20` | 价格围绕均线的稳定程度 | [0, 100] |

## 3. 计算方法

### 3.1 trend_arrangement（均线排列程度）

衡量短期均线相对长期均线的偏离程度：

```
trend_arrangement_5 = (ma_5 / ma_20 - 1) * 100
trend_arrangement_10 = (ma_10 / ma_20 - 1) * 100
trend_arrangement_20 = (ma_20 / ma_60 - 1) * 100
```

- 正值：短期均线在长期均线上方（多头趋势）
- 负值：短期均线在长期均线下方（空头趋势）
- 值越大，多头排列越强

### 3.2 trend_slope（均线斜率）

计算均线相对前一天的变化率：

```
trend_slope_n = (ma_n - ma_n_prev) / ma_n_prev * 100
```

- 正值：均线上移（上升趋势）
- 负值：均线下移（下降趋势）

### 3.3 trend_volume（价量配合程度）

衡量涨跌幅与成交量的相关程度：

```
涨量相关 = corr(pct_chg, vol_ratio_n) for 周期内
trend_volume_n = 涨量相关 * 100
```

- 正值：价涨量增、价跌量减（趋势健康）
- 负值：价涨量减、价跌量增（趋势背离）

### 3.4 trend_stability（趋势稳定性）

衡量价格围绕均线的稳定程度：

```
稳定性 = 100 - 平均绝对偏差
平均绝对偏差 = mean(|close - ma_n| / ma_n) * 100
```

- 值越高，趋势越稳定
- 值越低，波动越大

## 4. 实施计划

### 4.1 新建文件

**文件**: `backend/src/trade_alpha/indicators/custom/trend.py`

```python
def calculate_trend(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    """Calculate trend indicators for given periods.

    Args:
        df: DataFrame with 'close', 'vol', 'pct_chg', and MA columns
        periods: List of periods (default [5, 10, 20])

    Returns:
        DataFrame with added trend_* columns
    """
```

### 4.2 更新 StockDaily 模型

**文件**: `backend/src/trade_alpha/dao/stock_daily.py`

添加 12 个字段：
- `trend_arrangement_5`, `trend_arrangement_10`, `trend_arrangement_20`
- `trend_slope_5`, `trend_slope_10`, `trend_slope_20`
- `trend_volume_5`, `trend_volume_10`, `trend_volume_20`
- `trend_stability_5`, `trend_stability_10`, `trend_stability_20`

### 4.3 更新指标服务

**文件**: `backend/src/trade_alpha/indicators/service.py`

1. 导入 `calculate_trend`
2. 在 `calculate_and_store_custom_indicators` 中调用

### 4.4 更新默认配置

**文件**: `backend/src/trade_alpha/predict/config_service.py`

从 `DEFAULT_INDICATOR_FIELDS` 移除 `atr_14`
添加 12 个 trend_* 字段

### 4.5 更新前端

**文件**: `frontend/src/api/dataAnalysis.ts`

从 `DEFAULT_FEATURE_FIELDS` 移除 `atr_14`
添加 12 个 trend_* 字段

### 4.6 更新文档

**文件**: `docs/features-indicators.md`

添加趋势指标说明

## 5. 指标依赖关系

计算顺序：
1. `pct_chg`（涨跌幅）
2. `ma_*`（均线）
3. `vol_ratio_*`（量比）
4. `trend_*`（趋势指标，依赖 ma_*, pct_chg, vol_ratio_*）

## 6. 与价格绝对值关系

所有趋势指标均不受价格绝对值影响：
- `trend_arrangement_*`：比值形式
- `trend_slope_*`：百分比变化率
- `trend_volume_*`：相关系数
- `trend_stability_*`：相对偏差百分比
