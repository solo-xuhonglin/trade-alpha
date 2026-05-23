# 子进程任务执行实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将训练和回测任务从 FastAPI BackgroundTasks 迁移到独立子进程执行，避免阻塞 API 服务。

**Architecture:** 使用 subprocess.Popen 启动独立 Python 进程执行训练/回测核心逻辑，子进程直接连接 MongoDB 更新进度，支持软停止和强制停止，服务重启时自动清理孤儿任务。

**Tech Stack:** Python subprocess, MongoDB/Beanie, asyncio

---

## 文件结构

```
backend/src/trade_alpha/task/
├── __init__.py              # 模块导出
├── dao.py                   # Task Document 定义
├── service.py                # TaskService 状态管理
├── runner.py                 # 子进程执行器基类
├── training_runner.py        # 训练执行器
├── backtest_runner.py        # 回测执行器
└── run_task.py              # 统一入口脚本
```

**文件变更：**
- `dao/task.py` → 迁移到 `task/dao.py`
- `services/task_service.py` → 迁移到 `task/service.py`
- `api/routers/trainings.py` → 修改：改用 subprocess
- `api/routers/backtest.py` → 修改：改用 subprocess
- `api/routers/data_analysis.py` → 修改：改用 subprocess
- `main.py` → 修改：新增重启恢复逻辑

---

## Task 1: 创建 task 模块目录和基础文件

**Files:**
- Create: `backend/src/trade_alpha/task/__init__.py`
- Create: `backend/src/trade_alpha/task/dao.py`
- Create: `backend/src/trade_alpha/task/service.py`
- Delete: `backend/src/trade_alpha/dao/task.py`
- Delete: `backend/src/trade_alpha/services/task_service.py`
- Modify: `backend/src/trade_alpha/dao/__init__.py` (移除 task 导出)
- Modify: `backend/src/trade_alpha/services/__init__.py` (移除 task_service 导出)

- [ ] **Step 1: 创建 task 模块目录和 __init__.py**

Create `backend/src/trade_alpha/task/__init__.py`:
```python
"""Task module for subprocess-based task execution."""

from trade_alpha.task.dao import Task, TaskStatus, TaskType
from trade_alpha.task.service import TaskService

__all__ = ["Task", "TaskStatus", "TaskType", "TaskService"]
```

- [ ] **Step 2: 创建 dao.py (从 dao/task.py 迁移)**

Read `backend/src/trade_alpha/dao/task.py` 并复制内容到 `backend/src/trade_alpha/task/dao.py`

修改 import 语句：
```python
# 移除 from beanie import Document (已在 PydanticObjectId 导入)
# 添加必要导入
```

- [ ] **Step 3: 创建 service.py (从 services/task_service.py 迁移)**

Read `backend/src/trade_alpha/services/task_service.py` 并复制内容到 `backend/src/trade_alpha/task/service.py`

修改 import 语句：
```python
# from trade_alpha.dao.task import ... → from trade_alpha.task.dao import ...
```

新增 `start_task` 和 `stop_task` 方法：

```python
@staticmethod
async def start_task(task_id: PydanticObjectId, pid: int) -> Task:
    """Mark task as RUNNING and record PID."""
    task = await Task.get(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")
    task.status = TaskStatus.RUNNING
    task.started_at = datetime.now()
    task.progress = 0.0
    task.progress_message = "正在初始化..."
    task.pid = pid
    await task.save()
    logger.info(f"Task started: {task_id} pid={pid}")
    return task

@staticmethod
async def stop_task(task_id: PydanticObjectId, force: bool = False) -> Task:
    """Stop a running task."""
    import signal
    
    task = await Task.get(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")
    
    if task.status != TaskStatus.RUNNING:
        raise ValueError(f"Task is not running: {task.status}")
    
    if force and task.pid:
        logger.info(f"Force stopping task {task_id} (PID={task.pid})")
        try:
            os.kill(task.pid, signal.SIGTERM)
        except ProcessLookupError:
            logger.warning(f"Process {task.pid} already terminated")
    
    task.status = TaskStatus.CANCELLED
    task.completed_at = datetime.now()
    await task.save()
    logger.info(f"Task {task_id} cancelled (force={force})")
    return task
```

