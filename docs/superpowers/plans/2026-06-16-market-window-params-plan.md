# Market Window Parameters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `retention_days` and `correlation_window` parameters to refine the retention rate and score-return correlation computations.

**Architecture:** Two new config fields control how many lookback days each indicator uses. The computation methods in `ScoreManager` read these fields from `strategy_config`. Buffers and smoothing are unchanged.

**Tech Stack:** Python 3.14+, FastAPI, Beanie/MongoDB, TypeScript, Vue 3

**File structure overview:**

| Layer | File | Change |
|-------|------|--------|
| Backend DAO | `dao/strategy_config.py` | Add `retention_days`, `correlation_window` |
| Backend DAO | `dao/execution.py` | Add same 2 fields to `StrategySnapshotEmbed` |
| Backend Core | `execution/scoring.py` | Update `_compute_top_n_retention` and `_compute_score_return_correlation` |
| Backend Logic | `strategy/service.py` | Add 2 params to create/update function sigs |
| Backend API | `api/schemas.py` | Add 2 fields to request models |
| Backend API | `api/routers/strategy_config.py` | Serialize + pass 2 new fields |
| Frontend API | `api/strategyConfig.ts` | Add 2 fields to `Strategy` interface |
| Frontend View | `views/StrategyConfigView.vue` | Reorganize 4 sections; add 2 fields |
| Frontend View | `views/BacktestRecordsView.vue` | Add 2 comparison fields |
| Docs | `docs/features-indicators.md` | Update market analysis section |
| Backend Test | `tests/trade_alpha/unit/execution/test_scoring.py` | Add tests for new logic |

---

### Task 1: Backend DAO — strategy_config.py

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`

- [ ] **Step 1: Add 2 new fields**

After line 52 (`top_n_retention: int = 20`), add:

```python
    retention_days: int = 5
    correlation_window: int = 5
```

- [ ] **Step 2: Verify import**

```bash
cd backend
python -c "from trade_alpha.dao.strategy_config import StrategyConfig; print('OK')"
```

---

### Task 2: Backend DAO — execution.py (StrategySnapshotEmbed)

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution.py`

- [ ] **Step 1: Add 2 fields to StrategySnapshotEmbed**

After `top_n_retention: int = 20` (the line just added in previous commit), add:

```python
    retention_days: int = 5
    correlation_window: int = 5
```

The full block becomes:

```python
    top_n_retention: int = 20
    retention_days: int = 5
    correlation_window: int = 5
    market_trend_threshold: float = 0.05
```

---

### Task 3: Backend Core — scoring.py (retention rate)

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Update `_compute_top_n_retention` method**

Replace the existing method with window-param version:

```python
    def _compute_top_n_retention(
        self, stock_map: Dict[str, ScoredStock]
    ) -> float:
        """Compute raw top-N stock retention rate using _rank_history.

        Compares D days ago top N vs today top N.
        Returns 0.0 if insufficient history or n <= 0.
        """
        n = getattr(self._strategy_config, "top_n_retention", 20)
        d = getattr(self._strategy_config, "retention_days", 5)
        if n <= 0:
            return 0.0

        d_ago_top_n = set()
        for ts_code in stock_map:
            records = self._rank_history.get(ts_code, [])
            if len(records) > d and 0 < records[-1-d].rank <= n:
                d_ago_top_n.add(ts_code)

        if not d_ago_top_n:
            return 0.0

        today_top_n = {
            ts_code for ts_code, stock in stock_map.items()
            if 0 < stock.rank <= n
        }

        return len(d_ago_top_n & today_top_n) / len(d_ago_top_n)
```

- [ ] **Step 2: Verify module loads**

```bash
cd backend
python -c "from trade_alpha.execution.scoring import ScoreManager; print('OK')"
```

---

### Task 4: Backend Core — scoring.py (correlation)

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Update `_compute_score_return_correlation` method**

Replace the existing method with window-average version:

```python
    def _compute_score_return_correlation(
        self, stock_map: Dict[str, ScoredStock]
    ) -> float:
        """Compute Pearson correlation between N-day avg composite_score and N-day avg pct_chg.

        Uses correlation_window from strategy_config. Excludes stocks that had
        any is_excluded day in the window. Requires at least 3 stocks with data.
        """
        window = getattr(self._strategy_config, "correlation_window", 5)
        scores = []
        returns = []

        for ts_code in stock_map:
            records = self._rank_history.get(ts_code, [])
            if len(records) < window + 1:
                continue

            recent = records[-(window+1):]
            if any(s.is_excluded for s in recent[:-1]):
                continue

            # Average composite_score over past window days
            avg_score = sum(s.composite_score for s in recent[:-1]) / window

            # Average pct_chg over past window days
            pct_chgs = []
            for j in range(window):
                r1 = recent[-2-j]  # T-1-j
                r2 = recent[-3-j]  # T-2-j
                if r2.close <= 0:
                    break
                pct_chgs.append((r1.close - r2.close) / r2.close)
            if len(pct_chgs) < window:
                continue
            avg_pct_chg = sum(pct_chgs) / window

            scores.append(avg_score)
            returns.append(avg_pct_chg)

        if len(scores) < 3:
            return 0.0

        return _pearson_corr(scores, returns)
```

