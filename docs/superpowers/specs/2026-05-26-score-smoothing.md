# 预测信号平滑 — 降低多股票排名波动

## 问题

多股票排名模式下，每日预测分数波动剧烈，导致：

- 排名在阈值边缘反复跳动，持仓股票频繁换手
- 震荡市中表现为"高买低卖"，产生高额交易成本
- 策略信号的信噪比低，部分交易由噪声驱动

## 方案

引入两个独立的可插拔方法，在 pipeline 主循环中按序调用，不增加 `run_backtest()` 的复杂度。

```
原始分数 → _smooth_scores() → 平滑分数 → _record_ranks() → 排名回写 → scored → make_decisions()
```

## 架构

只改 1 个文件：[pipeline.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/pipeline.py)

### 数据流

所有改动集中在 `run_backtest()` 的"Step 2 → Step 3"之间，分两步：

```
② Predict T+1 → pred_results{ts_code: {score, up_prob_3d, ...}}
      ↓
  [新增] _smooth_scores(pred_results)        ← pred_results.score 原地替换为平滑值
      ↓
  [新增] _record_ranks(scored, pred_results)  ← 排序后回写 rank 到 pred_results
      ↓
③ make_decisions(scored, ...)
```

### 1. 分数平滑 `_smooth_scores()`

```python
def _smooth_scores(self, pred_results: Dict[str, Dict]) -> None:
    """Apply EWMA smoothing to scores in-place on pred_results.
    
    Maintains a cross-day buffer per stock. When buffer has < 3 values,
    uses raw score (no smoothing yet).
    """
    alpha = 0.5  # = 2 / (span=3 + 1)
    for ts_code, r in pred_results.items():
        raw = r["score"]
        buf = self._score_buffer.setdefault(ts_code, [])
        buf.append(raw)
        if len(buf) > 3:
            buf.pop(0)
        if len(buf) >= 3:
            smoothed = buf[0]
            for v in buf[1:]:
                smoothed = alpha * v + (1 - alpha) * smoothed
            r["score"] = smoothed
```

### 2. 排名记录 `_record_ranks()`

```python
def _record_ranks(self, scored: List[ScoredStock], pred_results: Dict[str, Dict]) -> None:
    """Sort scored stocks by score and write rank back into pred_results.
    
    Rank is persisted via daily_snapshot for later analysis.
    Single-stock mode: rank stays 1, harmless.
    """
    scored_sorted = sorted(scored, key=lambda s: s.score, reverse=True)
    for rank, stock in enumerate(scored_sorted, start=1):
        pred_results[stock.ts_code]["rank"] = rank
```

### __init__ 新增

```python
self._score_buffer: Dict[str, List[float]] = {}  # ts_code → EWMA history
```

### 调用位置

```python
# Step 2: Predict
pred_results = ...
if not pred_results:
    continue

# Step 2a: Smooth scores
self._smooth_scores(pred_results)

# Build ScoredStock list
scored = [ScoredStock(...) for ts_code, r in pred_results.items()]

# Step 2b: Record ranks
self._record_ranks(scored, pred_results)

# Step 3: Make decisions
pending_orders = await self.strategy.make_decisions(scored, ...)
```

## 不影响的

- 单股票模式：scored 只有一个元素，平滑不影响排名，rank 恒为 1
- `make_decisions()` 接口不变
- 快照、交易记录 API 不变
- 前端不变
