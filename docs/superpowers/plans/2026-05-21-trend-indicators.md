# Trend Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增12个趋势指标（4类×3周期），移除atr_14指标

**Architecture:** 基于现有指标框架，新增trend.py计算文件，更新StockDaily模型和配置服务

**Tech Stack:** Python pandas, Beanie ODM

---

## File Structure

```
backend/src/trade_alpha/
├── indicators/custom/
│   └── trend.py                    # 新增：趋势指标计算
├── indicators/custom/__init__.py   # 修改：导出calculate_trend
├── indicators/service.py            # 修改：集成趋势指标计算
├── dao/stock_daily.py              # 修改：添加12个趋势字段，移除atr_14
└── predict/config_service.py       # 修改：更新DEFAULT_INDICATOR_FIELDS

frontend/src/api/
└── dataAnalysis.ts                 # 修改：更新DEFAULT_FEATURE_FIELDS

docs/
└── features-indicators.md          # 修改：添加趋势指标文档
```

---

## Task 1: 创建趋势指标计算模块

**Files:**
- Create: `backend/src/trade_alpha/indicators/custom/trend.py`
- Test: `backend/tests/trade_alpha/indicators/test_trend.py`

- [ ] **Step 1: 编写测试文件**

```python
"""Tests for trend indicators."""
import pandas as pd
import numpy as np
import pytest
from trade_alpha.indicators.custom.trend import calculate_trend


def create_test_df():
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(100) * 2)
    vol = np.random.randint(1000000, 5000000, 100)
    pct_chg = pd.Series(close).pct_change() * 100
    
    df = pd.DataFrame({
        'trade_date': [d.strftime('%Y%m%d') for d in dates],
        'open': close * 0.99,
        'high': close * 1.02,
        'low': close * 0.98,
        'close': close,
        'vol': vol,
        'pct_chg': pct_chg,
    })
    
    for period in [5, 10, 20, 60]:
        df[f'ma_{period}'] = df['close'].rolling(period).mean()
    for period in [5, 10, 20, 60]:
        vol_ma = df['vol'].rolling(period).mean()
        df[f'vol_ratio_{period}'] = df['vol'] / vol_ma
    
    return df


def test_trend_arrangement():
    df = create_test_df()
    result = calculate_trend(df)
    
    assert 'trend_arrangement_5' in result.columns
    assert 'trend_arrangement_10' in result.columns
    assert 'trend_arrangement_20' in result.columns
    assert len(result) == len(df)


def test_trend_slope():
    df = create_test_df()
    result = calculate_trend(df)
    
    assert 'trend_slope_5' in result.columns
    assert 'trend_slope_10' in result.columns
    assert 'trend_slope_20' in result.columns


def test_trend_volume():
    df = create_test_df()
    result = calculate_trend(df)
    
    assert 'trend_volume_5' in result.columns
    assert 'trend_volume_10' in result.columns
    assert 'trend_volume_20' in result.columns


def test_trend_stability():
    df = create_test_df()
    result = calculate_trend(df)
    
    assert 'trend_stability_5' in result.columns
    assert 'trend_stability_10' in result.columns
    assert 'trend_stability_20' in result.columns
    assert result['trend_stability_5'].min() >= 0
    assert result['trend_stability_5'].max() <= 100
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/indicators/test_trend.py -v
```
Expected: FAIL - module 'trade_alpha.indicators.custom.trend' not found

- [ ] **Step 3: 编写趋势指标计算代码**

