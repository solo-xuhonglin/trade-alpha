# Three-Phase Direction: up / flat / down

## 1. 背景

6 个离散阶段（crash/decline/recovery/sideways/uptrend/normal）导致策略层需要复杂分支。
实际只需要 3 个方向，配合迟滞（hysteresis）达到与 6 阶段持久的同稳定性。

## 2. 迟滞状态机

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

### Scale 计算

复用原有 drawup/drawdown 缩放：
- 牛市（drawup > 2%）: scale = min(3.0, 1 + drawup × 5)
- 熊市（drawdown < -3%）: scale = max(0.5, 1 + drawdown × 2)
- 正常: scale = 1.0

## 3. 验证结果（725天）

| 阶段 | 天数 | 占比 | 平均持续 | 过转/百天 | 持久度 |
|------|------|------|---------|:--------:|:-----:|
| up | 99 | 13.6% | 6天 | - | - |
| flat | 568 | 78.2% | 19天 | 7.9 | 92/100 |
| down | 59 | 8.1% | 5天 | - | - |

## 4. Multipliers

| 阶段 | pos_mult | buy_mult | 策略含义 |
|------|----------|----------|---------|
| up | 1.0 | 1.0 | 满仓追涨趋势 |
| flat | 1.0 | 1.0 | 满仓均值回归 |
| down | 0.5 | 1.0 | 轻仓等反转 |

## 5. API 和存储

- `market_phase` 存储在 `ExecutionDailySnapshot`，通过 API 返回
- `MarketDataEmbed` 供 strategy 层读取 `market_phase`
- 前端图表底色：down=红色, up=蓝色, flat=透明
