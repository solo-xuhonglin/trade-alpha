# 策略类型命名重构 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将策略类型值从 `"portfolio"` 改为 `"multi"`，类名 `PortfolioStrategy` 改为 `MultiStockStrategy`，消除与"投资组合"概念的歧义。

**Architecture:** 纯重命名重构，不涉及逻辑变更。`single` 模式不变，`portfolio` 模式全部改为 `multi`，涉及后端 Python 源码、前端 Vue 组件、测试文件和文档。

**Tech Stack:** Python 3.14+ (FastAPI, Beanie), Vue 3 (Composition API, Vuetify 3)

---

### Task 1: 创建 multi_stock_strategy.py

**Files:**
- Create: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`
- Delete: `backend/src/trade_alpha/strategy/portfolio_strategy.py`

- [ ] **Step 1: 创建新文件**

从 `portfolio_strategy.py` 复制，将类名 `PortfolioStrategy` 改为 `MultiStockStrategy`，logger 名 `strategy.portfolio_strategy` 改为 `strategy.multi_stock_strategy`

```python
"""Multi-stock strategy - ranking-based multi-stock trading."""

from typing import Dict, List, Optional

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.schemas import ScoredStock, PendingOrder
from trade_alpha.strategy.base import PositionManager
from trade_alpha.logging import get_logger

logger = get_logger("strategy.multi_stock_strategy")


class MultiStockStrategy(PositionManager):
    """Multi-stock portfolio strategy based on ranking."""

    # ... 其余代码与 PortfolioStrategy 一致，仅类名变更
```

其余代码与原 `PortfolioStrategy` 完全一致（`__init__`, `make_decisions`, `_check_sell`, `_allocate_buy`）。

- [ ] **Step 2: 删除旧文件**

```bash
git rm backend/src/trade_alpha/strategy/portfolio_strategy.py
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
git rm backend/src/trade_alpha/strategy/portfolio_strategy.py
git commit -m "refactor: rename PortfolioStrategy to MultiStockStrategy"
```

---

### Task 2: 更新后端导入引用

**Files:**
- Modify: `backend/src/trade_alpha/strategy/__init__.py`
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

- [ ] **Step 1: 更新 strategy/__init__.py**

将 import 路径和 __all__ 中的名称从 `PortfolioStrategy` 改为 `MultiStockStrategy`：

```python
from trade_alpha.strategy.base import PositionManager
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
from trade_alpha.strategy.single_stock import SingleStockStrategy

__all__ = [
    "PositionManager",
    "MultiStockStrategy",
    "SingleStockStrategy",
]
```

- [ ] **Step 2: 更新 pipeline.py**

```python
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
```

以及构造函数中的引用：

```python
self.strategy = MultiStockStrategy(
    account_config=account_config,
    strategy_config=strategy_config,
    ...
)
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/strategy/__init__.py backend/src/trade_alpha/execution/pipeline.py
git commit -m "refactor: update imports after MultiStockStrategy rename"
```

---

### Task 3: 更新策略类型值

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`
- Modify: `backend/src/trade_alpha/api/routers/backtest.py`
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

- [ ] **Step 1: 更新 strategy_config.py 默认值**

```python
type: str = Field(default="multi")
```

- [ ] **Step 2: 更新 backtest.py BacktestRunRequest 默认值**

```python
mode: str = "multi"
```

- [ ] **Step 3: 更新 pipeline.py 默认值和判断逻辑**

```python
# __init__ 默认值
mode: str = "multi",

# 判断逻辑不变（"single" 分支不变，"multi" 分支走 MultiStockStrategy）
if mode == "single":
    ...
else:
    self.strategy = MultiStockStrategy(...)
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/dao/strategy_config.py backend/src/trade_alpha/api/routers/backtest.py backend/src/trade_alpha/execution/pipeline.py
git commit -m "refactor: change portfolio strategy type value from portfolio to multi"
```

---

### Task 4: 重命名 backtest_portfolio 脚本

**Files:**
- Create: `backend/scripts/backtest_multi.py`
- Delete: `backend/scripts/backtest_portfolio.py`

- [ ] **Step 1: 创建 backtest_multi.py**

从 `backtest_portfolio.py` 复制，更新 logger 名：

```python
logger = get_logger("backtest_multi")
```

其余代码内容完全一致。

- [ ] **Step 2: 删除旧文件**

```bash
git rm backend/scripts/backtest_portfolio.py
```

- [ ] **Step 3: 提交**

```bash
git add backend/scripts/backtest_multi.py
git rm backend/scripts/backtest_portfolio.py
git commit -m "refactor: rename backtest_portfolio.py to backtest_multi.py"
```

