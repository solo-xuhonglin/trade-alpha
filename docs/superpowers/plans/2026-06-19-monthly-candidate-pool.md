# 月度候选池重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `CandidateListProvider` 从周度双选（市值+周涨幅）改为月度双选（市值+日线指标动量分），清理旧逻辑。

**Architecture:** Provider 内部生成 ISO 月 key 代替周 key，新增 `_get_momentum_stocks()` 用 6 个日线指标排名选股，删除旧的周涨幅查询方法。WarmupManager 和 Pipeline 只涉及变量重命名。

**Tech Stack:** Python 3.14+, MongoDB (Beanie ODM), StockDaily / StockListHistory

---

### Task 1: CandidateListProvider — 参数 + 月 key + 删旧方法

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\candidate_list_provider.py`

- [ ] **Step 1: 修改参数默认值和 `__init__`**

  把 `_up_n` 删掉，换成 `_momentum_n`；`_last_week_key` → `_last_period_key`；range_n 默认改为 300。

  ```python
  def __init__(self, params: dict):
      self._ts_codes: Optional[List[str]] = params.get("ts_codes")
      self._range_n: int = params.get("range_n", 300)
      self._top_n: int = params.get("top_n", 100)
      self._momentum_n: int = params.get("momentum_n", 20)
      self._candidate_map: Dict[str, List[str]] = {}
      self._current_candidates: List[str] = []
      self._last_period_key: Optional[str] = None
  ```

  同时新增 `StockDaily` 导入：
  ```python
  from trade_alpha.dao import TradeCalendar, StockListHistory, StockList
  from trade_alpha.dao.stock_daily import StockDaily  # 新增
  ```

- [ ] **Step 2: 修改 `get_candidates_for_date`**

  `_last_week_key` → `_last_period_key`，`_get_week_key` → `_get_period_key`（下一步改名）。

  ```python
  def get_candidates_for_date(self, date: str) -> List[str]:
      if self._ts_codes:
          return self._ts_codes
      period_key = self._get_period_key(date)
      if period_key != self._last_period_key:
          self._current_candidates = self._candidate_map.get(period_key, [])
          self._last_period_key = period_key
      return self._current_candidates
  ```

- [ ] **Step 3: 重命名 `_get_week_key` / `get_week_key` → `_get_period_key` / `get_period_key`**

  ```python
  def _get_period_key(self, date: str) -> Optional[str]:
      sorted_keys = sorted(self._candidate_map.keys())
      for key in reversed(sorted_keys):
          if date >= key:
              return key
      return None

  def get_period_key(self, date: str) -> Optional[str]:
      return self._get_period_key(date)
  ```

- [ ] **Step 4: 删除 `_get_prev_trade_date` 和 `_get_weekly_mv_gainers` 方法**

  删除整个 `_get_prev_trade_date()` 和 `_get_weekly_mv_gainers()` 方法（L117-L154）。

- [ ] **Step 5: 新增 `_get_momentum_stocks` 方法**

  ```python
  async def _get_momentum_stocks(
      self, trade_date: str, universe_codes: List[str], momentum_n: int,
  ) -> List[str]:
      """Select top momentum_n stocks by composite indicator rank from universe."""
      MOMENTUM_FIELDS = [
          "trend_slope_20", "trend_arrangement_20",
          "close_position_20", "close_position_60",
          "bias_20", "bias_60",
      ]
      records = await StockDaily.find(
          StockDaily.trade_date == trade_date,
          In(StockDaily.ts_code, universe_codes),
          StockDaily.trend_slope_20 != None,
          StockDaily.trend_arrangement_20 != None,
          StockDaily.close_position_20 != None,
          StockDaily.close_position_60 != None,
          StockDaily.bias_20 != None,
          StockDaily.bias_60 != None,
      ).to_list()
      if not records:
          return []
      # Build {ts_code: [v1, v2, ...]}
      stock_values: Dict[str, List[float]] = {}
      for r in records:
          vals = [getattr(r, f) for f in MOMENTUM_FIELDS]
          if all(v is not None for v in vals):
              stock_values[r.ts_code] = vals
      if not stock_values:
          return []
      # Per-indicator ranking: sum ranks across indicators → lower is better
      n_stocks = len(stock_values)
      n_fields = len(MOMENTUM_FIELDS)
      composite: Dict[str, int] = {ts: 0 for ts in stock_values}
      for fi in range(n_fields):
          ranked = sorted(stock_values.items(), key=lambda x: x[1][fi])
          for rank, (ts, _) in enumerate(ranked):
              composite[ts] += rank
      sorted_stocks = sorted(composite.items(), key=lambda x: x[1])
      return [ts for ts, _ in sorted_stocks[:momentum_n]]
  ```

- [ ] **Step 6: 修改 `_get_weekly_candidates` → `_get_candidates`，改为月 key + 新动量筛选**

  ```python
  async def _get_candidates(
      self, start_date: str, end_date: str,
  ) -> Dict[str, List[str]]:
      logger.info(
          f"Computing monthly candidates: {start_date}~{end_date}, "
          f"range_n={self._range_n}, top_n={self._top_n}, momentum_n={self._momentum_n}"
      )
      calendar_days = await self._get_trade_calendar(start_date, end_date)
      if not calendar_days:
          logger.warning(f"No trading days found in range {start_date}~{end_date}")
          return {}
      # Group by ISO month
      monthly: Dict[str, str] = {}
      for day in calendar_days:
          dt = datetime.strptime(day.cal_date, "%Y%m%d")
          month_key = f"{dt.year}M{dt.month:02d}"
          if month_key not in monthly:
              monthly[month_key] = day.cal_date
      result: Dict[str, List[str]] = {}
      prev_base: List[str] = []
      for _month_key, first_trade_date in sorted(monthly.items()):
          resolved = await self._resolve_date(first_trade_date)
          if not resolved:
              continue
          universe_records = await self._query_top_stocks(resolved, self._range_n)
          if not universe_records:
              continue
          universe_codes = [r.ts_code for r in universe_records]
          mv_group = universe_codes[:self._top_n]
          momentum_group = await self._get_momentum_stocks(
              resolved, universe_codes, self._momentum_n,
          )
          current_base = list(dict.fromkeys(mv_group + momentum_group))
          final = list(dict.fromkeys(current_base + prev_base))
          result[resolved] = final
          prev_base = current_base
      logger.info(
          f"Monthly candidates computed: {len(result)} months"
      )
      return result
  ```

- [ ] **Step 7: 更新 `initialize` 调用**

  ```python
  async def initialize(self, start_date: str, end_date: str) -> None:
      if not self._ts_codes:
          self._candidate_map = await self._get_candidates(
              start_date=start_date, end_date=end_date,
          )
  ```

- [ ] **Step 8: 更新 `candidate_map` 和 docstring 注释**

  ```python
  class CandidateListProvider:
      """Unified provider for candidate stock lists (fixed or monthly dynamic).

      Fixed mode: when params includes ts_codes, returns that list always.
      Dynamic mode: when ts_codes is absent, builds monthly candidate_map via
      _get_candidates() and returns the appropriate month's candidates
      per date.
      """

      @property
      def candidate_map(self) -> Dict[str, List[str]]:
          """Monthly candidate map (populated only in dynamic mode)."""
          return self._candidate_map
  ```

  同时更新文件顶部的模块 docstring：`weekly` → `monthly`。

- [ ] **Step 9: 移除不再需要的 `timedelta` 导入**

  确认 `_get_prev_trade_date` 已删后，`timedelta` 不再使用，从 imports 移除。`datetime` 仍需要（`strptime` 用于月 key）。

  ```python
  from datetime import datetime  # no longer need timedelta
  ```

- [ ] **Step 10: 提交**

  ```bash
  git add backend/src/trade_alpha/execution/candidate_list_provider.py
  git commit -m "refactor: change candidate pool from weekly to monthly with indicator-based momentum"
  ```

---

### Task 2: WarmupManager — 重命名 `_last_week_key`

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\warmup_manager.py`

