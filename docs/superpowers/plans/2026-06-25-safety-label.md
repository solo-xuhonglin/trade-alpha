# 安全标签训练模式 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增 `label_mode="safety"`，训练模型预测股票 N 日内不跌破开盘价的概率

**范围:** 改后端 `helpers.py`(加一个函数+分支) + 前端 `ModelConfigView.vue`(加选项)

---

### Task 1: 后端 — 新增标签函数

**Files:**
- Modify: `backend/src/trade_alpha/models/training/helpers.py`

- [ ] **Step 1: 在 `_create_trend_labels` 之后、`create_labels` 之前插入**

```python
def _create_safety_labels(df: pd.DataFrame, horizons: List[int]) -> pd.DataFrame:
    """Create safety labels: does stock price stay above open price in horizon days?

    Label = 1  (safe):  min_close[T+1:T+h] >= open[T]
    Label = -1 (risky): min_low[T+1:T+h]  <  open[T] * 0.95
    Label = 0  (neutral): otherwise
    """
    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()
        for horizon in horizons:
            min_close = group["close"].rolling(horizon).min().shift(-horizon)
            min_low = group["low"].rolling(horizon).min().shift(-horizon)
            col = f"label_{horizon}d"
            group[col] = 0
            group.loc[min_close >= group["open"], col] = 1
            group.loc[min_low < group["open"] * 0.95, col] = -1
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)
```

- [ ] **Step 2: `create_labels` 增加分支**

替换现有函数为：

```python
def create_labels(df: pd.DataFrame, horizons: List[int], label_mode: str = "threshold", threshold_3d: float = 0.01, threshold_5d: float = 0.015, threshold_10d: float = 0.02, threshold_20d: float = 0.05) -> pd.DataFrame:
    if label_mode == "trend":
        return _create_trend_labels(df, horizons, threshold_3d, threshold_5d, threshold_10d, threshold_20d)
    if label_mode == "safety":
        return _create_safety_labels(df, horizons)
    return _create_classification_labels(df, horizons, threshold_3d, threshold_5d, threshold_10d, threshold_20d)
```

- [ ] **Step 3: 验证语法**

```bash
D:\projects\trade-alpha\backend\.venv\Scripts\python.exe -c "import ast; ast.parse(open(r'backend/src/trade_alpha/models/training/helpers.py').read()); print('OK')"
```

- [ ] **Step 4: 提交后端**

```bash
git add backend/src/trade_alpha/models/training/helpers.py
git commit -m "feat: add safety label training mode"
```

---

### Task 2: 前端 — 下拉选项加 safety

**Files:**
- Modify: `frontend/src/views/ModelConfigView.vue`

- [ ] **Step 1: label_mode 选择器加 `safety` 选项**

```html
<v-select v-model="form.label_mode" :items="[
  { title: '涨跌幅阈值', value: 'threshold' },
  { title: '均线趋势', value: 'trend' },
  { title: '规避风险', value: 'safety' }
]" label="标签计算模式"
  hint="threshold: 基于未来涨跌幅; trend: 基于均线+涨跌幅; safety: 基于最低价是否跌破开盘价" persistent-hint></v-select>
```

- [ ] **Step 2: 提交前端**

```bash
git add frontend/src/views/ModelConfigView.vue
git commit -m "feat(frontend): add safety label mode option"
```

### Task 3: 验证

- [ ] **Step 1: 重启服务**

```bash
cd D:\projects\trade-alpha; .\service.bat restart
```

前端打开模型配置页，标签计算模式下拉应看到 3 个选项。
