# 候选池周度更新实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `CandidateListProvider` 候选池从月度更新改为周度，每周最后一个交易日筛选。

**Architecture:** Provider 内部改用 ISO 周 key 分组，覆盖写入法取最后交易日。WarmupManager 预热窗口计算从月交易日折算改为周。Pipeline 无改动。

**Tech Stack:** Python 3.14+, MongoDB (Beanie ODM)

---

### Task 1: CandidateListProvider — 周度分组 + 最后交易日

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\candidate_list_provider.py`

- [ ] **Step 1: 修改 `_get_candidates()` — 月→周分组**

  改核心分组逻辑：

  ```python
  async def _get_candidates(
      self, start_date: str, end_date: str,
  ) -> Dict[str, List[str]]:
      logger.info(
          f"Computing weekly candidates: {start_date}~{end_date}, "
          f"range_n={self._range_n}, top_n={self._top_n}, momentum_n={self._momentum_n}"
      )
      calendar_days = await self._get_trade_calendar(start_date, end_date)
      if not calendar_days:
          logger.warning(f"No trading days found in range {start_date}~{end_date}")
          return {}

      # Group by ISO week, using last trading day of each week
      weekly: Dict[str, str] = {}
      for day in calendar_days:
          dt = datetime.strptime(day.cal_date, "%Y%m%d")
          iso_year, iso_week, _ = dt.isocalendar()
          week_key = f"{iso_year}W{iso_week:02d}"
          weekly[week_key] = day.cal_date  # overwrite → last trading day

      result: Dict[str, List[str]] = {}
      prev_base: List[str] = []
      for _week_key, last_trade_date in sorted(weekly.items()):
          resolved = await self._resolve_date(last_trade_date)
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
          f"Weekly candidates computed: {len(result)} weeks"
      )
      return result
  ```

- [ ] **Step 2: 更新 docstring 和注释**

  文件顶部 docstring：
  ```python
  """CandidateListProvider — provides weekly dynamic candidate stock pools for backtesting."""
  ```

  类 docstring：
  ```python
  class CandidateListProvider:
      """Unified provider for candidate stock lists (fixed or weekly dynamic).

      Fixed mode: when params includes ts_codes, returns that list always.
      Dynamic mode: when ts_codes is absent, builds weekly candidate_map via
      _get_candidates() and returns the appropriate week's candidates
      per date.
      """
  ```

  `candidate_map` property docstring：
  ```python
  @property
  def candidate_map(self) -> Dict[str, List[str]]:
      """Weekly candidate map (populated only in dynamic mode)."""
      return self._candidate_map
  ```

- [ ] **Step 3: 验证导入**

  ```bash
  cd d:\projects\trade-alpha\backend
  .venv\Scripts\python -c "from trade_alpha.execution.candidate_list_provider import CandidateListProvider; print('OK')"
  ```

  Expected: `OK`

- [ ] **Step 4: 提交**

  ```bash
  git add -A
  git commit -m "feat: change candidate pool from monthly to weekly (last trading day)"
  ```


### Task 2: WarmupManager — 预热窗口按周计算

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\warmup_manager.py`

- [ ] **Step 1: 修改 `update_pool` 中的 lookahead 计算**

  改前：
  ```python
  # Limit future candidates to within warmup_days trading days (~20 trading days/month)
  lookahead_months = max(1, (warmup_days + 19) // 20)
  sorted_future_keys = sorted(k for k in candidate_map if k > current_period_key)[:lookahead_months]
  ```

  改后：
  ```python
  # Limit future candidates to within warmup_days trading days (~5 trading days/week)
  lookahead_periods = max(1, (warmup_days + 4) // 5)
  sorted_future_keys = sorted(k for k in candidate_map if k > current_period_key)[:lookahead_periods]
  ```

- [ ] **Step 2: 验证导入**

  ```bash
  cd d:\projects\trade-alpha\backend
  .venv\Scripts\python -c "from trade_alpha.execution.warmup_manager import WarmupManager; print('OK')"
  ```

  Expected: `OK`

- [ ] **Step 3: 提交**

  ```bash
  git add -A
  git commit -m "feat: update warmup lookahead from monthly to weekly period calculation"
  ```


### Task 3: 单元测试更新

**Files:**
- Modify: `d:\projects\trade-alpha\backend\tests\trade_alpha\unit\execution\test_candidate_list_provider.py`