- [ ] **Step 4: 更新 dao/__init__.py**

移除 task 相关的导出语句

- [ ] **Step 5: 更新 services/__init__.py**

移除 task_service 相关的导出语句

- [ ] **Step 6: 删除旧文件**

```bash
rm backend/src/trade_alpha/dao/task.py
rm backend/src/trade_alpha/services/task_service.py
```

- [ ] **Step 7: 提交**

```bash
git add backend/src/trade_alpha/task/
git add backend/src/trade_alpha/dao/__init__.py
git add backend/src/trade_alpha/services/__init__.py
git rm backend/src/trade_alpha/dao/task.py
git rm backend/src/trade_alpha/services/task_service.py
git commit -m "refactor: move task module from services/dao to dedicated task/ module"
```

---

## Task 2: 创建子进程执行器基类

**Files:**
- Create: `backend/src/trade_alpha/task/runner.py`

- [ ] **Step 1: 创建 runner.py**

Create `backend/src/trade_alpha/task/runner.py`:
```python
"""Base runner for subprocess task execution."""

from abc import ABC, abstractmethod
from typing import Optional
from beanie import PydanticObjectId

from trade_alpha.task.dao import Task, TaskStatus
from trade_alpha.task.service import TaskService
from trade_alpha.logging import get_logger

logger = get_logger("task.runner")


class BaseRunner(ABC):
    """Base class for task runners executed in subprocess."""

    def __init__(self, task_id: PydanticObjectId):
        self.task_id = task_id
        self._task: Optional[Task] = None

    async def check_cancelled(self) -> bool:
        """Check if task has been cancelled. Returns True if should stop."""
        self._task = await TaskService.get_task(self.task_id)
        if not self._task:
            logger.warning(f"Task {self.task_id} not found")
            return True
        if self._task.status != TaskStatus.RUNNING:
            logger.info(f"Task {self.task_id} is not running (status={self._task.status}), stopping")
            return True
        return False

    async def update_progress(self, progress: float, message: str) -> None:
        """Update task progress."""
        await TaskService.update_progress(self.task_id, progress, message)

    @abstractmethod
    async def execute(self) -> None:
        """Execute the actual task logic. Override in subclass."""
        pass

    @classmethod
    async def run(cls, task_id: PydanticObjectId) -> None:
        """Run the task with cancellation check support."""
        runner = cls(task_id)
        
        if await runner.check_cancelled():
            logger.info(f"Task {task_id} was cancelled before start")
            return
        
        await runner.execute()
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/task/runner.py
git commit -m "feat: add BaseRunner for subprocess task execution"
```

---

## Task 3: 实现训练执行器

**Files:**
- Create: `backend/src/trade_alpha/task/training_runner.py`

- [ ] **Step 1: 创建 training_runner.py**

Create `backend/src/trade_alpha/task/training_runner.py`:
```python
"""Training runner for subprocess execution."""

from typing import Any
from beanie import PydanticObjectId

from trade_alpha.task.runner import BaseRunner
from trade_alpha.task.dao import Task
from trade_alpha.task.service import TaskService
from trade_alpha.models import training
from trade_alpha.logging import get_logger

logger = get_logger("task.training_runner")


class TrainingRunner(BaseRunner):
    """Runner for training tasks."""

    async def execute(self) -> None:
        """Execute training."""
        task = await TaskService.get_task(self.task_id)
        if not task:
            logger.error(f"Task {self.task_id} not found")
            return

        params = task.params
        logger.info(f"Starting training task {self.task_id}")

        try:
            result = await training.create_training(
                config_id=PydanticObjectId(params["config_id"]),
                name=params["name"],
                ts_codes=params["ts_codes"],
                start_date=params["start_date"],
                end_date=params["end_date"],
                task_id=self.task_id,
            )

            await TaskService.complete_task(self.task_id, str(result.id))
            logger.info(f"Training task {self.task_id} completed: result_id={result.id}")

        except Exception as e:
            logger.error(f"Training task {self.task_id} failed: {e}")
            await TaskService.fail_task(self.task_id, str(e))
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/task/training_runner.py
git commit -m "feat: add TrainingRunner for subprocess training execution"
```

---

## Task 4: 实现回测执行器

**Files:**
- Create: `backend/src/trade_alpha/task/backtest_runner.py`

