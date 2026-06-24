# 选股逻辑串行管道重构

## 概述

将候选池构建的 3 个选股逻辑（市值筛选、动量筛选、MA 趋势过滤）从并行合并改为串行管道，每个逻辑作为独立 Step 顺序执行，上一个的输出是下一个的输入。行为不变：最终候选池 = 当期结果 + 上期结果。

## 当前流程（并行）

```
universe(300)
  ├→ 市值取前 top_n → [市值组]
  ├→ 动量从剩余中选 momentum_n → [动量组]
  ├→ 合并: current_base = 市值组 + 动量组
  ├→ 留存: final = current_base + prev_base
  └→ MA趋势过滤 (挂在final后)
```

## 目标流程（串行）

```
universe(300)
  ↓ [Step 市值] 取前 top_n
  ↓ [Step 动量] 从剩余中选 momentum_n  
  ↓ [Step MA趋势] 剔除 MA5/MA60 < threshold
  ↓ 
  current_base = 各 step 入选的并集
  ↓
  final = current_base + prev_base
```

## 架构

### 统一 Step 接口

在 `candidate_list_provider.py` 中定义，每个 Step 是统一签名的异步方法：

```python
async def _step_market_cap(self, date: str, universe: List[str]) -> Tuple[List[str], Dict[str, float]]:
```

返回 `(selected_codes, scores)`，scores 为选股评分（动量 step 产出，其他 step 返回空 dict）。

### 3 个 Step

| Step | 方法 | 说明 |
|------|------|------|
| 市值 | `_step_market_cap` | 取 universe 前 top_n |
| 动量 | `_step_momentum` | 从 universe 中加权评分选 momentum_n（现 `_get_momentum_stocks`） |
| MA趋势 | `_step_ma_trend` | 从 universe 中剔除 MA5/MA60 < threshold |

### CandidateListProvider 修改

- `__init__`：移除 `_range_n`/`_top_n`/`_momentum_n` 等老字段，保留 strategy_config 引用
- `_get_candidates`：每个周期先取 `universe_codes`，然后顺序调用 3 个 Step
  - 每个 Step 的输入是截至目前尚未被任何 Step 选中的股票，输出是本次入选的股票
  - Step 的 `selected` 累加到 `current_base`
  - `current_base` 中已入选的股票传给下一个 Step 的 universe 中，但 Step 内部会过滤（动量 step 只用尚未入选的做排名）
- 删除 `_get_momentum_stocks`，逻辑迁移到 `_step_momentum`
