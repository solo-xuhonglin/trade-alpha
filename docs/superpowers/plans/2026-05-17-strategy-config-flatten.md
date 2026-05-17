# 策略配置扁平化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Goal

将策略配置从 `config: Dict[str, Any]` 改为扁平字段，提升编辑体验和类型安全。

## Architecture

按顺序修改后端和前端，保持 API 响应一致。

## Tech Stack

- Backend: Python, Beanie, FastAPI
- Frontend: Vue 3, Vuetify 3, TypeScript

---

## Task 1: 修改 StrategyConfig Document

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\dao\strategy.py`

**Step-by-Step:**

- [ ] **Step 1: Update Document schema**
  - Remove `config: Dict[str, Any]` field
  - Add new fields:
    - `min_order_value: float = 5000.0`
    - `stop_loss_pct: float = -0.1`
    - `max_hold_days: int = 30`
    - `max_positions: Optional[int] = 10` (portfolio specific)
    - `max_position_pct: Optional[float] = 0.3` (portfolio specific)
  - Keep `created_at` and `updated_at` fields

- [ ] **Step 2: Verify changes**
  - Read modified file to confirm all fields added correctly

---

## Task 2: 修改 API Schemas

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\api\schemas.py`

**Step-by-Step:**

- [ ] **Step 1: Find StrategyCreate/Update schemas**
  - Locate existing schemas for strategy configuration

- [ ] **Step 2: Update schemas**
  - Remove `config` field
  - Add flat fields matching StrategyConfig Document
  - Keep `name` and `type` fields

- [ ] **Step 3: Verify changes**
  - Read modified file to confirm schemas are correct

---

## Task 3: 修改策略服务 (service.py)

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\strategy\service.py`

**Step-by-Step:**

- [ ] **Step 1: Update create_strategy signature**
  - Remove `config: Dict[str, Any]` parameter
  - Add flat parameters: `min_order_value`, `stop_loss_pct`, `max_hold_days`, `max_positions`, `max_position_pct` with defaults
  - Pass these params to StrategyConfig constructor

- [ ] **Step 2: Update update_strategy**
  - Remove `config` parameter
  - Add flat params as Optional
  - Update corresponding fields on StrategyConfig instance

- [ ] **Step 3: Verify changes**
  - Read modified file to confirm logic flows correctly

---

## Task 4: 修改 API 路由 (strategy_config.py)

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\api\routers\strategy_config.py`

**Step-by-Step:**

- [ ] **Step 1: Update _strategy_to_dict helper**
  - Remove `config` from response
  - Add all new flat fields to response dict

- [ ] **Step 2: Update create strategy endpoint**
  - Pass new schema fields to service.create_strategy
  - Ensure defaults are applied

- [ ] **Step 3: Update update strategy endpoint**
  - Pass new schema fields to service.update_strategy

- [ ] **Step 4: Verify changes**
  - Read modified file to confirm routes are updated

---

## Task 5: 修改前端 API 接口 (strategy.ts)

**Files:**
- Modify: `d:\projects\trade-alpha\frontend\src\api\strategy.ts`

**Step-by-Step:**

- [ ] **Step 1: Update Strategy interface**
  - Remove `config: Record<string, any>`
  - Add all flat fields
  - Add `updated_at?: string` (optional)

- [ ] **Step 2: Verify changes**
  - Read modified file to confirm interface matches new schema

---

## Task 6: 重写 StrategyView.vue 表单

**Files:**
- Modify: `d:\projects\trade-alpha\frontend\src\views\StrategyView.vue`

**Step-by-Step:**

- [ ] **Step 1: Update dialog max-width to 600px**
  - Change from 500px to 600px

- [ ] **Step 2: Replace form fields**
  - Use v-row/v-col grid layout like AccountsPage.vue
  - Remove JSON textarea
  - Add basic fields: name, type
  - Dynamically show fields based on type:
    - single: min_order_value, stop_loss_pct, max_hold_days
    - portfolio: max_positions, max_position_pct, min_order_value, stop_loss_pct, max_hold_days

- [ ] **Step 3: Update form logic**
  - Replace form configJson logic with flat field binding
  - Update openDialog to map backend fields to form
  - Update saveStrategy to send flat fields

- [ ] **Step 4: Update table headers**
  - Remove `config` column
  - Add `min_order_value`, `stop_loss_pct`, `max_hold_days` columns

- [ ] **Step 5: Verify changes**
  - Read modified file to confirm all changes are correct

---

## Task 7: 运行后端集成测试

**Files:**
- Test: `d:\projects\trade-alpha\backend\tests\trade_alpha\integration\test_44_strategy_service.py`

**Step-by-Step:**

- [ ] **Step 1: Run strategy service tests**
  - Navigate to backend directory
  - Run: `pytest tests\trade_alpha\integration\test_44_strategy_service.py -v`
  - Expected: All tests pass

---

## Task 8: 验证前端构建

**Files:**
- Build: Frontend project

**Step-by-Step:**

- [ ] **Step 1: Run frontend build**
  - Navigate to frontend directory
  - Run: `npm run build`
  - Expected: Build succeeds with no errors

---

## Notes

- No data migration required for now (we can implement later if needed)
- Portfolio strategy should also implement min_order_value check in its allocate_buy (currently it doesn't, but that's a separate issue)
