# 选股参数配置 + 持仓保护实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将动量选股权重参数从硬编码改为 StrategyConfig 可配置，新增持仓保护开关

**Architecture:** StrategyConfig 新增 4 个字段；CandidateListProvider 直接接收 strategy_config 读取权重；backtest_pipeline 每日循环中根据 use_hold_protection 将持仓股保留在评分池中

**Tech Stack:** Python 3.14+, Vue 3, MongoDB (Beanie ODM), FastAPI

---

### Task 1: StrategyConfig DAO — 新增 4 个字段

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\dao\strategy_config.py`

- [ ] **Step 1: 新增字段**

  在 `StrategyConfig` 类末尾、`created_at` 之前添加：

  ```python
      # 选股参数（动量指标权重，None 时使用代码默认值）
      momentum_fields_weights: Optional[Dict[str, float]] = None
      log_mv_weight: float = 1.0
      improvement_weight: float = 0.2

      # 持仓保护
      use_hold_protection: bool = False
  ```

  同时补充 `from typing import Dict, Optional`（如果已有则跳过）。

- [ ] **Step 2: 验证导入**

  Run: `cd d:\projects\trade-alpha\backend ; .venv\Scripts\python -c "from trade_alpha.dao.strategy_config import StrategyConfig; c=StrategyConfig(name='t'); print(f'weights={c.momentum_fields_weights}, imp={c.improvement_weight}, hold={c.use_hold_protection}')"`
  Expected: `weights=None, imp=0.2, hold=False`

- [ ] **Step 3: Commit**

  Run: `cd d:\projects\trade-alpha ; git add -A ; git commit -m "feat: add momentum selection weight fields to StrategyConfig"`

---

### Task 2: API Schemas — 新增请求/响应字段

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\api\schemas.py`

- [ ] **Step 1: StrategyCreateRequest 新增字段**

  ```python
  momentum_fields_weights: Optional[Dict[str, float]] = None
  log_mv_weight: Optional[float] = 1.0
  improvement_weight: Optional[float] = 0.2
  use_hold_protection: Optional[bool] = False
  ```

- [ ] **Step 2: StrategyUpdateRequest 新增字段**

  同样添加以上 4 个字段，默认值一致。

- [ ] **Step 3: 验证导入**

  Run: `cd d:\projects\trade-alpha\backend ; .venv\Scripts\python -c "from trade_alpha.api.schemas import StrategyCreateRequest, StrategyUpdateRequest; print('OK')"`
  Expected: `OK`

- [ ] **Step 4: Commit**

  Run: `cd d:\projects\trade-alpha ; git add -A ; git commit -m "feat: add momentum selection fields to API schemas"`

---

### Task 3: Strategy Service — 传递新字段

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\strategy\service.py`

- [ ] **Step 1: create_strategy 添加参数**

  在函数签名中添加：
  ```python
  momentum_fields_weights: Optional[Dict[str, float]] = None,
  log_mv_weight: Optional[float] = None,
  improvement_weight: Optional[float] = None,
  use_hold_protection: Optional[bool] = None,
  ```

  在函数体中添加赋值：
  ```python
  if momentum_fields_weights is not None:
      strategy.momentum_fields_weights = momentum_fields_weights
  if log_mv_weight is not None:
      strategy.log_mv_weight = log_mv_weight
  if improvement_weight is not None:
      strategy.improvement_weight = improvement_weight
  if use_hold_protection is not None:
      strategy.use_hold_protection = use_hold_protection
  ```

- [ ] **Step 2: update_strategy 添加相同参数和赋值**

  update_strategy 函数签名和体做同样添加。

- [ ] **Step 3: 验证导入**

  Run: `cd d:\projects\trade-alpha\backend ; .venv\Scripts\python -c "from trade_alpha.strategy.service import create_strategy, update_strategy; print('OK')"`
  Expected: `OK`

- [ ] **Step 4: Commit**

  Run: `cd d:\projects\trade-alpha ; git add -A ; git commit -m "feat: pass momentum selection fields through strategy service"`

---

### Task 4: API Router — 序列化 + 传递新字段

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\api\routers\strategy_config.py`

- [ ] **Step 1: _strategy_to_dict 添加序列化**

  在 `ranking_smooth_alpha` 行之后、`score_decline_threshold` 之前添加：
  ```python
      "momentum_fields_weights": s.momentum_fields_weights,
      "log_mv_weight": s.log_mv_weight,
      "improvement_weight": s.improvement_weight,
      "use_hold_protection": s.use_hold_protection,
  ```