```python
"""Trend indicators calculation module."""
import pandas as pd
import numpy as np
from typing import List


def calculate_trend(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    """Calculate trend indicators for given periods.

    Args:
        df: DataFrame with 'close', 'vol', 'pct_chg', and MA columns
        periods: List of periods (default [5, 10, 20])

    Returns:
        DataFrame with added trend_* columns
    """
    if periods is None:
        periods = [5, 10, 20]
    
    result = df.copy()
    
    for period in periods:
        _calculate_arrangement(result, period)
        _calculate_slope(result, period)
        _calculate_volume(result, period)
        _calculate_stability(result, period)
    
    return result


def _calculate_arrangement(df: pd.DataFrame, period: int) -> None:
    """Calculate trend arrangement: short MA relative to long MA."""
    if period == 5:
        long_ma = df['ma_20']
    elif period == 10:
        long_ma = df['ma_20']
    else:  # period == 20
        long_ma = df['ma_60']
    
    short_ma = df[f'ma_{period}']
    df[f'trend_arrangement_{period}'] = (short_ma / long_ma - 1) * 100


def _calculate_slope(df: pd.DataFrame, period: int) -> None:
    """Calculate trend slope: MA change rate."""
    ma_col = f'ma_{period}'
    prev_ma = df[ma_col].shift(1)
    df[f'trend_slope_{period}'] = ((df[ma_col] - prev_ma) / prev_ma * 100)


def _calculate_volume(df: pd.DataFrame, period: int) -> None:
    """Calculate trend volume: correlation between pct_chg and vol_ratio."""
    vol_ratio_col = f'vol_ratio_{period}'
    
    rolling_corr = df['pct_chg'].rolling(window=period).corr(df[vol_ratio_col])
    df[f'trend_volume_{period}'] = rolling_corr * 100


def _calculate_stability(df: pd.DataFrame, period: int) -> None:
    """Calculate trend stability: inverse of mean absolute deviation."""
    ma_col = f'ma_{period}'
    mad = (df['close'] - df[ma_col]).abs() / df[ma_col] * 100
    rolling_mad = mad.rolling(window=period).mean()
    df[f'trend_stability_{period}'] = 100 - rolling_mad
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/trade_alpha/indicators/test_trend.py -v
```
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add backend/src/trade_alpha/indicators/custom/trend.py backend/tests/trade_alpha/indicators/test_trend.py
git commit -m "feat: add trend indicators calculation module"
```

---

## Task 2: 更新 StockDaily 模型

**Files:**
- Modify: `backend/src/trade_alpha/dao/stock_daily.py:53-66`

- [ ] **Step 1: 更新模型，移除atr_14，添加12个趋势字段**

```python
# 移除这一行
atr_14: Optional[float] = None

# 添加12个趋势字段（在rsi_12之后）
trend_arrangement_5: Optional[float] = None
trend_arrangement_10: Optional[float] = None
trend_arrangement_20: Optional[float] = None
trend_slope_5: Optional[float] = None
trend_slope_10: Optional[float] = None
trend_slope_20: Optional[float] = None
trend_volume_5: Optional[float] = None
trend_volume_10: Optional[float] = None
trend_volume_20: Optional[float] = None
trend_stability_5: Optional[float] = None
trend_stability_10: Optional[float] = None
trend_stability_20: Optional[float] = None
```

- [ ] **Step 2: 验证语法**

```bash
cd d:\projects\trade-alpha\backend
python -m py_compile src/trade_alpha/dao/stock_daily.py
```
Expected: 无错误

- [ ] **Step 3: 提交代码**

```bash
git add backend/src/trade_alpha/dao/stock_daily.py
git commit -m "feat: add 12 trend indicator fields to StockDaily model"
```

---

## Task 3: 更新指标服务

**Files:**
- Modify: `backend/src/trade_alpha/indicators/custom/__init__.py`
- Modify: `backend/src/trade_alpha/indicators/service.py:100-187`

- [ ] **Step 1: 更新 __init__.py 导出**

```python
# 在 __all__ 中添加
"calculate_trend",
```

- [ ] **Step 2: 更新 service.py 集成趋势指标**

```python
# 在 imports 中添加
from trade_alpha.indicators.custom import (
    calculate_pct_chg,
    calculate_bias,
    calculate_close_position,
    calculate_vol_ratio,
    calculate_kdj,
    calculate_boll,
    calculate_rsi,
    calculate_atr,
    calculate_obv,
    calculate_candle_features,
    calculate_trend,  # 新增
)

