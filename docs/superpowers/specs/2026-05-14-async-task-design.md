# Async Task Design

**Date**: 2026-05-14
**Author**: AI Assistant

## Overview

将回测和训练接口改造为异步任务模式，通过任务状态查询来获取执行结果。

## Problem

当前回测和训练接口是同步阻塞调用，执行时间长时会导致：
- 请求超时
- 用户体验差（长时间等待）
- 无法跟踪进度
- 无法取消任务

## Design

### 1. Task Model

**文件**: `backend/src/trade_alpha/dao/task.py`

```python
from enum import Enum
from beanie import Document
from beanie import PydanticObjectId
from datetime import datetime
from typing import Optional, Dict, Any

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskType(str, Enum):
    BACKTEST = "backtest"
    TRAINING = "training"

class Task(Document):
    task_id: PydanticObjectId
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result_id: Optional[PydanticObjectId] = None
    error_message: Optional[str] = None
    created_at: datetime = datetime.now()
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    params: Dict[str, Any] = {}
    
    class Settings:
        name = "tasks"
```

### 2. Backtest API Changes

**文件**: `backend/src/trade_alpha/api/routers/backtest.py`

| 接口 | 方法 | 说明 |
|-----|------|-----|
| `/backtest/run` | POST | 触发回测任务（异步） |
| `/backtest/task/{task_id}` | GET | 查询回测任务状态 |
| `/backtest/task/{task_id}` | DELETE | 取消回测任务 |
| `/backtest/tasks` | GET | 获取任务列表 |

#### POST /backtest/run

**请求参数**:
```python
account_config_id: str
training_id: str
start_date: str
end_date: str
name: str = "backtest"
mode: str = "portfolio"        # "portfolio" | "single"
ts_codes: List[str] = None     # 股票代码列表
max_positions: int = 10
```

**响应**:
```json
{
    "task_id": "6a0519848fc1cd0e6f315517",
    "status": "pending",
    "message": "Backtest task triggered"
}
```

#### GET /backtest/task/{task_id}

**响应**:
```json
{
    "task_id": "6a0519848fc1cd0e6f315517",
    "status": "completed",
    "progress": 100.0,
    "result": {
        "id": "6a05b377f3caad76272454a8",
        "total_return": 0.0341,
        "max_drawdown": 0.0719,
        "sharpe_ratio": -0.05,
        "volatility": 0.2027,
        "baseline_return": -0.0412,
        "excess_return": 0.0071,
        "total_trades": 1,
        "avg_hold_days": 30.0
    },
    "error_message": null,
    "created_at": "2025-01-01T09:00:00",
    "completed_at": "2025-01-01T09:15:30"
}
```

### 3. Training API Changes

**文件**: `backend/src/trade_alpha/api/routers/trainings.py`

| 接口 | 方法 | 说明 |
|-----|------|-----|
| `/trainings` | POST | 触发训练任务（异步） |
| `/trainings/task/{task_id}` | GET | 查询训练任务状态 |
| `/trainings/task/{task_id}` | DELETE | 取消训练任务 |
| `/trainings/tasks` | GET | 获取任务列表 |

#### POST /trainings

**请求参数**:
```python
name: str
model_config_id: str
```

**响应**:
```json
{
    "task_id": "6a0519848fc1cd0e6f315518",
    "status": "pending",
    "message": "Training task triggered"
}
```

#### GET /trainings/task/{task_id}

**响应**:
```json
{
    "task_id": "6a0519848fc1cd0e6f315518",
    "status": "completed",
    "progress": 100.0,
    "training": {
        "id": "6a0519848fc1cd0e6f315517",
        "name": "prod_training",
        "accuracy": 0.58,
        "f1_score": 0.56,
        "created_at": "2025-01-01T10:00:00"
    },
    "error_message": null,
    "created_at": "2025-01-01T09:00:00",
    "completed_at": "2025-01-01T09:30:00"
}
```

### 4. Task Executor

**文件**: `backend/src/trade_alpha/tasks/executor.py`