- [ ] **Step 1: 创建 backtest_runner.py**

Create `backend/src/trade_alpha/task/backtest_runner.py`:
```python
"""Backtest runner for subprocess execution."""

from beanie import PydanticObjectId

from trade_alpha.task.runner import BaseRunner
from trade_alpha.task.dao import Task
from trade_alpha.task.service import TaskService
from trade_alpha.models import training as training_module
from trade_alpha.execution.pipeline import ExecutionPipeline
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.strategy.service import get_strategy_by_id
from trade_alpha.logging import get_logger

logger = get_logger("task.backtest_runner")


class BacktestRunner(BaseRunner):
    """Runner for backtest tasks."""

    async def execute(self) -> None:
        """Execute backtest."""
        task = await TaskService.get_task(self.task_id)
        if not task:
            logger.error(f"Task {self.task_id} not found")
            return

        params = task.params
        logger.info(f"Starting backtest task {self.task_id}")

        try:
            account_config = await AccountConfig.get(PydanticObjectId(params["account_config_id"]))
            if not account_config:
                await TaskService.fail_task(self.task_id, f"Account config not found: {params['account_config_id']}")
                return

            training_record = await training_module.get_training_by_id(PydanticObjectId(params["training_id"]))
            if not training_record:
                await TaskService.fail_task(self.task_id, f"Training not found: {params['training_id']}")
                return

            model_config = await training_module.get_config_by_id(training_record.config_id)
            if not model_config:
                await TaskService.fail_task(self.task_id, f"Model config not found: {training_record.config_id}")
                return

            strategy_config = None
            if params.get("strategy_config_id"):
                strategy_config = await get_strategy_by_id(PydanticObjectId(params["strategy_config_id"]))
                if not strategy_config:
                    await TaskService.fail_task(self.task_id, f"Strategy config not found: {params['strategy_config_id']}")
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
                task_id=self.task_id,
            )

            await TaskService.complete_task(self.task_id, str(result.id))
            logger.info(f"Backtest task {self.task_id} completed: result_id={result.id}")

        except Exception as e:
            logger.error(f"Backtest task {self.task_id} failed: {e}")
            await TaskService.fail_task(self.task_id, str(e))
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/task/backtest_runner.py
git commit -m "feat: add BacktestRunner for subprocess backtest execution"
```

---

## Task 5: 创建统一入口脚本

**Files:**
- Create: `backend/src/trade_alpha/task/run_task.py`

- [ ] **Step 1: 创建 run_task.py**

Create `backend/src/trade_alpha/task/run_task.py`:
```python
"""Entry point for subprocess task execution.

Usage:
    python -m trade_alpha.task.run_task --task-id <id> --task-type <type>
"""

import sys
import argparse
import asyncio
from beanie import PydanticObjectId

from trade_alpha.dao.mongodb import init_db
from trade_alpha.task.dao import TaskStatus
from trade_alpha.task.service import TaskService
from trade_alpha.task.training_runner import TrainingRunner
from trade_alpha.task.backtest_runner import BacktestRunner
from trade_alpha.logging import get_logger

logger = get_logger("task.run_task")


async def main():
    parser = argparse.ArgumentParser(description="Run task in subprocess")
    parser.add_argument("--task-id", required=True, help="Task ID")
    parser.add_argument("--task-type", required=True, choices=["training", "backtest"], help="Task type")
    args = parser.parse_args()

    await init_db()

    task_id = PydanticObjectId(args.task_id)
    
    task = await TaskService.get_task(task_id)
    if not task:
        logger.error(f"Task {task_id} not found")
        return 1

    if task.status != TaskStatus.RUNNING:
        logger.info(f"Task {task_id} is not running (status={task.status}), exiting")
        return 0

    logger.info(f"Starting task {task_id} (type={args.task_type})")

    try:
        if args.task_type == "training":
            await TrainingRunner.run(task_id)
        elif args.task_type == "backtest":
            await BacktestRunner.run(task_id)
        else:
            logger.error(f"Unknown task type: {args.task_type}")
            await TaskService.fail_task(task_id, f"Unknown task type: {args.task_type}")
            return 1
    except Exception as e:
        logger.error(f"Task {task_id} execution failed: {e}")
        await TaskService.fail_task(task_id, str(e))
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
```