- [ ] **Step 1: `_last_week_key` → `_last_update_key`**

  `__init__` 中：

  ```python
  self._last_update_key: Optional[str] = None
  ```

  `update_pool` 方法签名和 docstring 中：

  ```python
  def update_pool(self, current_period_key: Optional[str], formal_set: Set[str], candidate_map: Dict[str, List[str]]) -> None:
      """Update warmup pool based on current formal set, only on period changes.
      ...
      Args:
          current_period_key: Current period key (None if before first candidate period).
      ...
      """
      if current_period_key is None or current_period_key == self._last_update_key:
          return
      self._last_update_key = current_period_key
  ```

- [ ] **Step 2: 执行测试**

  ```powershell
  cd backend ; .venv\Scripts\pytest tests\trade_alpha\integration\test_warmup_manager.py -v
  ```

- [ ] **Step 3: 提交**

  ```bash
  git add backend/src/trade_alpha/execution/warmup_manager.py
  git commit -m "refactor: rename _last_week_key to _last_update_key in WarmupManager"
  ```

---

### Task 3: BacktestPipeline — 同步调用方改名

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\backtest_pipeline.py`

- [ ] **Step 1: 两处调用更新**

  `_run_warmup` 中（L337-339）：

  ```python
  current_period_key = provider.get_period_key(date)
  warmup_mgr.update_pool(current_period_key, set(formal_codes), provider.candidate_map)
  ```

  `_run_daily_loop` 中（L510-512）：

  ```python
  current_period_key = provider.get_period_key(date)
  warmup_mgr.update_pool(current_period_key, set(candidates), provider.candidate_map)
  ```

- [ ] **Step 2: 验证导入**

  ```powershell
  cd backend ; .venv\Scripts\python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"
  ```

- [ ] **Step 3: 提交**

  ```bash
  git add backend/src/trade_alpha/execution/backtest_pipeline.py
  git commit -m "refactor: update backtest pipeline to use get_period_key"
  ```

---

### Task 4: 单元测试 — 改为月 key + mock 动量方法

**Files:**
- Modify: `d:\projects\trade-alpha\backend\tests\trade_alpha\unit\execution\test_candidate_list_provider.py`

- [ ] **Step 1: 重写测试 `test_get_monthly_candidates_with_rolling`**

  把 4 周的 mock 日历改为 3 个月，mock `_get_momentum_stocks` 代替 `_get_weekly_mv_gainers`：

  ```python
  """Unit tests for CandidateListProvider — monthly dual-selection + rolling retain."""

  import pytest
  from unittest.mock import AsyncMock, patch

  from trade_alpha.execution.candidate_list_provider import CandidateListProvider


  @pytest.mark.asyncio
  async def test_get_monthly_candidates_with_rolling():
      """Verify monthly key format, dual selection, and rolling retain."""
      provider = CandidateListProvider({})

      # 3 months: Jan, Feb, Mar
      mock_calendar = [
          type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
          type("MockCal", (), {"cal_date": "20240201", "is_open": 1})(),
          type("MockCal", (), {"cal_date": "20240301", "is_open": 1})(),
      ]

      def mock_top_stocks(trade_date, top_n):
          results = {
              "20240102": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "B"})],
              "20240201": [type("M", (), {"ts_code": "B"}), type("M", (), {"ts_code": "C"})],
              "20240301": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "C"})],
          }
          return results.get(trade_date, [])

      def mock_momentum(trade_date, universe_codes, momentum_n):
          results = {
              "20240102": ["C"],
              "20240201": ["A"],
              "20240301": ["B"],
          }
          return results.get(trade_date, [])

      async def mock_resolve(date):
          return date

      with (
          patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
          patch.object(provider, "_resolve_date", side_effect=mock_resolve),
          patch.object(provider, "_query_top_stocks", side_effect=mock_top_stocks),
          patch.object(provider, "_get_momentum_stocks", side_effect=mock_momentum),
      ):
          await provider.initialize(
              start_date="20240101",
              end_date="20240331",
          )

      result = provider.candidate_map
      assert "20240102" in result
      assert "20240201" in result
      assert "20240301" in result
      # Jan: mv=[A,B] + momentum=[C] → [A,B,C]
      assert result["20240102"] == ["A", "B", "C"]
      # Feb: mv=[B,C] + momentum=[A] → [A,B,C], retain prev=[A,B,C] → [A,B,C]
      assert set(result["20240201"]) == {"A", "B", "C"}
      # Mar: mv=[A,C] + momentum=[B] → [A,B,C]
      assert set(result["20240301"]) == {"A", "B", "C"}
  ```

- [ ] **Step 2: 重写测试 `test_first_month_no_previous_base`**

  ```python
  @pytest.mark.asyncio
  async def test_first_month_no_previous_base():
      """First month should only have current base (no rolling retain yet)."""
      provider = CandidateListProvider({})

      mock_calendar = [
          type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),
      ]

      with (
          patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
          patch.object(provider, "_resolve_date", AsyncMock(return_value="20240102")),
          patch.object(provider, "_query_top_stocks", AsyncMock(return_value=[
              type("M", (), {"ts_code": "A"}),
              type("M", (), {"ts_code": "B"}),
          ])),
          patch.object(provider, "_get_momentum_stocks", AsyncMock(return_value=["C"])),
      ):
          await provider.initialize(
              start_date="20240101", end_date="20240110",
          )

      result = provider.candidate_map
      assert result["20240102"] == ["A", "B", "C"]
  ```

  注意删除原 `_get_weekly_mv_gainers` 和 `_get_prev_trade_date` 的 mock，改为 `_get_momentum_stocks`。

- [ ] **Step 3: 更新 `test_skips_missing_data`（仅改注释）**

  ```python
  @pytest.mark.asyncio
  async def test_skips_missing_data():
      """Month with no data should be skipped."""
  ```

- [ ] **Step 4: 运行测试**

  ```powershell
  cd backend ; .venv\Scripts\pytest tests\trade_alpha\unit\execution\test_candidate_list_provider.py -v
  ```

- [ ] **Step 5: 提交**

  ```bash
  git add tests/trade_alpha/unit/execution/test_candidate_list_provider.py
  git commit -m "test: update candidate provider tests for monthly keys"
  ```

---

### Task 5: 运行全量集成测试

- [ ] **Step 1: 运行集成测试**

  ```powershell
  cd backend ; .venv\Scripts\pytest tests\trade_alpha\integration\ -v
  ```

  Expected: 全部通过（134 passed）。

- [ ] **Step 2: 推送**

  ```bash
  git push
  ```