- [ ] **Step 2: Verify module loads**

```bash
cd backend
python -c "from trade_alpha.execution.scoring import ScoreManager; print('OK')"
```

---

### Task 5: Backend Logic — strategy/service.py

**Files:**
- Modify: `backend/src/trade_alpha/strategy/service.py`

- [ ] **Step 1: Add params to `create_strategy` signature**

After `top_n_retention: Optional[int] = None,`, add:

```python
    retention_days: Optional[int] = None,
    correlation_window: Optional[int] = None,
```

- [ ] **Step 2: Add params to `update_strategy` signature**

Same change, after `top_n_retention: Optional[int] = None,`, add:

```python
    retention_days: Optional[int] = None,
    correlation_window: Optional[int] = None,
```

- [ ] **Step 3: Add apply block in `update_strategy`**

After `if top_n_retention is not None: strategy.top_n_retention = top_n_retention`, add:

```python
    if retention_days is not None:
        strategy.retention_days = retention_days
    if correlation_window is not None:
        strategy.correlation_window = correlation_window
```

---

### Task 6: Backend API — api/schemas.py

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py`

- [ ] **Step 1: Add to `StrategyCreateRequest`**

After `top_n_retention: Optional[int] = None`, add:

```python
    retention_days: Optional[int] = None
    correlation_window: Optional[int] = None
```

- [ ] **Step 2: Add to `StrategyUpdateRequest`**

Same fields at the same location.

---

### Task 7: Backend API — api/routers/strategy_config.py

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/strategy_config.py`

- [ ] **Step 1: Update `_strategy_to_dict`**

After `"top_n_retention": s.top_n_retention,`, add:

```python
        "retention_days": s.retention_days,
        "correlation_window": s.correlation_window,
```

- [ ] **Step 2: Update `create_strategy_endpoint` call**

Add to the kwargs dict:

```python
            retention_days=request.retention_days,
            correlation_window=request.correlation_window,
```

- [ ] **Step 3: Update `update_strategy_endpoint` call**

Same addition.

---

### Task 8: Frontend API — strategyConfig.ts

**Files:**
- Modify: `frontend/src/api/strategyConfig.ts`

- [ ] **Step 1: Add 2 fields to `Strategy` interface**

After `top_n_retention?: number`, add:

```typescript
  retention_days?: number
  correlation_window?: number
```

---

### Task 9: Frontend View — StrategyConfigView.vue (layout)

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue`

- [ ] **Step 1: Replace the entire market tab content**

Replace the content of `<v-window-item value="market">` (from line 270 `            <div>` to line 335 `            </div>`) with:

```html
            <div>
              <v-row>
                <v-col cols="12">
                  <v-switch v-model="form.use_market_aware_trading" hide-details density="compact"
                    color="primary" label="市场状态指导交易"
                    hint="下跌趋势不新买入，横盘期间最小持仓天数翻倍" persistent-hint />
                </v-col>
              </v-row>

              <v-divider class="my-3"></v-divider>

              <v-row>
                <v-col cols="12">
                  <div class="text-body-2 mb-2">
                    <v-icon size="small" class="mr-1">mdi-chart-bell-curve</v-icon>
                    平滑参数
                    <v-chip size="x-small" variant="outlined" color="info">用于分数中位数/留存率/关联度的EWMA平滑</v-chip>
                  </div>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.market_smooth_window" type="number" min="1"
                    label="市场平滑窗口" hint="EWMA 窗口天数，前 N 天不平滑（默认 5）" persistent-hint />
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.market_smooth_alpha" type="number" step="0.05" min="0.05" max="0.95"
                    label="市场平滑系数" hint="EMA 平滑系数，为空则用 2/(window+1)" persistent-hint />
                </v-col>
              </v-row>

              <v-divider class="my-3"></v-divider>

              <v-row>
                <v-col cols="12">
                  <div class="text-body-2 mb-2">
                    <v-icon size="small" class="mr-1">mdi-chart-bell-curve</v-icon>
                    分数中位数
                    <v-chip size="x-small" variant="outlined" color="info">基于全市场排序分(ranking_score)中位数</v-chip>
                  </div>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.market_trend_threshold" type="number" step="0.01"
                    label="趋势阈值" hint="排序分中位数高于此值 -> 趋势市（默认 0.05）" persistent-hint />
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.market_high_score_threshold" type="number" step="0.01"
                    label="高分线" hint="排序分高于此值 -> 算高分股（默认 0.30）" persistent-hint />
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.market_low_score_threshold" type="number" step="0.01"
                    label="低分线" hint="排序分低于此值 -> 算低分股（默认 -0.30）" persistent-hint />
                </v-col>
              </v-row>

              <v-divider class="my-3"></v-divider>

              <v-row>
                <v-col cols="12">
                  <div class="text-body-2 mb-2">
                    <v-icon size="small" class="mr-1">mdi-chart-bell-curve</v-icon>
                    留存率
                    <v-chip size="x-small" variant="outlined" color="info">排名前N的股票经过N日后的留存比例</v-chip>
                  </div>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.top_n_retention" type="number" min="1"
                    label="留存率N值" hint="排名前 N 的股票计算留存率（默认 20）" persistent-hint />
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.retention_days" type="number" min="1"
                    label="留存天数" hint="D 天前的 top N 到今天还有多少留存（默认 5）" persistent-hint />
                </v-col>
              </v-row>

              <v-divider class="my-3"></v-divider>

              <v-row>
                <v-col cols="12">
                  <div class="text-body-2 mb-2">
                    <v-icon size="small" class="mr-1">mdi-chart-bell-curve</v-icon>
                    评分收益关联度
                    <v-chip size="x-small" variant="outlined" color="info">N日内平均评分与平均收益率的截面相关</v-chip>
                  </div>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.correlation_window" type="number" min="2"
                    label="关联度窗口" hint="N 日内平均 composite_score 与平均 pct_chg 做截面相关（默认 5）" persistent-hint />
                </v-col>
              </v-row>
            </div>