- [ ] **Step 2: 更新 task/__init__.py 添加新类导出**

```python
"""Task module for subprocess-based task execution."""

from trade_alpha.task.dao import Task, TaskStatus, TaskType
from trade_alpha.task.service import TaskService
from trade_alpha.task.runner import BaseRunner
from trade_alpha.task.training_runner import TrainingRunner
from trade_alpha.task.backtest_runner import BacktestRunner

__all__ = [
    "Task",
    "TaskStatus", 
    "TaskType",
    "TaskService",
    "BaseRunner",
    "TrainingRunner",
    "BacktestRunner",
]
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/task/run_task.py
git add backend/src/trade_alpha/task/__init__.py
git commit -m "feat: add run_task entry point for subprocess execution"
```

---

## Task 6: 修改 trainings.py API

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/trainings.py`

- [ ] **Step 1: 读取现有 trainings.py 确认 import 和函数**

Read `backend/src/trade_alpha/api/routers/trainings.py`

- [ ] **Step 2: 修改 trigger_training 函数**

替换现有的 BackgroundTasks 实现：

```python
@router.post("")
async def trigger_training(
    config_id: str,
    name: str,
    start_date: TradeDateQuery,
    end_date: TradeDateQuery,
    start_rank: int = Query(1, ge=1),
    end_rank: int = Query(3000, ge=1),
):
    """Trigger training task in subprocess."""
    import subprocess
    import sys
    
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

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "trade_alpha.task.run_task",
            "--task-id", str(task.id),
            "--task-type", "training",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    await TaskService.start_task(task.id, proc.pid)

    return {
        "task_id": str(task.id),
        "status": task.status.value,
        "message": "Training task triggered",
    }
