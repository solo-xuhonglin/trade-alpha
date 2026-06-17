# Three-Phase Direction: up / flat / down (with detailed phase display)

## 1. Background

6 个离散阶段（crash/decline/recovery/sideways/uptrend/normal）导致策略层需要复杂分支。
实际只需要 3 个方向，附加详细阶段仅用于图表可视化。

## 2. Output Fields

| 字段 | 用途 | 值域 |
|------|------|------|
| `market_phase` | 策略消费的3阶段 | `"up"` / `"flat"` / `"down"` |
| `market_phase_detail` | 图表展示的详细阶段 | `"crash"` / `"decline"` / `"sideways"` / `"uptrend"` / `"normal"` |

## 3. 3-Phase with Hysteresis

### 3.1 迟滞状态机

```
当前 down（来自 crash/decline 检测）:
  dr_5d > -0.01 → flat    (退出下跌的条件比进入更宽松)
  否则          保持 down

当前 flat:
  dr_5d > 0.02 × scale → up    (牛市 scale 放大，需更强信号)
  否则          保持 flat

当前 up:
  dr_5d < 0.01 → flat    (退出上涨的条件比进入更宽松)
  否则          保持 up
```

### 3.2 Scale 计算

复用原有 drawup/drawdown 缩放：
- 牛市（drawup > 2%）: scale = min(3.0, 1 + drawup × 5)
- 熊市（drawdown < -3%）: scale = max(0.5, 1 + drawdown × 2)
- 正常: scale = 1.0

### 3.3 验证结果（725天）

| 阶段 | 天数 | 占比 | 平均持续 | 过转/百天 | 持久度 |
|------|------|------|---------|:--------:|:-----:|
| up | 99 | 13.6% | 6天 | - | - |
| flat | 568 | 78.2% | 19天 | 7.9 | 92/100 |
| down | 59 | 8.1% | 5天 | - | - |

## 4. Detailed Phase（Stateless，只用于展示）

```
crash:    dr_5d < crash_th
decline:  dr_5d < decline_bar AND low_5d > 0
sideways: abs(cum_10d) < 0.02 AND drawup < 0.15
uptrend:  dr_5d > 0.02 AND drawup > 0.10
normal:   全部剩余
```

## 5. Multipliers

| 3阶段 | pos_mult | buy_mult | 策略含义 |
|-------|----------|----------|---------|
| up | 1.0 | 1.0 | 满仓追涨趋势 |
| flat | 1.0 | 1.0 | 满仓均值回归 |
| down | 0.5 | 1.0 | 轻仓等反转 |

## 6. API 和存储

- `market_phase` / `market_phase_detail` 都存储在 `ExecutionDailySnapshot`
- `MarketDataEmbed` 供 strategy 层读取 `market_phase`
- 前端图表底色用 `market_phase_detail`（5种颜色）
- 前端 tooltip 显示两行："市场阶段: 上涨" / "详细阶段: 上涨趋势"

## 7. 文件变更

| 文件 | 变更 |
|------|------|
| `execution/scoring.py` | 替换6阶段为3迟滞 + detail |
| `schemas.py` | MarketDataEmbed 加 market_phase_detail |
| `dao/execution_daily_snapshot.py` | 加 market_phase_detail |
| `execution/backtest_service.py` | API 返回 market_phase_detail |
| `OverviewChart.vue` | chart 用 detail 底色，tooltip 显示两行 |
| `BacktestRecordsView.vue` | 数据映射加 market_phase_detail |
