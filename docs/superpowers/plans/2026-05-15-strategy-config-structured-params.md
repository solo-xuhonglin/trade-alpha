# 策略配置参数结构化改造方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将策略代码中的硬编码参数改为从 `StrategyConfig.config` 读取，前端参考账户配置模式展示结构化表单

**Architecture:** 
- 后端：`ExecutionPipeline` 从 `StrategyConfig.config` 读取参数传给策略构造函数，策略使用 config 中的值（有默认值兜底）
- 前端：策略表单根据 `type` 不同展示不同字段（参考 `AccountsPage.vue`），取消通用 JSON 编辑器

**Tech Stack:** Python/Beanie/MongoDB, Vue3/Vuetify

---

### Task 1: 后端 — Pipeline 从 StrategyConfig 读取参数

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:55-73`

- [ ] **Step 1: 读取 strategy_config 的 config 用于策略初始化**

修改 Pipeline.__init__，从 `strategy_config.config` 读取策略参数，传给策略构造函数：

```python
# pipeline.py 第 58-73 行，替换为：
        # Read strategy params from config (with defaults)
        strategy_cfg = strategy_config.config if strategy_config else {}
        
        if mode == "single":
            target_code = single_stock_ts_code or (ts_codes[0] if ts_codes else None)
            assert target_code, "single mode requires ts_codes or single_stock_ts_code"
            self.strategy = SingleStockStrategy(
                account_config=account_config,
                target_ts_code=target_code,
                stop_loss_pct=strategy_cfg.get("stop_loss_pct", -0.1),
                max_hold_days=strategy_cfg.get("max_hold_days", 30),
                min_order_value=strategy_cfg.get("min_order_value", 5000),
            )
            self.single_stock_ts_code = target_code
        else:
            self.strategy = PortfolioStrategy(
                account_config=account_config,
                max_positions=strategy_cfg.get("max_positions", max_positions),
                max_position_pct=strategy_cfg.get("max_position_pct", 0.3),
                stop_loss_pct=strategy_cfg.get("stop_loss_pct", -0.1),
                max_hold_days=strategy_cfg.get("max_hold_days", 20),
                min_order_value=strategy_cfg.get("min_order_value", 5000),
                ts_codes=ts_codes,
            )
```

- [ ] **Step 2: 修改 pipeline 中 scoring universe 大小从 config 读取**

修改 `pipeline.py:124` 的硬编码 limit：

```python
# 第 121-124 行，替换：
        scoring_limit = strategy_cfg.get("scoring_limit", 200) if self.single_stock_ts_code else strategy_cfg.get("scoring_limit", 3000)
        limit = scoring_limit
```

- [ ] **Step 3: 运行测试验证**

Run: `cd backend && python -m pytest tests/trade_alpha/integration/test_44_strategy_service.py -v --tb=short`
Expected: 5 passed

---

### Task 2: 后端 — 策略构造函数使用 config 参数

**Files:**
- Modify: `backend/src/trade_alpha/strategy/base.py:21-35`（不修改，保持默认值不变）
- Verify: `backend/src/trade_alpha/strategy/single_stock.py:17-32`（已接受参数）

这一步已在 Task 1 中通过 pipeline 传参完成。策略构造函数的默认值作为 fallback 保留。

- [ ] **Step 1: 验证单股策略参数可以外部传入**

检查 `SingleStockStrategy.__init__` 已接受 `stop_loss_pct`, `max_hold_days`, `min_order_value` 参数。

- [ ] **Step 2: 验证组合策略参数可以外部传入**

检查 `PortfolioStrategy.__init__` 已接受 `max_positions`, `max_position_pct`, `stop_loss_pct`, `max_hold_days`, `min_order_value` 参数。

---

### Task 3: 前端 — 策略表单结构化改造

**Files:**
- Modify: `frontend/src/views/StrategyView.vue`

参考 `AccountsPage.vue`，策略表单的配置字段改为结构化展示，不同 type 显示不同字段。

- [ ] **Step 1: 更新模板 — 为 single/portfolio 类型分别展示结构化字段**

```vue
<!-- 替换 template 中的配置区域 (第49-57行) -->
          <template v-if="form.type === 'single'">
            <v-col cols="12">
              <v-text-field v-model="form.config.target_ts_code" label="目标股票代码" hint="例如: 002594.SZ" persistent-hint></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.config.stop_loss_pct" label="止损比例" type="number" step="0.01" hint="默认 -0.1 (-10%)" persistent-hint></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.config.max_hold_days" label="最长持有天数" type="number" hint="默认 30 天" persistent-hint></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.config.min_order_value" label="最小订单金额" type="number" hint="默认 5000" persistent-hint></v-text-field>
            </v-col>
          </template>
          <template v-else-if="form.type === 'portfolio'">
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.config.max_positions" label="最大持仓数量" type="number" hint="默认 10" persistent-hint></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.config.max_position_pct" label="单股仓位上限" type="number" step="0.01" hint="默认 0.3 (30%)" persistent-hint></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.config.stop_loss_pct" label="止损比例" type="number" step="0.01" hint="默认 -0.1 (-10%)" persistent-hint></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.config.max_hold_days" label="最长持有天数" type="number" hint="默认 20 天" persistent-hint></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.config.min_order_value" label="最小订单金额" type="number" hint="默认 5000" persistent-hint></v-text-field>
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.config.scoring_limit" label="评分候选数量" type="number" hint="默认 3000" persistent-hint></v-text-field>
            </v-col>
          </template>
```

- [ ] **Step 2: 更新 setup 中的 form 和默认值**

```typescript
// 替换 form ref 定义
const defaultConfigs: Record<string, Record<string, any>> = {
  single: { stop_loss_pct: -0.1, max_hold_days: 30, min_order_value: 5000 },
  portfolio: { max_positions: 10, max_position_pct: 0.3, stop_loss_pct: -0.1, max_hold_days: 20, min_order_value: 5000, scoring_limit: 3000 },
}

const form = ref({
  name: '',
  type: 'single',
  config: {} as Record<string, any>,
})
```

- [ ] **Step 3: 更新 openDialog 函数设置默认配置**

```typescript
const openDialog = (item?: Strategy) => {
  if (item) {
    editingId.value = item.id
    form.value = { name: item.name, type: item.type, config: { ...item.config } }
  } else {
    editingId.value = null
    form.value = { name: 'default_strategy', type: 'single', config: { ...defaultConfigs['single'] } }
  }
  dialog.value = true
}
```

- [ ] **Step 4: 更新 saveStrategy 移除 configJson 相关逻辑**

```typescript
const saveStrategy = async () => {
  if (editingId.value) {
    await strategyApi.update(editingId.value, { name: form.value.name, config: form.value.config })
  } else {
    await strategyApi.create({ name: form.value.name, type: form.value.type, config: form.value.config })
  }
  dialog.value = false
  await loadStrategies()
}
```

- [ ] **Step 5: 构建验证**

Run: `cd frontend && npm run build`
Expected: Build successful, no errors

---

### Task 4: 运行全量验证

**Files:**
- Test: `backend/tests/trade_alpha/integration/`

- [ ] **Step 1: 运行集成测试**

Run: `cd backend && python -m pytest tests/trade_alpha/integration/ -v --tb=short`
Expected: 47 passed

- [ ] **Step 2: 重启服务**

Run: `cd d:\projects\trade-alpha && .\restart.bat`
Expected: Backend + Frontend started successfully