```

- [ ] **Step 3: 添加停止任务接口**

在 trainings.py 添加：

```python
@router.post("/task/{task_id}/stop")
async def stop_training_task(task_id: str, force: bool = False):
    """Stop a running training task."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    try:
        task = await TaskService.stop_task(obj_id, force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Task stopped", "status": task.status.value}
```

- [ ] **Step 4: 更新 import 语句**

```python
# 移除 BackgroundTasks
# from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi import APIRouter, HTTPException, Query

# 替换 TaskService import
# from trade_alpha.services.task_service import TaskService
from trade_alpha.task.service import TaskService
# from trade_alpha.dao.task import TaskStatus, TaskType
from trade_alpha.task.dao import TaskStatus, TaskType
```

- [ ] **Step 5: 移除 run_training_async 函数和 cancel_training_task 函数**

删除这两个不再需要的函数

- [ ] **Step 6: 提交**

```bash
git add backend/src/trade_alpha/api/routers/trainings.py
git commit -m "feat: migrate training API to subprocess execution"
```

---

## Task 7: 修改 backtest.py API

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest.py`

- [ ] **Step 1: 读取现有 backtest.py 确认 import 和函数**

Read `backend/src/trade_alpha/api/routers/backtest.py`

- [ ] **Step 2: 修改 trigger_backtest 函数**

替换现有的 BackgroundTasks 实现：

```python
@router.post("/run")
async def trigger_backtest(body: BacktestRunRequest):
    """Trigger backtest task in subprocess."""
    import subprocess
    import sys
    
    try:
        account_config = await AccountConfig.get(PydanticObjectId(body.account_config_id))
        if not account_config:
            raise HTTPException(status_code=404, detail="Account config not found")

        training = await training_module.get_training_by_id(PydanticObjectId(body.training_id))
        if not training:
            raise HTTPException(status_code=404, detail="Training not found")

        task = await TaskService.create_task(TaskType.BACKTEST, {
            "account_config_id": body.account_config_id,
            "training_id": body.training_id,
            "start_date": body.start_date,
            "end_date": body.end_date,
            "name": body.name,
            "mode": body.mode,
            "ts_codes": body.ts_codes,
            "max_positions": body.max_positions,
            "strategy_config_id": body.strategy_config_id,
        })

        proc = subprocess.Popen(
            [
                sys.executable, "-m", "trade_alpha.task.run_task",
                "--task-id", str(task.id),
                "--task-type", "backtest",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        await TaskService.start_task(task.id, proc.pid)

        return {
            "task_id": str(task.id),
            "status": task.status.value,
            "message": "Backtest task triggered",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 3: 添加停止任务接口**

```python
@router.post("/task/{task_id}/stop")
async def stop_backtest_task(task_id: str, force: bool = False):
    """Stop a running backtest task."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")

    try:
        task = await TaskService.stop_task(obj_id, force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Task stopped", "status": task.status.value}
```

- [ ] **Step 4: 更新 import 语句**

```python
# from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi import APIRouter, HTTPException

# from trade_alpha.services.task_service import TaskService
from trade_alpha.task.service import TaskService
# from trade_alpha.dao.task import TaskStatus, TaskType
from trade_alpha.task.dao import TaskStatus, TaskType
```

- [ ] **Step 5: 移除 run_backtest_async 函数和 cancel_backtest_task 函数**

删除这两个不再需要的函数

- [ ] **Step 6: 提交**

```bash
git add backend/src/trade_alpha/api/routers/backtest.py
git commit -m "feat: migrate backtest API to subprocess execution"
```

---

## Task 8: 修改 data_analysis.py API

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/data_analysis.py`

- [ ] **Step 1: 读取现有 data_analysis.py 确认 import 和函数**

Read `backend/src/trade_alpha/api/routers/data_analysis.py`

- [ ] **Step 2: 修改路由**

同 trainings.py 和 backtest.py 的模式，改为 subprocess 执行

- [ ] **Step 3: 更新 import 语句**

```python
# from trade_alpha.services.task_service import TaskService
from trade_alpha.task.service import TaskService
# from trade_alpha.dao.task import TaskStatus, TaskType
from trade_alpha.task.dao import TaskStatus, TaskType
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/api/routers/data_analysis.py
git commit -m "feat: migrate data_analysis API to subprocess execution"
```

---

## Task 9: 实现重启恢复逻辑

**Files:**
- Modify: `backend/src/trade_alpha/main.py`

- [ ] **Step 1: 读取 main.py 确认现有结构**

Read `backend/src/trade_alpha/main.py`

- [ ] **Step 2: 添加恢复函数**

```python
import os
import signal

async def recover_orphaned_tasks():
    """Check for orphaned RUNNING tasks and mark them as FAILED."""
    from trade_alpha.task.dao import Task, TaskStatus
    
    logger = get_logger("startup")
    
    running_tasks = await Task.find(Task.status == TaskStatus.RUNNING).to_list()
    recovered_count = 0
    
    for task in running_tasks:
        if task.pid:
            try:
                os.kill(task.pid, 0)
                logger.info(f"Task {task.id} (PID={task.pid}) is still running")
            except ProcessLookupError:
                task.status = TaskStatus.FAILED
                task.error_message = "Process died during service restart"
                task.completed_at = datetime.now()
                await task.save()
                logger.warning(f"Orphaned task {task.id} marked as FAILED")
                recovered_count += 1
        else:
            task.status = TaskStatus.FAILED
            task.error_message = "Task marked as failed during restart (no PID)"
            task.completed_at = datetime.now()
            await task.save()
            logger.warning(f"Task {task.id} marked as FAILED (no PID)")
            recovered_count += 1
    
    if recovered_count > 0:
        logger.info(f"Recovered {recovered_count} orphaned tasks")
```

- [ ] **Step 3: 在 lifespan startup 中调用**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    
    await init_db()
    await recover_orphaned_tasks()
    
    if settings.enable_data_sync:
        scheduler = create_scheduler()
        scheduler.start()
    
    yield
    
    logger.info("Shutting down...")
    if settings.enable_data_sync:
        scheduler.stop()
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/main.py
git commit -m "feat: add orphaned task recovery on startup"
```

---

## Task 10: 更新文档

**Files:**
- Modify: `docs/system-design.md`
- Modify: `docs/api.md`

- [ ] **Step 1: 更新 system-design.md**

1. 更新目录结构（task 模块）
2. 更新 Task 相关描述
3. 添加子进程执行说明

- [ ] **Step 2: 更新 api.md**

1. 更新异步任务 API 说明
2. 添加停止接口文档

- [ ] **Step 3: 提交**

```bash
git add docs/system-design.md docs/api.md
git commit -m "docs: update docs for subprocess task execution"
```

---

## Task 11: 测试验证

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_60_task_subprocess.py`

- [ ] **Step 1: 创建测试文件**

```python
"""Integration tests for subprocess task execution."""

import pytest
import asyncio
import time
import os
import signal
from datetime import datetime
from beanie import PydanticObjectId

from trade_alpha.dao.mongodb import init_db, get_database
from trade_alpha.task.dao import Task, TaskStatus, TaskType
from trade_alpha.task.service import TaskService


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    db = await get_database()
    await db.drop_collection("tasks")
    yield
    await db.drop_collection("tasks")


class TestTaskService:
    """Test TaskService methods."""

    async def test_create_task(self):
        task = await TaskService.create_task(TaskType.TRAINING, {"test": "data"})
        assert task.status == TaskStatus.PENDING
        assert task.params == {"test": "data"}

    async def test_start_task_with_pid(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        started = await TaskService.start_task(task.id, pid=12345)
        assert started.status == TaskStatus.RUNNING
        assert started.pid == 12345

    async def test_stop_task_soft(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        await TaskService.start_task(task.id, pid=12345)
        stopped = await TaskService.stop_task(task.id, force=False)
        assert stopped.status == TaskStatus.CANCELLED

    async def test_stop_task_force(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        await TaskService.start_task(task.id, pid=os.getpid())
        stopped = await TaskService.stop_task(task.id, force=True)
        assert stopped.status == TaskStatus.CANCELLED


class TestTaskStatus:
    """Test Task status transitions."""

    async def test_status_transitions(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        assert task.status == TaskStatus.PENDING

        await TaskService.start_task(task.id, pid=123)
        task = await TaskService.get_task(task.id)
        assert task.status == TaskStatus.RUNNING

        await TaskService.stop_task(task.id, force=False)
        task = await TaskService.get_task(task.id)
        assert task.status == TaskStatus.CANCELLED


class TestTaskPersistence:
    """Test Task persistence."""

    async def test_task_persistence(self):
        task = await TaskService.create_task(TaskType.BACKTEST, {"key": "value"})
        task_id = task.id
        
        fetched = await TaskService.get_task(task_id)
        assert fetched is not None
        assert fetched.params["key"] == "value"

    async def test_task_progress_update(self):
        task = await TaskService.create_task(TaskType.TRAINING, {})
        await TaskService.start_task(task.id, pid=123)
        
        await TaskService.update_progress(task.id, 50.0, "Half done")
        
        updated = await TaskService.get_task(task.id)
        assert updated.progress == 50.0
        assert updated.progress_message == "Half done"
```

- [ ] **Step 2: 运行测试**

```bash
cd d:/projects/trade-alpha/backend
pytest tests/trade_alpha/integration/test_60_task_subprocess.py -v
```

- [ ] **Step 3: 提交测试**

```bash
git add backend/tests/trade_alpha/integration/test_60_task_subprocess.py
git commit -m "test: add integration tests for subprocess task execution"
```

---

## Task 12: 端到端测试

**Files:**
- Modify: 现有集成测试（确保迁移后仍可正常运行）

- [ ] **Step 1: 运行现有训练测试**

```bash
pytest tests/trade_alpha/integration/test_51_training_xgboost.py -v
pytest tests/trade_alpha/integration/test_53_training_lstm.py -v
```

- [ ] **Step 2: 运行现有回测测试**

```bash
pytest tests/trade_alpha/integration/test_41_backtest_portfolio.py -v
```

- [ ] **Step 3: 提交**

```bash
git commit -m "test: verify existing tests pass after migration"
```

---

## 实施检查清单

- [ ] Task 1: task 模块创建完成
- [ ] Task 2: BaseRunner 基类完成
- [ ] Task 3: TrainingRunner 完成
- [ ] Task 4: BacktestRunner 完成
- [ ] Task 5: run_task.py 入口完成
- [ ] Task 6: trainings.py 修改完成
- [ ] Task 7: backtest.py 修改完成
- [ ] Task 8: data_analysis.py 修改完成
- [ ] Task 9: 重启恢复逻辑完成
- [ ] Task 10: 文档更新完成
- [ ] Task 11: 单元测试通过
- [ ] Task 12: 端到端测试通过