# 在 calculate_and_store_custom_indicators 函数中
# 在 df = calculate_obv(df) 之后添加
df = calculate_trend(df)

# 在 update_data 中添加12个趋势字段
"trend_arrangement_5": row.get("trend_arrangement_5"),
"trend_arrangement_10": row.get("trend_arrangement_10"),
"trend_arrangement_20": row.get("trend_arrangement_20"),
"trend_slope_5": row.get("trend_slope_5"),
"trend_slope_10": row.get("trend_slope_10"),
"trend_slope_20": row.get("trend_slope_20"),
"trend_volume_5": row.get("trend_volume_5"),
"trend_volume_10": row.get("trend_volume_10"),
"trend_volume_20": row.get("trend_volume_20"),
"trend_stability_5": row.get("trend_stability_5"),
"trend_stability_10": row.get("trend_stability_10"),
"trend_stability_20": row.get("trend_stability_20"),
```

- [ ] **Step 3: 验证语法**

```bash
python -m py_compile src/trade_alpha/indicators/service.py
python -m py_compile src/trade_alpha/indicators/custom/__init__.py
```

- [ ] **Step 4: 提交代码**

```bash
git add backend/src/trade_alpha/indicators/custom/__init__.py backend/src/trade_alpha/indicators/service.py
git commit -m "feat: integrate trend indicators into indicator service"
```

---

## Task 4: 更新模型配置

**Files:**
- Modify: `backend/src/trade_alpha/predict/config_service.py:20-30`

- [ ] **Step 1: 更新 DEFAULT_INDICATOR_FIELDS**

移除 `atr_14`，添加12个趋势字段：

```python
DEFAULT_INDICATOR_FIELDS = [
    "ma_5", "ma_10", "ma_20", "ma_60",
    "macd", "macd_signal", "macd_hist",
    "pct_chg",
    "bias_5", "bias_10", "bias_20", "bias_60",
    "close_position_5", "close_position_10", "close_position_20", "close_position_60",
    "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60",
    "kdj_k", "kdj_d", "kdj_j",
    "boll_upper", "boll_middle", "boll_lower", "boll_position",
    "rsi_6", "rsi_12",
    "trend_arrangement_5", "trend_arrangement_10", "trend_arrangement_20",
    "trend_slope_5", "trend_slope_10", "trend_slope_20",
    "trend_volume_5", "trend_volume_10", "trend_volume_20",
    "trend_stability_5", "trend_stability_10", "trend_stability_20",
    "obv"
]
```

- [ ] **Step 2: 验证语法**

```bash
python -m py_compile src/trade_alpha/predict/config_service.py
```

- [ ] **Step 3: 提交代码**

```bash
git add backend/src/trade_alpha/predict/config_service.py
git commit -m "feat: update default indicator fields with trend indicators, remove atr_14"
```

---

## Task 5: 更新前端配置

**Files:**
- Modify: `frontend/src/api/dataAnalysis.ts`

- [ ] **Step 1: 更新 DEFAULT_FEATURE_FIELDS**

```typescript
export const DEFAULT_FEATURE_FIELDS = [
  "ma_5", "ma_10", "ma_20", "ma_60",
  "macd", "macd_signal", "macd_hist",
  "pct_chg",
  "bias_5", "bias_10", "bias_20", "bias_60",
  "close_position_5", "close_position_10", "close_position_20", "close_position_60",
  "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60",
  "kdj_k", "kdj_d", "kdj_j",
  "boll_upper", "boll_middle", "boll_lower", "boll_position",
  "rsi_6", "rsi_12",
  "trend_arrangement_5", "trend_arrangement_10", "trend_arrangement_20",
  "trend_slope_5", "trend_slope_10", "trend_slope_20",
  "trend_volume_5", "trend_volume_10", "trend_volume_20",
  "trend_stability_5", "trend_stability_10", "trend_stability_20",
  "obv"
];
```

- [ ] **Step 2: 提交代码**

```bash
git add frontend/src/api/dataAnalysis.ts
git commit -m "feat: update frontend default feature fields with trend indicators, remove atr_14"
```

---

## Task 6: 更新文档

**Files:**
- Modify: `docs/features-indicators.md`

- [ ] **Step 1: 在文档中添加趋势指标章节**

在 "K线形态指标" 章节之后添加：

```markdown
#### 趋势指标

