# 训练和回测进度优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现细粒度的训练和回测进度显示，训练按年/月阶段更新，回测按月更新

**Architecture:** 
- 后端：Task模型新增progress_message字段，日期工具类，训练流程重构
- 前端：显示进度文字信息

---

## 文件结构

| 操作 | 文件 |
|------|------|
| 新建 | `backend/src/trade_alpha/utils/__init__.py` |
| 新建 | `backend/src/trade_alpha/utils/date_utils.py` |
| 修改 | `backend/src/trade_alpha/dao/task.py` |
| 修改 | `backend/src/trade_alpha/predict/training_service.py` |
| 修改 | `backend/src/trade_alpha/api/routers/trainings.py` |
| 修改 | `backend/src/trade_alpha/execution/pipeline.py` |
| 修改 | `backend/src/trade_alpha/api/routers/backtest.py` |
| 修改 | `frontend/src/api/training.ts` |
| 修改 | `frontend/src/api/backtest.ts` |
| 修改 | `frontend/src/views/TrainingManageView.vue` |
| 修改 | `frontend/src/views/BacktestManageView.vue` |

---

## Task 1: 创建日期工具类

**Files:**
- Create: `d:\projects\trade-alpha\backend\src\trade_alpha\utils\__init__.py`
- Create: `d:\projects\trade-alpha\backend\src\trade_alpha\utils\date_utils.py`

- [ ] **Step 1: 创建__init__.py**

```python
from .date_utils import get_year_months, format_progress
```

- [ ] **Step 2: 创建date_utils.py**

```python
"""日期工具函数"""

from typing import List, Tuple


def get_year_months(start_date: str, end_date: str) -> List[Tuple[int, int]]:
    """获取年月列表，支持任意起止日期"""
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    start_month = int(start_date[4:6]) if len(start_date) >= 6 else 1
    end_month = int(end_date[4:6]) if len(end_date) >= 6 else 12
    
    result = []
    for year in range(start_year, end_year + 1):
        m_start = start_month if year == start_year else 1
        m_end = end_month if year == end_year else 12
        for month in range(m_start, m_end + 1):
            result.append((year, month))
    return result


def format_progress(stage: str, year: int, month: int = None, idx: int = 1, total: int = 1) -> str:
    """格式化进度消息"""
    msg_map = {
        "load": f"正在加载{year}年数据 ({idx}/{total})",
        "label": f"正在计算{year}年标签 ({idx}/{total})",
        "norm": f"正在标准化{year}年{month:02d}月 ({idx}/{total})",
        "train": f"正在训练{year}年{month:02d}月 ({idx}/{total})",
        "backtest": f"正在回测{year}年{month:02d}月 ({idx}/{total})",
        "done": "训练完成",
    }
    return msg_map.get(stage, f"处理中 {year}年{month or ''}")
```

- [ ] **Step 3: 验证**

---

## Task 2: Task模型添加progress_message字段

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\dao\task.py`

- [ ] **Step 1: 读取task.py**

- [ ] **Step 2: 添加progress_message字段**

```python
class Task(Document):
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    progress_message: Optional[str] = None
    result_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = datetime.now()
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    params: Dict[str, Any] = {}
```

---

## Task 3: 重构training_service.py

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\predict\training_service.py`

- [ ] **Step 1: 读取training_service.py**

- [ ] **Step 2: 添加导入**

```python
from trade_alpha.utils.date_utils import get_year_months, format_progress
```

- [ ] **Step 3: 新增子函数**

在 `_create_classification_labels` 后添加：

