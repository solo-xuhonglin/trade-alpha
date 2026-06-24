# MA 趋势过滤 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 候选池构建最后阶段增加一个可配置的硬过滤：剔除 MA5 在 MA60 下方超过阈值的下降趋势股票

**Architecture:**
- 后端：`_get_candidates` 计算完 `final` 后，若开关开启，查询 MA5/MA60 并过滤；DAO 和 API Schema 各加 2 个字段
- 前端：选股 tab 新增开关和阈值，compareFields 同步

**Tech Stack:** Python 3.14+, FastAPI, Beanie ODM, Vue 3 + Vuetify

---

## 文件结构

| 文件 | 改动 |
|------|------|
| `backend/src/trade_alpha/dao/strategy_config.py` | 新增 `use_ma_trend_filter`、`ma_trend_ratio_threshold` |
| `backend/src/trade_alpha/dao/execution.py` | StrategySnapshotEmbed 同步新增 2 个字段 |
| `backend/src/trade_alpha/execution/candidate_list_provider.py` | `__init__` 读取配置 + `_get_candidates` 末尾加过滤 |
| `backend/src/trade_alpha/api/schemas.py` | CreateRequest + UpdateRequest 各加 2 个字段 |
| `frontend/src/api/strategyConfig.ts` | TS 接口 + 2 字段 |
| `frontend/src/views/StrategyConfigView.vue` | 选股 tab UI + form 默认值 + 保存/编辑 + compareFields |
| `frontend/src/views/BacktestRecordsView.vue` | compareFields 新增 2 条 |

---

### Task 1: 后端 DAO 加字段

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py` — 在 `sel_` 段落后、`分数加权` 前新增
- Modify: `backend/src/trade_alpha/dao/execution.py` — StrategySnapshotEmbed 同步新增

- [ ] **Step 1: strategy_config.py 加字段**

在 `sel_ewma_alpha` 之后、`# ── 分数加权 ──` 之前插入：

```python
    # ── 趋势过滤 ──
    use_ma_trend_filter: bool = False
    ma_trend_ratio_threshold: float = 1.0
```

- [ ] **Step 2: execution.py StrategySnapshotEmbed 同步**

在 StrategySnapshotEmbed 类中对应位置新增相同 2 个字段：

```python
    use_ma_trend_filter: bool = False
    ma_trend_ratio_threshold: float = 1.0
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/dao/strategy_config.py backend/src/trade_alpha/dao/execution.py
git commit -m "feat(dao): add ma_trend_filter fields to strategy config"
```

---

### Task 2: API Schema 加字段

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py`

- [ ] **Step 1: CreateRequest 新增**

在 CreateRequest 的 `use_hold_protection` 行后追加：

```python
    use_ma_trend_filter: Optional[bool] = False
    ma_trend_ratio_threshold: Optional[float] = 1.0
```

- [ ] **Step 2: UpdateRequest 新增**

在 UpdateRequest 的 `use_hold_protection` 行后追加：

```python
    use_ma_trend_filter: Optional[bool] = None
    ma_trend_ratio_threshold: Optional[float] = None
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/api/schemas.py
git commit -m "feat(api): add ma_trend_filter to strategy config schemas"
```

---

### Task 3: 候选池过滤逻辑

**Files:**
- Modify: `backend/src/trade_alpha/execution/candidate_list_provider.py`

- [ ] **Step 1: `__init__` 读取配置**

在 `self._use_hold_protection` 行后追加：

```python
        self._use_ma_trend_filter = strategy_config.use_ma_trend_filter
        self._ma_trend_ratio_threshold = strategy_config.ma_trend_ratio_threshold
```

- [ ] **Step 2: `_get_candidates` 末尾加过滤**

在 `result[resolved] = final` 行之前，即计算出 final 之后插入过滤逻辑：

```python
            # Apply MA trend filter: exclude stocks where MA5/MA60 < threshold
            if self._use_ma_trend_filter and final:
                ma_records = await StockDaily.find(
                    StockDaily.trade_date == resolved,
                    In(StockDaily.ts_code, final),
                    StockDaily.ma_5 != None,
                    StockDaily.ma_60 != None,
                ).to_list()
                valid_codes = set()
                for r in ma_records:
                    if r.ma_5 and r.ma_60 and r.ma_60 > 0:
                        ratio = r.ma_5 / r.ma_60
                        if ratio >= self._ma_trend_ratio_threshold:
                            valid_codes.add(r.ts_code)
                    else:
                        valid_codes.add(r.ts_code)
                # Keep stocks that passed filter or had no MA data
                final = [ts for ts in final if ts in valid_codes]