| 字段名 | 说明 | 计算周期 |
|--------|------|---------|
| trend_arrangement_5 | 5日均线相对20日均线的偏离程度 | 5天 |
| trend_arrangement_10 | 10日均线相对20日均线的偏离程度 | 10天 |
| trend_arrangement_20 | 20日均线相对60日均线的偏离程度 | 20天 |
| trend_slope_5 | 5日均线斜率 | 5天 |
| trend_slope_10 | 10日均线斜率 | 10天 |
| trend_slope_20 | 20日均线斜率 | 20天 |
| trend_volume_5 | 5日价量相关程度 | 5天 |
| trend_volume_10 | 10日价量相关程度 | 10天 |
| trend_volume_20 | 20日价量相关程度 | 20天 |
| trend_stability_5 | 5日趋势稳定程度 | 5天 |
| trend_stability_10 | 10日趋势稳定程度 | 10天 |
| trend_stability_20 | 20日趋势稳定程度 | 20天 |

**计算方法**：
- trend_arrangement_n = (ma_short / ma_long - 1) * 100
- trend_slope_n = (ma_n - ma_n_prev) / ma_n_prev * 100
- trend_volume_n = corr(pct_chg, vol_ratio_n) * 100
- trend_stability_n = 100 - mean(|close - ma_n| / ma_n) * 100
```

同时更新 DEFAULT_INDICATOR_FIELDS 部分，移除 `atr_14`，添加12个趋势字段。

- [ ] **Step 2: 提交代码**

```bash
git add docs/features-indicators.md
git commit -m "docs: add trend indicators documentation, remove atr_14"
```

---

## Task 7: 集成测试

**Files:**
- Test: 使用比亚迪(002594.SZ)验证指标计算

- [ ] **Step 1: 运行趋势指标计算测试**

```bash
cd d:\projects\trade-alpha\backend
python -c "
import asyncio
from trade_alpha.dao import init_db, StockList
from trade_alpha.indicators.service import calculate_all_indicators

async def test():
    await init_db()
    stock = await StockList.find_one(StockList.ts_code == '002594.SZ')
    if stock:
        await calculate_all_indicators('002594.SZ')
        print('Trend indicators calculated successfully')
    else:
        print('Test stock not found')

asyncio.run(test())
"
```

- [ ] **Step 2: 验证数据库字段**

```bash
python -c "
import asyncio
from trade_alpha.dao import init_db, StockDaily

async def check():
    await init_db()
    record = await StockDaily.find_one(StockDaily.ts_code == '002594.SZ', sort='-trade_date')
    if record:
        print('trend_arrangement_5:', record.trend_arrangement_5)
        print('trend_slope_5:', record.trend_slope_5)
        print('trend_volume_5:', record.trend_volume_5)
        print('trend_stability_5:', record.trend_stability_5)
        print('atr_14:', record.atr_14)  # 应该为 None
    else:
        print('No records found')

asyncio.run(check())
"
```

---

## Task 8: 推送所有更改

- [ ] **Step 1: 推送代码**

```bash
git push
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | 创建趋势指标计算模块 | trend.py, test_trend.py |
| 2 | 更新 StockDaily 模型 | stock_daily.py |
| 3 | 更新指标服务 | service.py, __init__.py |
| 4 | 更新模型配置 | config_service.py |
| 5 | 更新前端配置 | dataAnalysis.ts |
| 6 | 更新文档 | features-indicators.md |
| 7 | 集成测试 | - |
| 8 | 推送代码 | - |