- [ ] **Step 2: create/update handler 传递新参数**

  在 create handler 的 `create_strategy(` 调用中添加：
  ```python
  momentum_fields_weights=request.momentum_fields_weights,
  log_mv_weight=request.log_mv_weight,
  improvement_weight=request.improvement_weight,
  use_hold_protection=request.use_hold_protection,
  ```

  update handler 同样添加。

- [ ] **Step 3: 验证导入**

  Run: `cd d:\projects\trade-alpha\backend ; .venv\Scripts\python -c "from trade_alpha.api.routers.strategy_config import _strategy_to_dict; print('OK')"`
  Expected: `OK`

- [ ] **Step 4: Commit**

  Run: `cd d:\projects\trade-alpha ; git add -A ; git commit -m "feat: serialize momentum selection fields in strategy API"`

---

### Task 5: CandidateListProvider — 接收 strategy_config + 使用配置权重

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\candidate_list_provider.py`

- [ ] **Step 1: __init__ 新增 strategy_config 参数**

  将构造函数改为：
  ```python
  def __init__(self, params: dict, strategy_config: Optional[StrategyConfig] = None):
      # Fixed-list mode
      self._ts_codes: Optional[List[str]] = params.get("ts_codes")
      # Dynamic pool params
      self._range_n: int = params.get("range_n", 300)
      self._top_n: int = params.get("top_n", 100)
      self._momentum_n: int = params.get("momentum_n", 20)
      # Momentum selection weights from strategy_config
      self._momentum_fields_weights: Optional[Dict[str, float]] = None
      self._log_mv_weight: float = 1.0
      self._improvement_weight: float = 0.2
      if strategy_config is not None:
          self._momentum_fields_weights = strategy_config.momentum_fields_weights
          self._log_mv_weight = strategy_config.log_mv_weight
          self._improvement_weight = strategy_config.improvement_weight
      # Internal state
      self._candidate_map: Dict[str, List[str]] = {}
      self._stock_groups: Dict[str, str] = {}
      self._current_candidates: List[str] = []
      self._last_period_key: Optional[str] = None
  ```

- [ ] **Step 2: _get_momentum_stocks 使用配置权重替代硬编码**

  修改 `_get_momentum_stocks` 中硬编码的权重定义：

  ```python
      # 用配置权重替代硬编码
      MOMENTUM_FIELDS = [
          ("trend_slope_20", True, w := self._momentum_fields_weights.get("trend_slope_20", 1.0) if self._momentum_fields_weights else 1.0),
      ]
  ```

  实际上更清晰的方式—在方法开头构建列表：
  ```python
      # Build field weights from config (or defaults)
      FIELD_WEIGHTS = {
          "trend_slope_20": 1.0, "trend_arrangement_20": 1.0,
          "close_position_20": 1.0, "close_position_60": 1.0,
          "bias_20": 1.0, "bias_60": 1.0, "atr_14": 0.3,
      }
      if self._momentum_fields_weights is not None:
          FIELD_WEIGHTS.update(self._momentum_fields_weights)

      MOMENTUM_FIELDS = [
          ("trend_slope_20", True, FIELD_WEIGHTS["trend_slope_20"]),
          ("trend_arrangement_20", True, FIELD_WEIGHTS["trend_arrangement_20"]),
          ("close_position_20", True, FIELD_WEIGHTS["close_position_20"]),
          ("close_position_60", True, FIELD_WEIGHTS["close_position_60"]),
          ("bias_20", True, FIELD_WEIGHTS["bias_20"]),
          ("bias_60", True, FIELD_WEIGHTS["bias_60"]),
          ("atr_14", False, FIELD_WEIGHTS["atr_14"]),
      ]
  ```

  同时将 `LOG_MV_WEIGHT` 和 `IMPROVEMENT_WEIGHT` 改为从 `self` 读取。

- [ ] **Step 3: 验证导入**

  Run: `cd d:\projects\trade-alpha\backend ; .venv\Scripts\python -c "from trade_alpha.execution.candidate_list_provider import CandidateListProvider; print('OK')"`
  Expected: `OK`

- [ ] **Step 4: 运行相关测试**

  Run: `cd d:\projects\trade-alpha\backend ; .venv\Scripts\pytest tests\trade_alpha\unit\execution\test_candidate_list_provider.py tests\trade_alpha\integration\test_warmup_manager.py -v`
  Expected: 11/11 passed

- [ ] **Step 5: Commit**

  Run: `cd d:\projects\trade-alpha ; git add -A ; git commit -m "feat: CandidateListProvider reads momentum weights from strategy_config"`

---

### Task 6: BacktestPipeline — 传入 strategy_config + 持仓保护逻辑

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\backtest_pipeline.py`

