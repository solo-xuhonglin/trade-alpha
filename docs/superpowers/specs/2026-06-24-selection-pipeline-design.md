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

### SelectionStep 协议

新增 `execution/selection_step.py`，每个 Step 是统一接口的类：

```python
class SelectionStep(ABC):
    """Base class for a selection step in the pipeline."""
    
    @abstractmethod
    async def run(self, date: str, universe: List[str]) -> SelectionResult:
        ...
```

`SelectionResult` 包含：
- `selected: List[str]` — 本轮新入选的股票
- `scored: Dict[str, float]` — 评分（用于跨周期平滑，动量 step 产出）

### 3 个 Step

| Step | 职责 | 输入 | 输出 |
|------|------|------|------|
| MarketCapStep | 市值前 top_n | universe | 选中的 ts_code 列表 |
| MomentumStep | 从剩余中加权评分选 momentum_n | universe（不含市值组已选） | 选中列表 + 评分 |
| MaTrendStep | 剔除 MA5/MA60 < threshold 的 | universe | 过滤后列表 |

### CandidateListProvider 修改

- `__init__`：构建 Step 管道列表
- `_get_candidates`：每个周期遍历管道，Step 顺序执行
  - 每个 Step 的 `selected` 累加到 `current_base`
  - 下一个 Step 的输入 = 当前全部候选（含之前 step 已选的）
- `_get_momentum_stocks` 迁移到 `MomentumStep.run()`

### 文件改动

- 新增：`execution/selection_step.py` — 协议 + 3 个 Step
- 修改：`execution/candidate_list_provider.py` — 用管道替代现有逻辑，删除 `_get_momentum_stocks`
- 其他文件：无改动（对外接口不变）
