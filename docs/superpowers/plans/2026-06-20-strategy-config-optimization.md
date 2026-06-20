# 策略配置优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 更新策略配置默认值、新增百分比排名字段、移除冗余判空和旧字段。

**Architecture:** 后端 model 改默认值 + 新增百分比字段、删除旧字段；各使用处去掉 getattr/if 兜底，改为直接访问；前端同步默认值、补充缺失的表单字段和布局。

**Tech Stack:** Python 3.14+, Vue 3, MongoDB (Beanie ODM)

---

### Task 1: StrategyConfig 模型 — 默认值 + 百分比字段 + 删除旧字段

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\dao\strategy_config.py`

- [ ] **Step 1: 更新默认值，新增 6 个百分比字段，删除 6 个旧字段**

  ```python
  class StrategyConfig(Document):
      name: str
      type: str = Field(default="multi")
      min_order_value: float = 50000.0
      stop_loss_pct: float = -0.1
      max_hold_days: int = 180
      min_hold_days: int = 5
      buy_threshold: float = 0.3
      sell_threshold: float = -0.05
      max_positions: Optional[int] = 6
      max_position_pct: Optional[float] = 0.2
      sell_rank_pct: float = 0.15
      hold_score_threshold: Optional[float] = 0.1
      use_momentum_boost: bool = False
      momentum_window: int = 12
      max_momentum_bonus: float = 0.15
      use_momentum_penalty: bool = False
      use_explosion_filter: bool = False
      explosion_price_threshold: float = 0.08
      explosion_volume_ratio: float = 3.0
      explosion_window: int = 5
      use_trend_bonus: bool = False
      trend_bonus_window: int = 15
      trend_bonus_scale: float = 0.03
      trend_r2_threshold: float = 0.30
      trend_max_bonus: float = 0.1
      use_trend_penalty: bool = False
      use_full_position_sell: bool = False
      full_position_threshold: float = 0.90
      full_position_days: int = 5
      full_position_score_window: int = 15
      full_position_sell_count: int = 1
      use_rank_up_priority: bool = False
      rank_up_window: int = 3
      rank_up_count: int = 1
      rank_up_min_score: float = -0.1
      rank_up_min_improvement_pct: float = 0.15
      ranking_smooth_window: int = 5
      ranking_smooth_alpha: float = 0.3
      score_decline_threshold: float = 0.05
      use_score_decline_filter: bool = False
      full_position_pnl_weight: float = 0.5
      market_smooth_window: int = 3
      market_smooth_alpha: float = 0.3
      top_n_retention_pct: float = 0.20
      retention_days: int = 5
      correlation_window: int = 5
      use_phase_strategy: bool = True
      atr_stop_multiplier: float = 3.0
      atr_trail_rate: float = 0.5
      max_daily_buys: int = 2
      rotation_bottom_pct: float = 0.60
      rotation_rank_min_pct: float = 0.30
      rotation_rank_max_pct: float = 0.70
      rotation_use_reversal_check: bool = True
      rotation_was_top_pct: float = 0.15
      rotation_pullback_window: int = 5
      rotation_was_top_window: int = 60
      created_at: Optional[datetime] = None
      updated_at: Optional[datetime] = None
  ```

  删除的旧字段：`sell_rank_n`, `rotation_bottom_threshold`, `rotation_rank_min`, `rotation_rank_max`, `rotation_was_top_n`, `top_n_retention`

- [ ] **Step 2: 验证导入**

  ```powershell
  cd backend ; .venv\Scripts\python -c "from trade_alpha.dao.strategy_config import StrategyConfig; print('OK')"
  ```

- [ ] **Step 3: 提交**

  ```bash
  git add backend/src/trade_alpha/dao/strategy_config.py
  git commit -m "feat: update strategy config defaults, add pct fields, remove old fields"
  ```

---

### Task 2: scoring.py — 移除 `if self._strategy_config`

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\scoring.py:438-455`

- [ ] **Step 1: 修改 `_load_close_prices_hist`**

  ```python
  async def _load_close_prices_hist(
      self,
      pred_results: Dict[str, Dict],
      date: str,
      data_loader: DataLoader,
  ) -> Dict[str, List[float]]:
      lookback = 15
      if self._strategy_config.use_trend_bonus:
          lookback = max(lookback, self._strategy_config.trend_bonus_window)
      if self._strategy_config.use_momentum_boost:
          lookback = max(lookback, self._strategy_config.momentum_window)
  ```

- [ ] **Step 2: 提交**

  ```bash
  git add backend/src/trade_alpha/execution/scoring.py
  git commit -m "refactor: remove redundant strategy_config null checks in scoring"
  ```

---

### Task 3: backtest_pipeline.py — 移除 `getattr` 兜底

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\backtest_pipeline.py:83-87`

- [ ] **Step 1: 直接访问字段**

  ```python
  self.portfolio = PortfolioManager(
      account_config=self.account_config,
      initial_capital=account_config.initial_capital,
      max_positions=strategy_config.max_positions,
      max_position_pct=strategy_config.max_position_pct,
      min_order_value=strategy_config.min_order_value,
      atr_stop_multiplier=strategy_config.atr_stop_multiplier,
      atr_trail_rate=strategy_config.atr_trail_rate,
  )
  ```

  第 58 行 `strategy_config: Optional[StrategyConfig] = None` 改为 `strategy_config: StrategyConfig`。

  第 143 行 `}) if self.strategy_config else None,` 去掉 `if` 判断。

- [ ] **Step 2: 验证导入**

  ```powershell
  cd backend ; .venv\Scripts\python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"
  ```

- [ ] **Step 3: 提交**

  ```bash
  git add backend/src/trade_alpha/execution/backtest_pipeline.py
  git commit -m "refactor: remove getattr fallback for strategy_config in backtest_pipeline"
  ```

---

### Task 4: market_regime.py — 移除 `getattr` + 改用百分比

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\market_regime.py:133`

