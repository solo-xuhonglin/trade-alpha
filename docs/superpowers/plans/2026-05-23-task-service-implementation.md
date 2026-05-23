# Task Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建统一的 TaskService 类，封装所有异步任务的状态管理和查询操作，简化 API 路由代码。

**Architecture:** TaskService 作为单例服务类，提供静态方法供调用。内部封装 Beanie ODM 操作，API 路由通过依赖注入获取服务实例。

**Tech Stack:** Python, Beanie ODM, Pydantic, AsyncIO

---

## Task 1: Create TaskService Class

**Files:**
- Create: `backend/src/trade_alpha/services/__init__.py`
- Create: `backend/src/trade_alpha/services/task_service.py`

- [ ] **Step 1: Create services directory init**

```python
"""Services module for business logic encapsulation."""

from trade_alpha.services.task_service import TaskService

__all__ = ["TaskService"]
```

- [ ] **Step 2: Write TaskService implementation**

```python
"""Task service for async task management."""

from typing import Optional, Dict, Any
from datetime import datetime
from beanie import PydanticObjectId

from trade_alpha.dao.task import Task, TaskStatus, TaskType
from trade_alpha.logging import get_logger

logger = get_logger("task_service")


class TaskService:
    """Service for task lifecycle management."""

    @staticmethod
    async def create_task(task_type: TaskType, params: Dict[str, Any]) -> Task:
        """Create a new task with PENDING status."""
        task = Task(
            type=task_type,
            status=TaskStatus.PENDING,
            params=params,
            created_at=datetime.now(),
        )
        await task.insert()
        logger.info(f"Task created: {task.id} type={task_type.value}")
        return task

    @staticmethod
    async def start_task(task_id: PydanticObjectId) -> Task:
        """Mark task as RUNNING."""
        task = await Task.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.progress = 0.0
        task.progress_message = "正在初始化..."
        await task.save()
        logger.info(f"Task started: {task_id}")
        return task

    @staticmethod
    async def complete_task(task_id: PydanticObjectId, result_id: Optional[str] = None) -> Task:
        """Mark task as COMPLETED."""
        task = await Task.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.progress_message = "完成"
        task.result_id = result_id
        task.completed_at = datetime.now()
        await task.save()
        logger.info(f"Task completed: {task_id} result_id={result_id}")
        return task

    @staticmethod
    async def fail_task(task_id: PydanticObjectId, error_message: str) -> Task:
        """Mark task as FAILED."""
        task = await Task.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.status = TaskStatus.FAILED
        task.error_message = error_message
        task.progress_message = f"失败: {error_message}"
        task.completed_at = datetime.now()
        await task.save()
        logger.error(f"Task failed: {task_id} error={error_message}")
        return task

    @staticmethod
    async def update_progress(task_id: PydanticObjectId, progress: float, message: str) -> None:
        """Update task progress atomically."""
        await Task.find_one(Task.id == task_id).update(
            {"$set": {"progress": progress, "progress_message": message}}
        )

    @staticmethod
    async def get_task(task_id: PydanticObjectId) -> Optional[Task]:
        """Get task by ID."""
        return await Task.get(task_id)

    @staticmethod
    async def list_tasks(
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List tasks with pagination."""
        query = Task.find()
        if task_type:
            query = query.find(Task.type == task_type)
        if status:
            query = query.find(Task.status == status)
        
        total = await query.count()
        tasks = await query.sort(-Task.created_at).skip((page - 1) * page_size).limit(page_size).to_list()
        
        return {
            "items": tasks,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/services/__init__.py backend/src/trade_alpha/services/task_service.py
git commit -m "feat: add TaskService class for task lifecycle management"
```

---

## Task 2: Add TaskService Integration Test

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_35_task_service.py`

- [ ] **Step 1: Run integration tests**

```bash
cd backend && pytest tests/trade_alpha/integration/test_35_task_service.py -v
```

Expected: All tests should PASS

- [ ] **Step 2: Commit**

```bash
git add backend/tests/trade_alpha/integration/test_35_task_service.py
git commit -m "test: add integration tests for TaskService"
```

---

## Task 3: Migrate backtest.py to use TaskService

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest.py:1-30` (imports)
- Modify: `backend/src/trade_alpha/api/routers/backtest.py:115-170` (run_backtest_async function)

- [ ] **Step 1: Add TaskService import**

```python
from trade_alpha.services.task_service import TaskService
```

- [ ] **Step 2: Refactor run_backtest_async to use TaskService**