```python
"""异步任务执行器"""

from datetime import datetime
from beanie import PydanticObjectId
from trade_alpha.dao.task import Task, TaskStatus, TaskType
from trade_alpha.execution.pipeline import ExecutionPipeline
from trade_alpha.predict.training_service import train_model
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.predict.config_service import get_config_by_id
from trade_alpha.logging import get_logger

logger = get_logger("tasks.executor")

async def run_backtest_async(task_id: PydanticObjectId):
    """异步执行回测"""
    task = await Task.get(task_id)
    if not task:
        return
    
    try:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        await task.save()
        
        params = task.params
        account_config = await AccountConfig.get(PydanticObjectId(params["account_config_id"]))
        
        pipeline = ExecutionPipeline(
            account_config=account_config,
            training_id=PydanticObjectId(params["training_id"]),
            mode=params["mode"],
            ts_codes=params.get("ts_codes"),
            max_positions=params.get("max_positions", 10),
        )
        
        result = await pipeline.run_backtest(
            start_date=params["start_date"],
            end_date=params["end_date"],
            name=params["name"],
        )
        
        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.result_id = result.id
        task.completed_at = datetime.now()
        await task.save()
        
    except Exception as e:
        logger.error(f"Backtest task {task_id} failed: {e}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        await task.save()

async def run_training_async(task_id: PydanticObjectId):
    """异步执行训练"""
    task = await Task.get(task_id)
    if not task:
        return
    
    try:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        await task.save()
        
        params = task.params
        model_config = await get_config_by_id(PydanticObjectId(params["model_config_id"]))
        training = await train_model(params["name"], model_config)
        
        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.result_id = training.id
        task.completed_at = datetime.now()
        await task.save()
        
    except Exception as e:
        logger.error(f"Training task {task_id} failed: {e}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        await task.save()
```

### 5. Frontend Updates

#### BacktestView.vue

**新增状态轮询逻辑**:
```typescript
const pollTaskStatus = async () => {
    if (!currentTaskId.value) return
    
    const res = await backtestApi.getTask(currentTaskId.value)
    const task = res.data
    
    if (task.status === 'completed') {
        result.value = task.result
        stopPolling()
    } else if (task.status === 'failed') {
        error.value = task.error_message
        stopPolling()
    }
}

let pollInterval: number | null = null

const startPolling = () => {
    pollInterval = window.setInterval(pollTaskStatus, 2000)
}

const stopPolling = () => {
    if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
    }
}
```

#### TrainingsView.vue

**同样添加状态轮询逻辑**

### 6. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend                              │
│  ┌─────────────────┐    ┌─────────────────┐              │
│  │  BacktestView   │    │ TrainingsView   │              │
│  │  (轮询状态)      │    │  (轮询状态)      │              │
│  └────────┬────────┘    └────────┬────────┘              │
└───────────┼───────────────────────┼───────────────────────┘
            │                       │
            ▼                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI                               │
│  ┌─────────────────┐    ┌─────────────────┐              │
│  │ /backtest/run   │    │ /trainings      │              │
│  │ /backtest/task  │    │ /trainings/task │              │
│  └────────┬────────┘    └────────┬────────┘              │
└───────────┼───────────────────────┼───────────────────────┘
            │                       │
            ▼                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Task Executor                           │
│  ┌─────────────────┐    ┌─────────────────┐              │
│  │ run_backtest_async│   │ run_training_async│             │
│  │  (后台执行)       │    │  (后台执行)       │              │
│  └────────┬────────┘    └────────┬────────┘              │
└───────────┼───────────────────────┼───────────────────────┘
            │                       │
            ▼                       ▼
┌─────────────────────────────────────────────────────────────┐
│                       MongoDB                              │
│  ┌──────────┐  ┌───────────────────┐  ┌───────────────┐   │
│  │  tasks   │  │ execution_results │  │  trainings   │   │
│  └──────────┘  └───────────────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Plan

1. Create Task model (dao/task.py)
2. Update backtest router with async endpoints
3. Update training router with async endpoints
4. Create task executor (tasks/executor.py)
5. Update frontend backtest view
6. Update frontend trainings view

## Success Criteria

- 回测和训练接口改为异步触发
- 通过任务状态查询获取结果
- 前端轮询显示实时进度
- 支持任务取消
- 错误信息正确返回