- [ ] **Step 1: 改用 `top_n_retention_pct`**

  ```python
  def _compute_top_n_retention(
      self, stock_map: Dict[str, ScoredStock]
  ) -> float:
      n_pct = self._strategy_config.top_n_retention_pct
      d = self._strategy_config.retention_days
      total_stocks = len(stock_map)
      n = max(1, int(total_stocks * n_pct))
      if n <= 0:
          return 0.0
  ```

- [ ] **Step 2: 提交**

  ```bash
  git add backend/src/trade_alpha/execution/market_regime.py
  git commit -m "refactor: use top_n_retention_pct in market_regime"
  ```

---

### Task 5: suggestion_pipeline.py — 移除 `if self.strategy_config and`

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\suggestion_pipeline.py:153-156`

- [ ] **Step 1: 简化条件判断**

  ```python
  lookback = max(
      self.strategy_config.trend_bonus_window if self.strategy_config.use_trend_bonus else 0,
      self.strategy_config.momentum_window if self.strategy_config.use_momentum_boost else 0,
      self.strategy_config.ranking_smooth_window,
  )
  ```

  第 60 行 `strategy_config: Optional[StrategyConfig] = None` 改为 `strategy_config: StrategyConfig`。

- [ ] **Step 2: 提交**

  ```bash
  git add backend/src/trade_alpha/execution/suggestion_pipeline.py
  git commit -m "refactor: remove redundant strategy_config null checks in suggestion_pipeline"
  ```

---

### Task 6: multi_stock_strategy.py + rotation_mode.py — 百分比转换

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\strategy\multi_stock_strategy.py:84-88`
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\strategy\modes\rotation_mode.py:42-51`

- [ ] **Step 1: `make_orders` — 百分比 + 清理 `top_ts_codes` 死参**

  ```python
  # ── 6. Compute sell_rank_ts_codes for check_sell ──
  sorted_all = sorted(scored_stocks, key=lambda s: s.ranking_score, reverse=True)
  total = len(sorted_all)
  sell_rank_count = max(1, int(total * ctx.strategy_config.sell_rank_pct))
  sell_rank_ts_codes = {s.ts_code for s in sorted_all[:sell_rank_count]}

  # ── 7. Sell loop ──
  for ts_code, pos in ctx.portfolio.positions.items():
      should_sell, reason = self.check_sell(
          pos, sell_rank_ts_codes, score_map,
          close_prices, market_data, ctx=ctx,
      )
  ```

  `check_sell` 签名去掉 `top_ts_codes`：

  ```python
  def check_sell(
      self,
      position: PositionEmbed,
      sell_rank_ts_codes: set,
      score_map: Dict[str, float],
      ...
  ```

- [ ] **Step 2: `rotation_mode.py` — 百分比转换**

  ```python
  def select_buy_candidates(self, scored_stocks, ctx, market_data=None):
      config = ctx.strategy_config
      hold_ts_codes = set(ctx.portfolio.positions.keys())
      total = len(scored_stocks)
      rank_min = int(total * config.rotation_rank_min_pct)
      rank_max = int(total * config.rotation_rank_max_pct)
      bottom_rank = int(total * config.rotation_bottom_pct)
      was_top_count = int(total * config.rotation_was_top_pct)

      candidates: List[BuyCandidate] = []
      for st in scored_stocks:
          if st.is_excluded:
              continue
          if st.ts_code in hold_ts_codes:
              continue
          if not (rank_min <= st.rank <= rank_max):
              continue
          rank_history = ...
          pw = config.rotation_pullback_window
          ww = config.rotation_was_top_window
          if len(rank_history) < max(ww, pw) + pw + 1:
              continue
          was_top = any(r <= was_top_count for r in rank_history[-(ww + pw):-pw])
          recent_bottom = any(r >= bottom_rank for r in rank_history[-pw:])
          ...
  ```

- [ ] **Step 3: 提交**

  ```bash
  git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
  git add backend/src/trade_alpha/strategy/modes/rotation_mode.py
  git commit -m "refactor: use pct-based ranks, clean top_ts_codes dead param"
  ```

---

### Task 7: 前端同步 — 默认值 + 表单字段

**Files:**
- Modify: `d:\projects\trade-alpha\frontend\src\views\StrategyConfigView.vue`

- [ ] **Step 1: 更新 `form` 默认值**

  同步更新全部数值默认值，新增百分比字段和缺失的 boolean 开关字段，删除旧字段。

- [ ] **Step 2: 补充表单 UI**

  - 新增 `use_momentum_penalty`、`use_trend_penalty`、`use_score_decline_filter` 的开关组件
  - 补充百分比字段的输入组件和 label
  - 删除旧字段（`sell_rank_n` 等）的输入组件
  - 调整表单布局，确保所有字段有对应的 UI 展示

- [ ] **Step 3: 提交**

  ```bash
  git add frontend/src/views/StrategyConfigView.vue
  git commit -m "feat: sync frontend strategy config with new defaults and pct fields"
  ```

---

### Task 8: 集成验证

- [ ] **Step 1: 全量导入检查**

  ```powershell
  cd backend ; .venv\Scripts\python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; from trade_alpha.execution.suggestion_pipeline import SuggestionPipeline; from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy; from trade_alpha.strategy.modes.rotation_mode import RotationMode; print('OK')"
  ```

- [ ] **Step 2: 运行集成测试**

  ```powershell
  cd backend ; .venv\Scripts\pytest tests\trade_alpha\integration\ -v
  ```

- [ ] **Step 3: 推送**

  ```bash
  git push
  ```
