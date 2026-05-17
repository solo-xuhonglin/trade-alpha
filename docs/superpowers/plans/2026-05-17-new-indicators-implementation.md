# 新增技术指标实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 RSI、ATR、OBV 三个技术指标的计算逻辑，集成到指标计算管道，并在前端配置界面暴露相关字段选项。

**Architecture:** 每个指标独立实现为一个计算函数，接受 pandas DataFrame 输入，返回带计算结果的 DataFrame。在 `calculate_all_indicators` 中统一调用三个新指标的计算和存储。

**Tech Stack:** Python (pandas), MongoDB, Vue 3 (Vuetify)

---

## 文件变更概览

| 文件 | 改动类型 |
|------|---------|
| `indicators/custom/rsi.py` | 新增 |
| `indicators/custom/atr.py` | 新增 |
| `indicators/custom/obv.py` | 新增 |
| `indicators/custom/__init__.py` | 修改 |
| `indicators/service.py` | 修改 |
| `config_service.py` | 修改 |
| `ModelsView.vue` | 修改 |

---

## Task 1: 实现 RSI 指标计算

**Files:**
- Create: `backend/src/trade_alpha/indicators/custom/rsi.py`
- Modify: `backend/src/trade_alpha/indicators/custom/__init__.py`
- Modify: `backend/src/trade_alpha/indicators/service.py`

- [ ] **Step 1: 创建 `indicators/custom/rsi.py`**

```python
"""RSI (Relative Strength Index) calculation module."""

import pandas as pd
import numpy as np


def calculate_rsi(df: pd.DataFrame, periods: list[int] | None = None) -> pd.DataFrame:
    """Calculate RSI for given periods.

    RSI = 100 - 100/(1 + RS)
    RS = average_gain / average_loss

    Args:
        df: DataFrame with 'close' and 'pct_chg' columns
        periods: List of RSI periods (default [6, 12])

    Returns:
        DataFrame with new RSI columns added
    """
    if periods is None:
        periods = [6, 12]

    df = df.copy()

    for period in periods:
        col_name = f"rsi_{period}"

        delta = df["pct_chg"].copy()
        delta = delta.replace(0, np.nan).fillna(0)

        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        df[col_name] = 100 - (100 / (1 + rs))

        df.loc[avg_loss == 0, col_name] = 100

    return df
```

- [ ] **Step 2: 更新 `indicators/custom/__init__.py`**

在 `__all__` 列表中添加：
```python
"calculate_rsi",
```

- [ ] **Step 3: 在 `indicators/service.py` 中集成 RSI 计算**

在 `calculate_and_store_custom_indicators` 函数的 df 初始化后添加：
```python
df = calculate_rsi(df)
```

在 update_data 字典中添加：
```python
"rsi_6": row.get("rsi_6"),
"rsi_12": row.get("rsi_12"),
```

- [ ] **Step 4: 提交**

```bash
git add indicators/custom/rsi.py indicators/custom/__init__.py indicators/service.py
git commit -m "feat: add RSI indicator calculation (rsi_6, rsi_12)"
```

---

## Task 2: 实现 ATR 指标计算

**Files:**
- Create: `backend/src/trade_alpha/indicators/custom/atr.py`
- Modify: `backend/src/trade_alpha/indicators/custom/__init__.py`
- Modify: `backend/src/trade_alpha/indicators/service.py`

- [ ] **Step 1: 创建 `indicators/custom/atr.py`**

```python
"""ATR (Average True Range) calculation module."""

import pandas as pd
import numpy as np


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate ATR for given period.

    True Range (TR) = max(H - L, |H - C_prev|, |L - C_prev|)
    ATR = MA(TR, period)

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ATR period (default 14)

    Returns:
        DataFrame with new atr_14 column added
    """
    df = df.copy()

    prev_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    df["atr_14"] = tr.rolling(window=period, min_periods=period).mean()

    return df
```

- [ ] **Step 2: 更新 `indicators/custom/__init__.py`**

在 `__all__` 列表中添加：
```python
"calculate_atr",
```

- [ ] **Step 3: 在 `indicators/service.py` 中集成 ATR 计算**