```

注意：`In` 已经 import 了（`from beanie.odm.operators.find.comparison import In`）。

- [ ] **Step 3: 验证语法**

```bash
D:\projects\trade-alpha\backend\.venv\Scripts\python.exe -c "import ast; ast.parse(open('src/trade_alpha/execution/candidate_list_provider.py').read()); print('OK')"
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/execution/candidate_list_provider.py
git commit -m "feat: add MA trend filter to candidate pool final list"
```

---

### Task 4: 前端类型定义

**Files:**
- Modify: `frontend/src/api/strategyConfig.ts`

- [ ] **Step 1: Strategy 接口新增 2 个字段**

找到 `use_hold_protection?: boolean` 行，在它之后新增：

```typescript
  use_ma_trend_filter?: boolean
  ma_trend_ratio_threshold?: number
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/strategyConfig.ts
git commit -m "feat(frontend): add ma_trend_filter types"
```

---

### Task 5: 前端选股 Tab UI

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue`

需要在 4 个位置新增字段：
1. 选股 tab 的 template（开关 + 阈值输入框）
2. form 默认值
3. compareFields 数组
4. load 回显（edit 时取值）
5. 保存时构造 body

- [ ] **Step 1: Template 新增 UI**

在持仓保护 switch 之后插入（约 line 604）：

```html
                <v-col cols="12" md="6">
                  <v-switch v-model="form.use_ma_trend_filter" color="primary"
                    label="MA下降趋势过滤" hint="剔除MA5低于MA60超过阈值的下降趋势股" persistent-hint />
                </v-col>
                <v-col cols="12" md="6" v-if="form.use_ma_trend_filter">
                  <v-text-field v-model.number="form.ma_trend_ratio_threshold" type="number" step="0.01" min="0.5" max="1.5"
                    label="趋势比率阈值" hint="MA5/MA60 < 此值时剔除（默认1.0）" persistent-hint />
                </v-col>
```

- [ ] **Step 2: form 默认值**

在 `use_hold_protection: false,` 之后新增：

```typescript
  use_ma_trend_filter: false,
  ma_trend_ratio_threshold: 1.0,
```

- [ ] **Step 3: compareFields 数组**

在选股配置组的对应位置新增：

```typescript
  { key: 'use_ma_trend_filter', label: 'MA下降趋势过滤', group: '选股配置', type: 'boolean' },
  { key: 'ma_trend_ratio_threshold', label: '趋势比率阈值', group: '选股配置', type: 'number' },
```

- [ ] **Step 4: load 回显**

在 `use_hold_protection: item.use_hold_protection ?? false,` 之后新增：

```typescript
      use_ma_trend_filter: item.use_ma_trend_filter ?? false,
      ma_trend_ratio_threshold: item.ma_trend_ratio_threshold ?? 1.0,
```

- [ ] **Step 5: save body（POST）**

在 `use_hold_protection: form.value.type === 'multi' ? form.value.use_hold_protection : undefined,` 之后新增：

```typescript
      use_ma_trend_filter: form.value.type === 'multi' ? form.value.use_ma_trend_filter : undefined,
      ma_trend_ratio_threshold: form.value.type === 'multi' ? form.value.ma_trend_ratio_threshold : undefined,
```

- [ ] **Step 6: save body（PUT）**

在 `use_hold_protection: form.value.type === 'multi' ? form.value.use_hold_protection : undefined,` 之后新增（第二个保存函数）：

```typescript
      use_ma_trend_filter: form.value.type === 'multi' ? form.value.use_ma_trend_filter : undefined,
      ma_trend_ratio_threshold: form.value.type === 'multi' ? form.value.ma_trend_ratio_threshold : undefined,
```

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/StrategyConfigView.vue
git commit -m "feat(frontend): add MA trend filter UI in strategy config"
```

---

### Task 6: compareFields 同步

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: compareFields 新增**

在选股配置组的对应位置找到 `{ key: 'use_hold_protection', ... }`，在它之后新增：

```typescript
  { key: 'use_ma_trend_filter', label: 'MA下降趋势过滤', group: '选股配置', type: 'boolean' },
  { key: 'ma_trend_ratio_threshold', label: '趋势比率阈值', group: '选股配置', type: 'number' },
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/BacktestRecordsView.vue
git commit -m "feat(frontend): add MA trend filter to compareFields"
```

---

### Task 7: 重启 + 验证

- [ ] **Step 1: 重启服务**

```powershell
cd D:\projects\trade-alpha; .\service.bat restart
```

- [ ] **Step 2: 验证策略配置 CRUD**

通过前端界面创建一个新策略配置，开启 MA 趋势过滤开关、设置阈值，保存后编辑确认值正确。

- [ ] **Step 3: 提交**

```bash
git add -A; git commit -m "feat: add MA trend filter for downtrend stock exclusion"
```