- [ ] **Step 1: Provider 创建时传入 strategy_config**

  ```python
  # 改前
  provider = CandidateListProvider(params)

  # 改后
  provider = CandidateListProvider(params, strategy_config)
  ```

- [ ] **Step 2: 每日循环中持仓保护逻辑**

  在 `_run_daily_loop` 中，找到 `candidates = provider.get_candidates_for_date(date)` 之后的 `candidate_close` 构建处：

  ```python
  candidates = provider.get_candidates_for_date(date)
  if self.strategy_config.use_hold_protection:
      hold_codes = set(ctx.portfolio.positions.keys())
      all_scored = set(candidates) | hold_codes
      candidate_close = {k: v for k, v in close_prices.items() if k in all_scored}
  else:
      candidate_close = {k: v for k, v in close_prices.items() if k in candidates}
  ```

- [ ] **Step 3: _detect_outdated_positions 添加持仓保护**

  ```python
  def _detect_outdated_positions(self, date, close_prices, candidates):
      sell_orders = []
      for ts_code, pos in list(self.portfolio.positions.items()):
          if ts_code not in candidates:
              if self.strategy_config.use_hold_protection:
                  continue
              # ... 原有逻辑不变
  ```

- [ ] **Step 4: 验证导入**

  Run: `cd d:\projects\trade-alpha\backend ; .venv\Scripts\python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"`
  Expected: `OK`

- [ ] **Step 5: Run full integration tests**

  Run: `cd d:\projects\trade-alpha\backend ; .venv\Scripts\pytest tests\trade_alpha\integration\ -v`
  Expected: 134 passed

- [ ] **Step 6: Commit**

  Run: `cd d:\projects\trade-alpha ; git add -A ; git commit -m "feat: add hold protection and pass strategy_config to provider"`

---

### Task 7: 前端 API 类型更新

**Files:**
- Modify: `d:\projects\trade-alpha\frontend\src\api\strategyConfig.ts`

- [ ] **Step 1: Strategy 接口新增字段**

  ```typescript
  export interface Strategy {
    // ... 现有字段 ...
    momentum_fields_weights?: Record<string, number>
    log_mv_weight?: number
    improvement_weight?: number
    use_hold_protection?: boolean
  }
  ```

- [ ] **Step 2: 验证编译**

  Run: `cd d:\projects\trade-alpha\frontend ; npx vue-tsc --noEmit 2>&1`
  Expected: No errors

- [ ] **Step 3: Commit**

  Run: `cd d:\projects\trade-alpha ; git add -A ; git commit -m "feat: update frontend Strategy interface with weight fields"`

---

### Task 8: 前端页面 — 新增"选股配置"Tab

**Files:**
- Modify: `d:\projects\trade-alpha\frontend\src\views\StrategyConfigView.vue`

- [ ] **Step 1: Tabs 新增"选股配置"tab**

  在 `<v-tabs>` 中添加：
  ```vue
  <v-tab value="selection">选股配置</v-tab>
  ```

- [ ] **Step 2: Tab 内容面板**

  在 `<v-tabs-items>` 中添加对应面板，包含：
  - 8 个指标的权重输入框（step=0.1, min=0, max=10）
  - improvement_weight 输入框（step=0.05, min=0, max=1）
  - use_hold_protection 开关
  - 每个字段带 hint 说明

- [ ] **Step 3: 表单默认值**

  在 `createDefaultForm()` 和 `openDialog()` 的 fallback 中添加：
  ```javascript
  momentum_fields_weights: null,
  log_mv_weight: 1.0,
  improvement_weight: 0.2,
  use_hold_protection: false,
  ```

- [ ] **Step 4: 提交时包含新字段**

  在 `submitForm` 中确保新字段被发送。

- [ ] **Step 5: 配置对比包含新字段**

  `compareFields` 中添加新字段到对比列表。

- [ ] **Step 6: 验证编译**

  Run: `cd d:\projects\trade-alpha\frontend ; npx vue-tsc --noEmit 2>&1`
  Expected: No errors

- [ ] **Step 7: Commit**

  Run: `cd d:\projects\trade-alpha\git add -A ; git commit -m "feat: add stock selection config tab to strategy config page"`

---

### Task 9: 全量验证 + 推送

- [ ] **Step 1: 全量集成测试**

  Run: `cd d:\projects\trade-alpha\backend ; .venv\Scripts\pytest tests\trade_alpha\integration\ -v`
  Expected: All passed

- [ ] **Step 2: 前端编译检查**

  Run: `cd d:\projects\trade-alpha\frontend ; npx vue-tsc --noEmit 2>&1`
  Expected: No errors

- [ ] **Step 3: 推送**

  Run: `cd d:\projects\trade-alpha ; git push`