- [ ] **Step 1: 重命名测试 + mock 数据从月改为周**

  测试数据改为 3 个连续的周（可以跨月），验证每周最后一个交易日逻辑：

  ```python
  """Unit tests for CandidateListProvider — weekly dual-selection + rolling retain."""

  import pytest
  from unittest.mock import AsyncMock, patch

  from trade_alpha.execution.candidate_list_provider import CandidateListProvider


  @pytest.mark.asyncio
  async def test_get_weekly_candidates_with_rolling():
      """Verify weekly key format, last trading day, dual selection, and rolling retain."""
      provider = CandidateListProvider({})

      # 3 weeks: week 1 (Mon Jan 1), week 2 (Mon Jan 8), week 3 (Mon Jan 15)
      # Last trading days would be Jan 5 (Fri), Jan 12 (Fri), Jan 19 (Fri)
      mock_calendar = [
          type("MockCal", (), {"cal_date": "20240101", "is_open": 1})(),  # Mon
          type("MockCal", (), {"cal_date": "20240102", "is_open": 1})(),  # Tue
          type("MockCal", (), {"cal_date": "20240103", "is_open": 1})(),  # Wed
          type("MockCal", (), {"cal_date": "20240104", "is_open": 1})(),  # Thu
          type("MockCal", (), {"cal_date": "20240105", "is_open": 1})(),  # Fri (last of W1)
          type("MockCal", (), {"cal_date": "20240109", "is_open": 1})(),  # Tue
          type("MockCal", (), {"cal_date": "20240110", "is_open": 1})(),  # Wed
          type("MockCal", (), {"cal_date": "20240111", "is_open": 1})(),  # Thu
          type("MockCal", (), {"cal_date": "20240112", "is_open": 1})(),  # Fri (last of W2)
          type("MockCal", (), {"cal_date": "20240116", "is_open": 1})(),  # Tue
          type("MockCal", (), {"cal_date": "20240117", "is_open": 1})(),  # Wed
          type("MockCal", (), {"cal_date": "20240118", "is_open": 1})(),  # Thu
          type("MockCal", (), {"cal_date": "20240119", "is_open": 1})(),  # Fri (last of W3)
      ]

      def mock_top_stocks(trade_date, top_n):
          results = {
              "20240105": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "B"})],
              "20240112": [type("M", (), {"ts_code": "B"}), type("M", (), {"ts_code": "C"})],
              "20240119": [type("M", (), {"ts_code": "A"}), type("M", (), {"ts_code": "C"})],
          }
          return results.get(trade_date, [])

      def mock_momentum(trade_date, universe_codes, momentum_n):
          results = {
              "20240105": ["C"],
              "20240112": ["A"],
              "20240119": ["B"],
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
              end_date="20240131",
          )

      result = provider.candidate_map
      # Should only have 3 weekly keys (last trading day of each week)
      assert "20240105" in result
      assert "20240112" in result
      assert "20240119" in result
      # W1: mv=[A,B] + momentum=[C] -> [A,B,C]
      assert result["20240105"] == ["A", "B", "C"]
      # W2: mv=[B,C] + momentum=[A] -> [A,B,C], rolling retain same set
      assert set(result["20240112"]) == {"A", "B", "C"}
      # W3: mv=[A,C] + momentum=[B] -> [A,B,C]
      assert set(result["20240119"]) == {"A", "B", "C"}
      # Verify Monday Jan 1 and Tuesday Jan 2 are NOT keys (only last trading days)
      assert "20240101" not in result
      assert "20240102" not in result


  @pytest.mark.asyncio
  async def test_first_week_no_previous_base():
      """First week should only have current base (no rolling retain yet)."""
      provider = CandidateListProvider({})

      mock_calendar = [
          type("MockCal", (), {"cal_date": "20240103", "is_open": 1})(),
          type("MockCal", (), {"cal_date": "20240104", "is_open": 1})(),
          type("MockCal", (), {"cal_date": "20240105", "is_open": 1})(),
      ]

      with (
          patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
          patch.object(provider, "_resolve_date", AsyncMock(return_value="20240105")),
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
      # Only the last trading day 20240105 (Friday) should be the key
      assert "20240105" in result
      assert result["20240105"] == ["A", "B", "C"]


  @pytest.mark.asyncio
  async def test_skips_missing_data():
      """Week with no resolveable data should be skipped."""
      provider = CandidateListProvider({})

      mock_calendar = [type("MockCal", (), {"cal_date": "20240103", "is_open": 1})()]

      with (
          patch.object(provider, "_get_trade_calendar", AsyncMock(return_value=mock_calendar)),
          patch.object(provider, "_resolve_date", AsyncMock(return_value=None)),
      ):
          await provider.initialize(
              start_date="20240101", end_date="20240131",
          )

      assert provider.candidate_map == {}
  ```

- [ ] **Step 2: 运行测试**

  ```bash
  cd d:\projects\trade-alpha\backend
  .venv\Scripts\pytest tests\trade_alpha\unit\execution\test_candidate_list_provider.py -v
  ```

  Expected: 3/3 passed

- [ ] **Step 3: 提交**

  ```bash
  git add -A
  git commit -m "test: update candidate provider tests for weekly keys and last trading day"
  ```


### Task 4: 集成测试验证

- [ ] **Step 1: 运行全量集成测试**

  ```bash
  cd d:\projects\trade-alpha\backend
  .venv\Scripts\pytest tests\trade_alpha\integration\ -v
  ```

  Expected: all passed

- [ ] **Step 2: 推送**

  ```bash
  git push
  ```
