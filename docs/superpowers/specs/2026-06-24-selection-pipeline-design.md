# 选股逻辑串行管道重构

## 概述

将候选池构建的 3 个选股逻辑从并行合并改为串行管道。每个逻辑是统一签名的 Step 方法，输入股票列表，输出筛选后的股票列表。

## Step 接口

所有 Step 统一签名：

```python
async def _step_xxx(self, date: str, universe: List[str]) -> List[str]
```

- `date`: 交易日
- `universe`: 输入的股票池
- 返回: 通过筛选的股票列表

Step 内部可持有自身状态（如动量 step 的 `prev_composite`），不暴露在接口中。

## 管道流程

```
[全量候选 300]
  ↓ _step_market_cap    取前 top_n 只
  ↓                     (未选中的送入下一轮)
  ↓ _step_momentum      从剩余中选 momentum_n 只
  ↓                     (入选的加入 current_base)
  ↓ _step_ma_trend      从 current_base 中剔除下降趋势股
  ↓
  current_base → + prev_base → final
```

Step 1（市值）：从 universe 中取前 top_n，返回这些股票。未命中传递到 Step 2。

Step 2（动量）：从 universe（未命中的剩余）中选 momentum_n 只。当前所有动量权重、EWMA 平滑逻辑都在此 step 内部。

Step 3（MA趋势）：从 current_base 中过滤，剔除 MA5/MA60 < threshold 的。

## 改动范围

仅修改 `candidate_list_provider.py`：
- 删除 `_get_momentum_stocks`
- 新增 `_step_market_cap`、`_step_momentum`、`_step_ma_trend`
- 重写 `_get_candidates` 串行调用
- `_step_momentum` 中 `prev_composite` 改用 `self._prev_composite`

其他文件无改动。