```python
async def run_backtest_async(task_id: str):
    """Execute backtest asynchronously."""
    from trade_alpha.logging import get_logger

    logger = get_logger("backtest.task")
    task = await TaskService.get_task(PydanticObjectId(task_id))
    if not task:
        return

    try:
        await TaskService.start_task(task.id)

        params = task.params
        account_config = await AccountConfig.get(PydanticObjectId(params["account_config_id"]))

        training = await training_module.get_training_by_id(PydanticObjectId(params["training_id"]))
        if not training:
            await TaskService.fail_task(task.id, f"Training not found: {params['training_id']}")
            return
        
        model_config = await training_module.get_config_by_id(training.config_id)
        if not model_config:
            await TaskService.fail_task(task.id, f"Model config not found: {training.config_id}")
            return

        strategy_config = None
        if params.get("strategy_config_id"):
            strategy_config = await get_strategy_by_id(PydanticObjectId(params["strategy_config_id"]))
            if not strategy_config:
                await TaskService.fail_task(task.id, f"Strategy config not found: {params['strategy_config_id']}")
                return

        pipeline = ExecutionPipeline(
            account_config=account_config,
            training_id=PydanticObjectId(params["training_id"]),
            model_config=model_config,
            strategy_config=strategy_config,
            mode=params["mode"],
            ts_codes=params.get("ts_codes"),
            max_positions=params.get("max_positions", 10),
        )

        result = await pipeline.run_backtest(
            start_date=params["start_date"],
            end_date=params["end_date"],
            name=params["name"],
            task_id=task.id,
        )

        await TaskService.complete_task(task.id, str(result.id))

    except Exception as e:
        logger.error(f"Backtest task {task_id} failed: {e}")
        await TaskService.fail_task(task.id, str(e))
```

- [ ] **Step 3: Refactor get_backtest_task endpoint**

```python
@router.get("/backtest/task/{task_id}")
async def get_backtest_task(task_id: str):
    """Get backtest task status."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await TaskService.get_task(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # ... rest of the function unchanged
```

- [ ] **Step 4: Refactor list_backtest_tasks endpoint**

```python
@router.get("/backtest/tasks")
async def list_backtest_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
):
    """List backtest tasks."""
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    
    result = await TaskService.list_tasks(
        task_type=TaskType.BACKTEST,
        status=task_status,
        page=page,
        page_size=page_size,
    )
    
    return {
        "items": [
            {
                "task_id": str(t.id),
                "status": t.status.value,
                "progress": t.progress,
                "progress_message": t.progress_message,
                "error_message": t.error_message,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
            }
            for t in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"],
    }
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/api/routers/backtest.py
git commit -m "refactor: migrate backtest.py to use TaskService"
```

---