---

### Task 5: 更新前端

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue`
- Modify: `frontend/src/views/BacktestManageView.vue`

- [ ] **Step 1: 更新 StrategyConfigView.vue**

将策略类型数组、默认值、中文标签和所有条件判断中的 `'portfolio'` 改为 `'multi'`：

```vue
<script setup>
const strategyTypes = ['single', 'multi']
</script>

<template>
  <v-select v-model="form.type" :items="strategyTypes" label="策略类型"></v-select>
  
  <!-- 条件渲染改为 type === 'multi' -->
  <v-tabs v-model="activeTab" color="primary" v-if="form.type === 'multi'">
    <v-tab value="multi">多股票配置</v-tab>
  </v-tabs>
  <v-window v-model="activeTab" v-if="form.type === 'multi'" class="mt-4">
    <v-window-item value="multi">
      <!-- 多股票配置内容 -->
    </v-window-item>
  </v-window>
</template>
```

以及提交/更新时的条件判断：

```javascript
max_positions: form.value.type === 'multi' ? form.value.max_positions : undefined,
max_position_pct: form.value.type === 'multi' ? form.value.max_position_pct : undefined,
sell_rank_n: form.value.type === 'multi' ? form.value.sell_rank_n : undefined,
hold_score_threshold: form.value.type === 'multi' ? form.value.hold_score_threshold : undefined,
```

- [ ] **Step 2: 更新 BacktestManageView.vue**

```javascript
const currentMode = computed(() => {
  const id = form.value.strategy_config_id
  if (!id) return 'multi'
  return strategyTypeMap.value[id] === 'single' ? 'single' : 'multi'
})
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/StrategyConfigView.vue frontend/src/views/BacktestManageView.vue
git commit -m "refactor: update frontend strategy type from portfolio to multi"
```

---

### Task 6: 更新测试

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_44_strategy_service.py`
- Modify: `backend/tests/trade_alpha/integration/test_61_backtest_lstm.py`

- [ ] **Step 1: 更新 test_44_strategy_service.py**

将测试中的策略类型值从 `"single"` / `"portfolio"` 更新（现有测试全部用 `"single"`，这里就是确认没有硬编码 `"portfolio"`）。

当前测试中所有 `strategy_type="single"` 保持不变，无需改动。

- [ ] **Step 2: 确认 test_61_backtest_lstm.py**

该测试使用 `mode="single"`，不受影响，无需改动。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/trade_alpha/integration/test_44_strategy_service.py
git commit -m "test: update strategy type values after rename"
```

---

### Task 7: 更新文档

**Files:**
- Modify: `docs/system-design.md`
- Modify: `docs/api.md`
- Modify: `docs/database-schema.md`
- Modify: `docs/scripts.md`

- [ ] **Step 1: 更新 system-design.md**

目录树：`portfolio_strategy.py` → `multi_stock_strategy.py`
策略描述：`portfolio` → `multi`

- [ ] **Step 2: 更新 api.md**

API 回测请求示例中的 `"portfolio"` → `"multi"`
mode 字段描述更新

- [ ] **Step 3: 更新 database-schema.md**

数据库示例中的 `"portfolio"` → `"multi"`

- [ ] **Step 4: 更新 scripts.md**

表格和描述中的 `backtest_portfolio.py` → `backtest_multi.py`

- [ ] **Step 5: 提交**

```bash
git add docs/system-design.md docs/api.md docs/database-schema.md docs/scripts.md
git commit -m "docs: update documentation after strategy type rename"
```

---

### Task 8: 全面验证

- [ ] **Step 1: 检查残留引用**

```bash
# 确认没有遗留的 "portfolio" 策略类型引用（排除 ExecutionPortfolioDaily）
cd d:\projects\trade-alpha
git grep -n "mode.*portfolio\|type.*portfolio\|PortfolioStrategy\|portfolio_strategy" -- backend/src backend/tests frontend/src docs
```

预期结果：只显示 `ExecutionPortfolioDaily` 相关引用（应保留）。

- [ ] **Step 2: 提交最终验证**

如果没有遗留问题，不需要额外提交。

- [ ] **Step 3: 运行测试**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/unit/ -v
```

确认所有单元测试通过。

---

### 不移改的确认清单

| 引用 | 原因 | 状态 |
|------|------|------|
| `ExecutionPortfolioDaily` | 投资组合概念，非策略类型 | 保留 ✅ |
| `PROD_ACCOUNT_CONFIG_NAME = "prod_account_config"` | 账户配置名，非策略类型 | 保留 ✅ |
| 非策略类型的 `portfolio` 文档/注释 | 通用术语 | 保留 ✅ |