```python
async def _load_year_data(year: int, ts_codes: List[str], horizon: int) -> Optional[pd.DataFrame]:
    """加载指定年份数据（含未来horizon天）"""
    year_start = f"{year}0101"
    year_end = f"{year}1231"
    future_end = f"{year + (horizon + 180) // 365}1231"
    
    year_dfs = []
    for ts_code in ts_codes:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if not stock or stock.sync_status != "active":
            continue
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= year_start,
            StockDaily.trade_date <= future_end,
        ).sort(StockDaily.trade_date).to_list()
        if not records:
            continue
        df = pd.DataFrame([r.model_dump() for r in records])
        df["ts_code"] = ts_code
        year_dfs.append(df)
    
    return pd.concat(year_dfs, ignore_index=True) if year_dfs else None


def _normalize_month(df: pd.DataFrame, config) -> Optional[pd.DataFrame]:
    """标准化单月数据"""
    normalizer = CrossSectionalNormalizer(
        standardize_fields=config.standardize_fields,
        winsorize_fields=config.winsorize_fields,
        output_fields=config.output_fields,
    )
    target_names = [f"label_{h}d" for h in config.classification_horizons]
    df_norm = normalizer.normalize(df[config.feature_fields + target_names + ["trade_date", "ts_code"]])
    return df_norm.dropna(subset=config.feature_fields + target_names)


def _create_classifier(config) -> any:
    """创建分类器"""
    if config.model_type == "xgboost":
        return XGBoostClassifier(
            n_estimators=config.xgb_n_estimators,
            max_depth=config.xgb_max_depth,
            learning_rate=config.xgb_learning_rate,
            min_child_weight=config.xgb_min_child_weight,
            subsample=config.xgb_subsample,
            colsample_bytree=config.xgb_colsample_bytree,
        )
    return CLASSIFIERS[config.model_type]()
```

- [ ] **Step 4: 重写create_training主函数**

```python
async def create_training(
    config_id: PydanticObjectId,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
    progress_callback: Optional[callable] = None,
) -> TrainingResult:
    """训练流程：逐年加载→逐年计算标签→逐月标准化训练"""
    existing = await get_training_by_name(name)
    if existing:
        raise ValueError(f"Training already exists: {name}")

    config = await get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    if config.model_type not in CLASSIFIERS:
        raise ValueError(f"Unsupported model type: {config.model_type}")

    year_months = get_year_months(start_date, end_date)
    years = sorted(set(y for y, _ in year_months))
    total_years = len(years)
    total_stages = sum(1 + 1 + len([m for y, m in year_months if y == year]) * 2 for year in years)

    def update(stage_num: int, msg: str):
        if progress_callback:
            progress_callback(stage_num / total_stages * 100, msg)

    stage = 0
    classifier = None
    horizon = max(config.classification_horizons)
    target_names = [f"label_{h}d" for h in config.classification_horizons]

    for year_idx, year in enumerate(years):
        year_num = year_idx + 1
        
        # 加载year年数据（含未来horizon天）
        stage += 1
        update(stage, format_progress("load", year, idx=year_num, total=total_years))
        year_df = await _load_year_data(year, ts_codes, horizon)
        if year_df is None:
            continue

        # 计算year年标签（按年一次性计算）
        stage += 1
        update(stage, format_progress("label", year, idx=year_num, total=total_years))
        year_df = _create_classification_labels(year_df, config.classification_horizons, config.classification_threshold)

        year_month_list = [(y, m) for y, m in year_months if y == year]

        for (y, month) in year_month_list:
            # 标准化month月
            stage += 1
            update(stage, format_progress("norm", y, month, idx=year_num, total=total_years))
            month_df = year_df[year_df["trade_date"].astype(str).str.startswith(f"{y}-{month:02d}")]
            if month_df.empty:
                continue
            month_norm = _normalize_month(month_df, config)

            # 训练month月
            stage += 1
            update(stage, format_progress("train", y, month, idx=year_num, total=total_years))
            X = month_norm[config.feature_fields].values
            y_data = month_norm[target_names].values
            
            if classifier is None:
                classifier = _create_classifier(config)
                classifier.fit(X, y_data, target_names)
            else:
                classifier.partial_fit(X, y_data, target_names)

    if classifier is None:
        raise ValueError("No available data")

    update(total_stages, format_progress("done", 2024))

    _ensure_model_dir(str(config_id))
    model_path = os.path.join(MODELS_DIR, str(config_id), f"{name}.pkl")
    classifier.save(model_path)

    training = TrainingResult(
        config_id=config_id, name=name, ts_codes=ts_codes,
        start_date=start_date, end_date=end_date,
        metrics={}, model_path=model_path,
        created_at=datetime.now(timezone.utc),
    )
    await training.insert()
    return training
```