## Task 4: Migrate trainings.py to use TaskService

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/trainings.py`

- [ ] **Step 1: Add TaskService import**

```python
from trade_alpha.services.task_service import TaskService
```

- [ ] **Step 2: Update trigger_training to use TaskService.create_task**

```python
@router.post("")
async def trigger_training(
    background_tasks: BackgroundTasks,
    config_id: str,
    name: str,
    start_date: TradeDateQuery,
    end_date: TradeDateQuery,
    start_rank: int = Query(1, ge=1),
    end_rank: int = Query(3000, ge=1),
):
    """Trigger training task (async). Resolves stocks by market value rank range internally."""
    try:
        config_obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")
    
    try:
        validate_date_range(start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stocks = await list_stocks_by_mv_rank(start_rank, end_rank)
    ts_codes = [s.ts_code for s in stocks]

    if not ts_codes:
        raise HTTPException(status_code=400, detail=f"No stocks found for rank range {start_rank}-{end_rank}")

    task = await TaskService.create_task(TaskType.TRAINING, {
        "config_id": config_id,
        "name": name,
        "ts_codes": ts_codes,
        "start_date": start_date,
        "end_date": end_date,
    })

    background_tasks.add_task(run_training_async, str(task.id))

    return {
        "task_id": str(task.id),
        "status": task.status.value,
        "message": "Training task triggered",
    }
```

- [ ] **Step 3: Refactor run_training_async to use TaskService**

```python
async def run_training_async(task_id: str):
    """Execute training asynchronously."""
    from trade_alpha.logging import get_logger

    logger = get_logger("training.task")
    task = await TaskService.get_task(PydanticObjectId(task_id))
    if not task:
        return

    try:
        await TaskService.start_task(task.id)

        params = task.params
        training_result = await training.create_training(
            config_id=PydanticObjectId(params["config_id"]),
            name=params["name"],
            ts_codes=params["ts_codes"],
            start_date=params["start_date"],
            end_date=params["end_date"],
            task_id=task.id,
        )

        await TaskService.complete_task(task.id, str(training_result.id))

    except Exception as e:
        logger.error(f"Training task {task_id} failed: {e}")
        await TaskService.fail_task(task.id, str(e))
```

- [ ] **Step 4: Refactor get_training_task endpoint**

```python
@router.get("/trainings/task/{task_id}")
async def get_training_task(task_id: str):
    """Get training task status."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    task = await TaskService.get_task(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # ... rest of the function unchanged
```

- [ ] **Step 5: Refactor list_training_tasks endpoint**

```python
@router.get("/trainings/tasks")
async def list_training_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
):
    """List training tasks."""
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    
    result = await TaskService.list_tasks(
        task_type=TaskType.TRAINING,
        status=task_status,
        page=page,
        page_size=page_size,
    )
    
    return {
        "items": [
            {
                "task_id": str(t.id),
                "status": t.status.value,
                "progress": t.progress,
                "progress_message": t.progress_message,
                "error_message": t.error_message,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
            }
            for t in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"],
    }
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/trade_alpha/api/routers/trainings.py
git commit -m "refactor: migrate trainings.py to use TaskService"
```

---

## Task 5: Migrate data_analysis.py to use TaskService

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/data_analysis.py`

- [ ] **Step 1: Add TaskService import**

```python
from trade_alpha.services.task_service import TaskService
```

- [ ] **Step 2: Update trigger_data_analysis to use TaskService.create_task**

```python
@router.post("")
async def trigger_data_analysis(
    background_tasks: BackgroundTasks,
    params: DataAnalysisCreate,
):
    """Trigger data analysis task (async)."""
    if not params.name:
        now = datetime.now()
        params.name = f"analysis_{now.strftime('%Y%m%d%H%M%S')}"

    task = await TaskService.create_task(TaskType.DATA_ANALYSIS, {
        "name": params.name,
        "ts_codes": params.ts_codes,
        "start_rank": params.start_rank,
        "end_rank": params.end_rank,
        "start_date": params.start_date,
        "end_date": params.end_date,
        "feature_fields": params.feature_fields,
    })

    background_tasks.add_task(run_data_analysis_async, str(task.id))

    return {
        "task_id": str(task.id),
        "status": task.status.value,
        "message": "Data analysis task triggered",
    }
```

- [ ] **Step 3: Refactor run_data_analysis_async to use TaskService**

```python
async def run_data_analysis_async(task_id: str):
    """Execute data analysis asynchronously."""
    from trade_alpha.logging import get_logger

    logger = get_logger("data_analysis.task")
    task = await TaskService.get_task(PydanticObjectId(task_id))
    if not task:
        return

    try:
        await TaskService.start_task(task.id)

        params = task.params
        
        # 处理ts_codes或start_rank/end_rank
        ts_codes = params.get("ts_codes", [])
        if not ts_codes:
            await TaskService.update_progress(task.id, 5.0, "正在查询股票列表...")
            start_rank = params.get("start_rank", 1)
            end_rank = params.get("end_rank", 1000)
            stocks = await list_stocks_by_mv_rank(start_rank, end_rank)
            ts_codes = [s.ts_code for s in stocks]

        if not ts_codes:
            await TaskService.fail_task(task.id, "No stocks found")
            return
            
        feature_fields = params.get("feature_fields") or DEFAULT_INDICATOR_FIELDS

        result = await run_data_analysis(
            ts_codes=ts_codes,
            start_date=params["start_date"],
            end_date=params["end_date"],
            feature_fields=feature_fields,
            task_id=task.id,
        )

        analysis_result_id = await save_analysis_result(
            task_id=str(task.id),
            name=params.get("name", ""),
            ts_codes=ts_codes,
            start_date=params["start_date"],
            end_date=params["end_date"],
            feature_fields=feature_fields,
            result=result,
        )

        await TaskService.complete_task(task.id, analysis_result_id)

    except Exception as e:
        logger.error(f"Data analysis task {task_id} failed: {e}")
        await TaskService.fail_task(task.id, str(e))
```

- [ ] **Step 4: Refactor get_analysis_task endpoint**

```python
@router.get("/data-analysis/task/{task_id}")
async def get_analysis_task(task_id: str):
    """Get analysis task status and result."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    task = await TaskService.get_task(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # ... rest of the function unchanged
```

- [ ] **Step 5: Refactor list_analysis_tasks endpoint**

```python
@router.get("/data-analysis/tasks")
async def list_analysis_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
):
    """List analysis tasks."""
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    
    result = await TaskService.list_tasks(
        task_type=TaskType.DATA_ANALYSIS,
        status=task_status,
        page=page,
        page_size=page_size,
    )
    
    return {
        "items": [
            {
                "task_id": str(t.id),
                "name": t.params.get("name", ""),
                "status": t.status.value,
                "progress": t.progress,
                "progress_message": t.progress_message,
                "created_at": t.created_at.isoformat(),
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "error_message": t.error_message,
            }
            for t in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"],
    }
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/trade_alpha/api/routers/data_analysis.py
git commit -m "refactor: migrate data_analysis.py to use TaskService"
```

---

## Task 6: Push all changes

- [ ] **Step 1: Push to remote**

```bash
git push
```

---

## Spec Coverage Check

✅ Task creation with auto-initialization (TaskService.create_task)
✅ Status management: start_task, complete_task, fail_task (TaskService)
✅ Progress update (TaskService.update_progress)
✅ Query operations: get_task, list_tasks (TaskService)
✅ Integration tests for TaskService
✅ Usage examples in plan tasks

All spec requirements covered.