```

- [ ] **Step 2: Add `retention_days` and `correlation_window` to form load from API**

After line 698 (`top_n_retention: item.top_n_retention ?? 20,`), add:

```typescript
      retention_days: item.retention_days ?? 5,
      correlation_window: item.correlation_window ?? 5,
```

- [ ] **Step 3: Add to default values**

After line 747 (`top_n_retention: 20,`), add:

```typescript
      retention_days: 5,
      correlation_window: 5,
```

- [ ] **Step 4: Add to create submit**

After line 799 (`top_n_retention: form.value.top_n_retention,`), add:

```typescript
      retention_days: form.value.retention_days,
      correlation_window: form.value.correlation_window,
```

- [ ] **Step 5: Add to update submit**

After line 847 (`top_n_retention: form.value.top_n_retention,`), add:

```typescript
      retention_days: form.value.retention_days,
      correlation_window: form.value.correlation_window,
```

- [ ] **Step 6: Add to comparison fields (after `top_n_retention` line 631)**

```typescript
  { key: 'retention_days', label: '留存天数', group: '市场分析', type: 'number' },
  { key: 'correlation_window', label: '关联度窗口', group: '市场分析', type: 'number' },
```

---

### Task 10: Frontend View — BacktestRecordsView.vue (comparison fields)

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: Add 2 comparison fields**

After line 964 (`{ key: 'top_n_retention', label: '留存率N值', group: '市场分析', type: 'number' },`), add:

```typescript
  { key: 'retention_days', label: '留存天数', group: '市场分析', type: 'number' },
  { key: 'correlation_window', label: '关联度窗口', group: '市场分析', type: 'number' },