在 `calculate_and_store_custom_indicators` 函数的 df 初始化后添加：
```python
df = calculate_atr(df)
```

在 update_data 字典中添加：
```python
"atr_14": row.get("atr_14"),
```

- [ ] **Step 4: 提交**

```bash
git add indicators/custom/atr.py indicators/custom/__init__.py indicators/service.py
git commit -m "feat: add ATR indicator calculation (atr_14)"
```

---

## Task 3: 实现 OBV 指标计算

**Files:**
- Create: `backend/src/trade_alpha/indicators/custom/obv.py`
- Modify: `backend/src/trade_alpha/indicators/custom/__init__.py`
- Modify: `backend/src/trade_alpha/indicators/service.py`

- [ ] **Step 1: 创建 `indicators/custom/obv.py`**

```python
"""OBV (On Balance Volume) calculation module."""

import pandas as pd


def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate OBV (On Balance Volume).

    OBV_t = OBV_{t-1} + vol_t (if close_t > close_{t-1})
    OBV_t = OBV_{t-1} - vol_t (if close_t < close_{t-1})
    OBV_t = OBV_{t-1} (if close_t == close_{t-1})

    Args:
        df: DataFrame with 'close' and 'vol' columns

    Returns:
        DataFrame with new obv column added
    """
    df = df.copy()

    close_diff = df["close"].diff()

    obv = pd.Series(index=df.index, dtype=float)
    obv.iloc[0] = df["vol"].iloc[0] if df["vol"].iloc[0] > 0 else 0

    for i in range(1, len(df)):
        if close_diff.iloc[i] > 0:
            obv.iloc[i] = obv.iloc[i - 1] + df["vol"].iloc[i]
        elif close_diff.iloc[i] < 0:
            obv.iloc[i] = obv.iloc[i - 1] - df["vol"].iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i - 1]

    df["obv"] = obv

    return df
```

- [ ] **Step 2: 更新 `indicators/custom/__init__.py`**

在 `__all__` 列表中添加：
```python
"calculate_obv",
```

- [ ] **Step 3: 在 `indicators/service.py` 中集成 OBV 计算**

在 `calculate_and_store_custom_indicators` 函数的 df 初始化后添加：
```python
df = calculate_obv(df)
```

在 update_data 字典中添加：
```python
"obv": row.get("obv"),
```

- [ ] **Step 4: 提交**

```bash
git add indicators/custom/obv.py indicators/custom/__init__.py indicators/service.py
git commit -m "feat: add OBV indicator calculation"
```

---

## Task 4: 更新默认特征列表和前端配置

**Files:**
- Modify: `backend/src/trade_alpha/predict/config_service.py`
- Modify: `frontend/src/views/ModelsView.vue`

- [ ] **Step 1: 更新 `config_service.py` 的 `DEFAULT_INDICATOR_FIELDS`**

在列表末尾添加 4 个新字段：
```python
"rsi_6", "rsi_12", "atr_14", "obv"
```

完整列表应为：
```python
DEFAULT_INDICATOR_FIELDS = [
    "ma_5", "ma_10", "ma_20", "ma_60",
    "macd", "macd_signal", "macd_hist",
    "pct_chg",
    "bias_5", "bias_10", "bias_20", "bias_60",
    "close_pct_rank_5", "close_pct_rank_10", "close_pct_rank_20", "close_pct_rank_60",
    "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60",
    "kdj_k", "kdj_d", "kdj_j",
    "boll_upper", "boll_middle", "boll_lower",
    "rsi_6", "rsi_12", "atr_14", "obv",
]
```

- [ ] **Step 2: 更新 `ModelsView.vue` 的 `indicatorFields` 数组**

在数组末尾添加 4 个新字段：
```typescript
'rsi_6', 'rsi_12', 'atr_14', 'obv'
```

完整数组应为：
```typescript
const indicatorFields = [
  'ma_5', 'ma_10', 'ma_20', 'ma_60',
  'macd', 'macd_signal', 'macd_hist',
  'pct_chg',
  'bias_5', 'bias_10', 'bias_20', 'bias_60',
  'close_pct_rank_5', 'close_pct_rank_10', 'close_pct_rank_20', 'close_pct_rank_60',
  'vol_ratio_5', 'vol_ratio_10', 'vol_ratio_20', 'vol_ratio_60',
  'kdj_k', 'kdj_d', 'kdj_j',
  'boll_upper', 'boll_middle', 'boll_lower',
  'rsi_6', 'rsi_12', 'atr_14', 'obv',
]
```

