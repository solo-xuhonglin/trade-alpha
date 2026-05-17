# 训练流程简化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 简化训练主流程，去掉内层按月循环，改为按年加载→按年标准化→按年累积→一次性训练

**Architecture:** 只修改 `training_service.py` 一个文件，删除内层 `for month` 循环，将 `_normalize_month` 重命名为通用 `_normalize_data`，简化进度回调为按年维度

**Tech Stack:** Python, pandas, numpy

---

### Task 1: 修改 `training_service.py` — 主流程简化

**Files:**
- Modify: `backend/src/trade_alpha/predict/training_service.py`

- [ ] **Step 1: 重命名 `_normalize_month` 为 `_normalize_data`**

将函数名和所有调用处更新：

```python
# 原函数
def _normalize_month(df: pd.DataFrame, config) -> Optional[pd.DataFrame]:

# 改为
def _normalize_data(df: pd.DataFrame, config) -> Optional[pd.DataFrame]:
```

- [ ] **Step 2: 简化主流程 `create_training()` 中的循环**

删除内层 `for month` 循环，改为对整年数据做一次标准化后 append：

```python
    # 删除这些变量声明
    target_names = [f"label_{h}d" for h in config.classification_horizons]
    all_ts_codes = []
    all_X = []
    all_y = []
    all_targets = None

    for year_idx, year in enumerate(years):
        year_num = year_idx + 1

        # 加载
        stage += 1
        update(stage, format_progress("load", year, idx=year_num, total=total_years))
        year_df = await _load_year_data(year, ts_codes, horizon)
        if year_df is None:
            continue

        # 计算标签
        stage += 1
        update(stage, format_progress("label", year, idx=year_num, total=total_years))
        year_df = _create_classification_labels(year_df, config.classification_horizons, config.classification_threshold)

        # 整年统一标准化
        year_norm = _normalize_data(year_df, config)
        if year_norm is not None and not year_norm.empty:
            available_features = [f for f in config.feature_fields if f in year_norm.columns]
            available_targets = [t for t in target_names if t in year_norm.columns]
            if all_targets is None:
                all_targets = available_targets
            all_X.append(year_norm[available_features].values)
            all_y.append(year_norm[available_targets].values)

        # 收集活跃股票代码
        year_ts_codes = sorted(year_df["ts_code"].unique())
        all_ts_codes.extend([c for c in year_ts_codes if c not in all_ts_codes])
```

具体替换代码（当前对应第 144-177 行）——删除内层 `for (y, month) in year_month_list:` 循环及其内部代码，替换为上述整年标准化逻辑。

- [ ] **Step 3: 添加 `sample_count` 累加**

在 `np.vstack` 后计算 sample_count：

```python
    X = np.vstack(all_X)
    y = np.vstack(all_y) if len(all_y) > 1 else all_y[0]
    sample_count = len(X)
```

- [ ] **Step 4: 验证修改后文件语法正确**

Run: `D:/projects/trade-alpha/backend/.venv/Scripts/python.exe -c "import ast; ast.parse(open('D:/projects/trade-alpha/backend/src/trade_alpha/predict/training_service.py').read()); print('OK')"`

Expected: OK

### Task 2: 测试验证

- [ ] **Step 1: 运行测试脚本验证训练成功**

Run: `D:/projects/trade-alpha/backend/.venv/Scripts/python.exe D:/projects/trade-alpha/backend/scripts/test_training_small.py`

Expected: 训练成功完成，进度显示简洁（只显示加载/标签/训练完成三个阶段的进度）

- [ ] **Step 2: 清理临时测试文件**

```bash
del D:\projects\trade-alpha\test_training.py
del D:\projects\trade-alpha\test_training2.py
del D:\projects\trade-alpha\check_data.py
del D:\projects\trade-alpha\check_data2.py
del D:\projects\trade-alpha\wait_server.py
```
