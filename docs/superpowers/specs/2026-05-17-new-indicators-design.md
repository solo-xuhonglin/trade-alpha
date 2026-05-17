# 新增技术指标设计

## 概述

新增 3 个技术指标（RSI、ATR、OBV）以丰富特征维度，提高模型的预测能力。

## 新增指标定义

| 指标 | 字段名 | 计算公式 | 说明 |
|------|--------|---------|------|
| **RSI** | `rsi_6`, `rsi_12` | RSI = 100 - 100/(1 + RS)，RS = 平均涨幅/平均跌幅 | 震荡指标，判断超买超卖 |
| **ATR** | `atr_14` | ATR = MA(TR, 14)，TR = max(H-L, \|H-C_prev\|, \|L-C_prev\|) | 波动率指标，衡量价格波动幅度 |
| **OBV** | `obv` | OBV_t = OBV_{t-1} + vol (涨) / -vol (跌) | 量能指标，反映资金流向 |

## 后端改动

### 新增文件

| 文件 | 职责 |
|------|------|
| `indicators/custom/rsi.py` | RSI 计算逻辑 |
| `indicators/custom/atr.py` | ATR 计算逻辑 |
| `indicators/custom/obv.py` | OBV 计算逻辑 |

每个文件导出 `calculate_xxx(df: pd.DataFrame) -> pd.DataFrame` 函数。

### 修改文件

| 文件 | 改动 |
|------|------|
| `indicators/custom/__init__.py` | 新增导出 `calculate_rsi`, `calculate_atr`, `calculate_obv` |
| `indicators/service.py` | `calculate_and_store_custom_indicators` 中调用新指标计算并写入数据库 |
| `config_service.py` | `DEFAULT_INDICATOR_FIELDS` 新增 4 个字段 |

## 数据库改动

`stock_daily` 集合新增字段（允许 null）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `rsi_6` | float | 6日 RSI（0-100） |
| `rsi_12` | float | 12日 RSI（0-100） |
| `atr_14` | float | 14日 ATR |
| `obv` | float | 累计 OBV 值 |

**空值处理**：直接保留 NaN，XGBoost 原生支持 NaN。

## 前端改动

### ModelsView.vue

`indicatorFields` 数组新增：
```typescript
'rsi_6', 'rsi_12', 'atr_14', 'obv'
```

## 改动范围汇总

| 文件 | 改动类型 |
|------|---------|
| `indicators/custom/rsi.py` | 新增 |
| `indicators/custom/atr.py` | 新增 |
| `indicators/custom/obv.py` | 新增 |
| `indicators/custom/__init__.py` | 修改 |
| `indicators/service.py` | 修改 |
| `config_service.py` | 修改 |
| `ModelsView.vue` | 修改 |
| `docs/data-processing.md` | 修改 |

## 参数选择

- RSI: 6日、12日（更敏感，适合短期）
- ATR: 14日（标准配置）
- OBV: 单值（累积）