---

## Task 4: 更新trainings.py路由

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\api\routers\trainings.py`

- [ ] **Step 1: 修改run_training_async**

```python
async def run_training_async(task_id: str):
    from trade_alpha.logging import get_logger
    logger = get_logger("training.task")
    task = await Task.get(PydanticObjectId(task_id))
    if not task:
        return

    async def update_progress(progress: float, message: str):
        task.progress = progress
        task.progress_message = message
        await task.save()

    try:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.progress = 0.0
        task.progress_message = "正在初始化..."
        await task.save()

        params = task.params
        training = await training_service.create_training(
            config_id=PydanticObjectId(params["config_id"]),
            name=params["name"],
            ts_codes=params["ts_codes"],
            start_date=params["start_date"],
            end_date=params["end_date"],
            progress_callback=update_progress,
        )

        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.progress_message = "训练完成"
        task.result_id = str(training.id)
        task.completed_at = datetime.now()
        await task.save()

    except Exception as e:
        logger.error(f"Training task {task_id} failed: {e}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        task.progress_message = f"训练失败: {str(e)}"
        await task.save()
```

- [ ] **Step 2: 修改get_training_task响应**

```python
return {
    "task_id": task_id,
    "status": task.status.value,
    "progress": task.progress,
    "progress_message": task.progress_message,
    "training": training.dict() if training else None,
    "error_message": task.error_message,
    "created_at": task.created_at,
    "started_at": task.started_at,
    "completed_at": task.completed_at,
}
```

---

## Task 5: 更新pipeline.py回测进度

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\execution\pipeline.py`

- [ ] **Step 1: 添加导入**

```python
from trade_alpha.utils.date_utils import get_year_months, format_progress
```

- [ ] **Step 2: 修改run_backtest签名**

```python
def run_backtest(self, start_date: str, end_date: str, name: str = "backtest",
                 progress_callback: Optional[callable] = None):
    year_months = get_year_months(start_date, end_date)
    total_months = len(year_months)
    last_idx = 0
    
    # while date循环中：
    # 每进入新月时：
    for idx, (y, m) in enumerate(year_months):
        if y == current_year and m == current_month and idx >= last_idx:
            last_idx = idx + 1
            if progress_callback:
                progress_callback(last_idx / total_months * 100,
                    format_progress("backtest", y, m, idx=last_idx, total=total_months))
            break
```

---

## Task 6: 更新backtest.py路由

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\api\routers\backtest.py`

- [ ] **Step 1: 修改run_backtest_async（参考trainings.py模式）**

- [ ] **Step 2: 修改get_backtest_task响应**

```python
return {
    "task_id": task_id,
    "status": task.status.value,
    "progress": task.progress,
    "progress_message": task.progress_message,
    "result": _execution_to_dict(result) if result else None,
    "error_message": task.error_message,
    "created_at": task.created_at,
    "started_at": task.started_at,
    "completed_at": task.completed_at,
}
```

---

## Task 7-10: 前端改动

**Files:**
- `frontend/src/api/training.ts` - 添加 `progress_message` 字段
- `frontend/src/api/backtest.ts` - 添加 `progress_message` 字段
- `frontend/src/views/TrainingManageView.vue` - 进度列显示 `progress_message`
- `frontend/src/views/BacktestManageView.vue` - 进度列显示 `progress_message`

```vue
<template v-slot:item.progress="{ item }">
  <div class="d-flex flex-column">
    <span class="text-body-2">{{ item.progress_message || `${item.progress.toFixed(1)}%` }}</span>
    <v-progress-linear :value="item.progress" height="4" class="mt-1" />
  </div>
</template>
```

---

## 自检清单

- [x] 工具类简洁，只有2个函数，被使用
- [x] 主流程清晰：逐年加载→逐年计算标签→逐月标准化训练
- [x] 标签按年计算（因为需要加载未来horizon天）
- [x] 只保存一个模型，用partial_fit递增训练
- [x] 语法正确