```

---

### Task 11: Backend Tests — update test_scoring.py

**Files:**
- Modify: `backend/tests/trade_alpha/unit/execution/test_scoring.py`

- [ ] **Step 1: Add unit tests for `_compute_top_n_retention` and `_compute_score_return_correlation` with window params**

Add after the existing classes:

```python
class TestScoreManagerMethods:
    """Tests for ScoreManager computation methods using mock rank history."""

    def _make_mock_stock(self, ts_code: str, rank: int, close: float = 10.0,
                         composite_score: float = 0.0, is_excluded: bool = False) -> ScoredStock:
        return ScoredStock(
            ts_code=ts_code,
            stock_name=ts_code,
            rank=rank,
            close=close,
            composite_score=composite_score,
            is_excluded=is_excluded,
        )

    @pytest.mark.asyncio
    async def test_top_n_retention_insufficient_history_returns_zero(self):
        """When rank_history has fewer records than retention_days, return 0.0."""
        from trade_alpha.execution.scoring import ScoreManager
        from trade_alpha.dao.strategy_config import StrategyConfig

        config = StrategyConfig(name="test", type="multi")
        manager = ScoreManager(config, None)

        stock_map = {"000001.SZ": self._make_mock_stock("000001.SZ", rank=1)}
        result = manager._compute_top_n_retention(stock_map)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_top_n_retention_default_days(self):
        """Test retention_days=1 (same as original T-1→T logic)."""
        from trade_alpha.execution.scoring import ScoreManager
        from trade_alpha.dao.strategy_config import StrategyConfig

        config = StrategyConfig(name="test", type="multi", top_n_retention=2, retention_days=1)
        manager = ScoreManager(config, None)

        # Day 1: stock A rank=1, stock B rank=2, stock C rank=3 (not in top 2)
        day1 = {
            "A": self._make_mock_stock("A", rank=1),
            "B": self._make_mock_stock("B", rank=2),
            "C": self._make_mock_stock("C", rank=3),
        }
        # populate rank_history
        for s in day1.values():
            manager._rank_history.setdefault(s.ts_code, []).append(s)

        # Day 2: A still rank=1, C now rank=2 (B dropped out)
        day2 = {
            "A": self._make_mock_stock("A", rank=1),
            "C": self._make_mock_stock("C", rank=2),
            "B": self._make_mock_stock("B", rank=3),
        }
        # Day 2 uses the existing day1 data + day2 stock_map for "today"
        for s in day2.values():
            manager._rank_history.setdefault(s.ts_code, []).append(s)

        # retention_days=1: T-1 top2 = {A, B}, today top2 = {A, C}
        # retained = {A}, 1/2 = 0.5
        result = manager._compute_top_n_retention(day2)
        assert abs(result - 0.5) < 0.001

    @pytest.mark.asyncio
    async def test_top_n_retention_custom_days(self):
        """Test retention_days=2: D days ago vs today."""
        from trade_alpha.execution.scoring import ScoreManager
        from trade_alpha.dao.strategy_config import StrategyConfig

        config = StrategyConfig(name="test", type="multi", top_n_retention=2, retention_days=2)
        manager = ScoreManager(config, None)

        # Day 1: A=1, B=2
        for s in [self._make_mock_stock("A", rank=1), self._make_mock_stock("B", rank=2),
                  self._make_mock_stock("C", rank=3)]:
            manager._rank_history.setdefault(s.ts_code, []).append(s)

        # Day 2: A=1, C=2, B=3
        for s in [self._make_mock_stock("A", rank=1), self._make_mock_stock("C", rank=2),
                  self._make_mock_stock("B", rank=3)]:
            manager._rank_history.setdefault(s.ts_code, []).append(s)

        # Day 3 (today): B=1, A=2, C=3
        day3 = {"A": self._make_mock_stock("A", rank=2), "B": self._make_mock_stock("B", rank=1),
                "C": self._make_mock_stock("C", rank=3)}
        for s in day3.values():
            manager._rank_history.setdefault(s.ts_code, []).append(s)

        # retention_days=2: D=2 ago (day1) top2 = {A, B}, today top2 = {B, A}
        # retained = {A, B}, 2/2 = 1.0
        result = manager._compute_top_n_retention(day3)
        assert abs(result - 1.0) < 0.001
```

- [ ] **Step 2: Run tests**

```bash
cd backend
.venv\Scripts\pytest tests\trade_alpha\unit\execution\test_scoring.py -v
```

Expected: 21 tests pass (17 existing + 4 new).

---

### Task 12: Documentation — features-indicators.md

**Files:**
- Modify: `docs/features-indicators.md`

- [ ] **Step 1: Update market analysis section**

In the parameter table at the bottom of the market analysis section, add:

```markdown
| `retention_days` | int | 5 | 留存天数：D 天前的 top N 到今天还有多少留存 |
| `correlation_window` | int | 5 | 关联度窗口：N 日内平均评分与平均收益率做截面相关 |
```

And update the retention rate description to mention the days parameter:

```
- **Top-N Retention Rate (排名前N留存率)** — D 天前排名前 n 的股票中，当天仍然在前 n 名的比例。
  参数 `top_n_retention`（N值）和 `retention_days`（天数）可配置。
```

Update the correlation description:

```
- **Score-Return Correlation (评分与收益率关联度)** — N 日内每只股票 `composite_score` 均值与 `pct_chg` 均值的 Pearson 截面相关系数。
  参数 `correlation_window` 控制均值窗口长度。
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Config (Tasks 1-2), scoring logic (Tasks 3-4), service/API wiring (Tasks 5-7), frontend (Tasks 8-10), tests (Task 11), docs (Task 12).
- [x] **Placeholder scan:** No TBD, TODO, or incomplete sections.
- [x] **Type consistency:** All field names (`retention_days`, `correlation_window`) are consistently used across all 12 tasks.
- [x] **Testing:** New test cases cover retention_days=1 (backward compat), retention_days=2 (multi-day), and insufficient history.