- [ ] **Step 3: 提交**

```bash
git add config_service.py ModelsView.vue
git commit -m "feat: add new indicator fields to default config and frontend"
```

---

## Task 5: 验证和测试

- [ ] **Step 1: 测试 RSI 计算**

```bash
cd backend
python -c "
import pandas as pd
import numpy as np
from trade_alpha.indicators.custom.rsi import calculate_rsi

# 创建测试数据
dates = pd.date_range('2024-01-01', periods=20)
df = pd.DataFrame({
    'close': np.random.randn(20).cumsum() + 100,
    'pct_chg': np.random.randn(20) * 2,
    'trade_date': [d.strftime('%Y%m%d') for d in dates]
})
df.loc[0, 'pct_chg'] = 0

result = calculate_rsi(df)
print('RSI_6 sample:', result['rsi_6'].tail(5).values)
print('RSI_12 sample:', result['rsi_12'].tail(5).values)
"
```

预期输出：RSI 值在 0-100 之间

- [ ] **Step 2: 测试 ATR 计算**

```bash
cd backend
python -c "
import pandas as pd
import numpy as np
from trade_alpha.indicators.custom.atr import calculate_atr

# 创建测试数据
df = pd.DataFrame({
    'high': 100 + np.random.randn(20).cumsum(),
    'low': 99 + np.random.randn(20).cumsum(),
    'close': 99.5 + np.random.randn(20).cumsum(),
})
df['high'] = df[['high', 'close']].max(axis=1) + np.abs(np.random.randn(20) * 0.5)
df['low'] = df[['low', 'close']].min(axis=1) - np.abs(np.random.randn(20) * 0.5)

result = calculate_atr(df)
print('ATR_14 sample:', result['atr_14'].tail(5).values)
"
```

预期输出：ATR 值应大于 0

- [ ] **Step 3: 测试 OBV 计算**

```bash
cd backend
python -c "
import pandas as pd
import numpy as np
from trade_alpha.indicators.custom.obv import calculate_obv

# 创建测试数据
df = pd.DataFrame({
    'close': [100, 102, 101, 103, 102],
    'vol': [1000, 1200, 800, 1500, 900],
})

result = calculate_obv(df)
print('OBV values:', result['obv'].values)
print('OBV should increase when price up, decrease when price down')
"
```

预期输出：OBV 应随价格上涨而增加

- [ ] **Step 4: 验证前端 TypeScript 编译**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期输出：无编译错误

---

## Task 6: 更新文档

**Files:**
- Modify: `docs/data-processing.md`

- [ ] **Step 1: 更新 `docs/data-processing.md`**

在"二、技术指标计算"章节中，新增指标列表：

```markdown
### 2.1 指标列表（共 30 个）

| 类别 | 指标 | 字段名 | 计算方式 |
|------|------|--------|----------|
| ... | ... | ... | ... |
| 震荡类 | RSI | `rsi_6`, `rsi_12` | RSI = 100 - 100/(1 + RS) |
| 波动率类 | ATR | `atr_14` | ATR = MA(TR, 14) |
| 量能类 | OBV | `obv` | OBV_t = OBV_{t-1} ± vol |
```

- [ ] **Step 2: 提交文档更新**

```bash
git add docs/data-processing.md
git commit -m "docs: update indicator list in data-processing.md"
```

---

## 验证清单

- [ ] RSI 计算正确（值在 0-100 范围）
- [ ] ATR 计算正确（值大于 0）
- [ ] OBV 计算正确（随价格涨跌增减）
- [ ] `calculate_all_indicators` 成功调用所有新指标
- [ ] 前端 `indicatorFields` 包含新字段
- [ ] `DEFAULT_INDICATOR_FIELDS` 包含新字段
- [ ] TypeScript 编译通过
- [ ] 文档已更新
