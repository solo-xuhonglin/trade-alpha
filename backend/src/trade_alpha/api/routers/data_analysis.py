"""Data analysis API router with async task support."""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, field_validator
from typing import List, Optional
from beanie import PydanticObjectId
from datetime import datetime

from trade_alpha.task.dao import TaskStatus, TaskType
from trade_alpha.task.service import TaskService
from trade_alpha.dao.data_analysis_result import DataAnalysisResult
from trade_alpha.data.service import list_stocks_by_mv_rank
from trade_alpha.data.analysis_service import (
    run_data_analysis,
    save_analysis_result,
    get_analysis_result_by_task,
)
from trade_alpha.utils.date_utils import to_api_format
from trade_alpha.models.training.config import DEFAULT_INDICATOR_FIELDS
from trade_alpha.api.validators import validate_trade_date

router = APIRouter(prefix="/data-analysis", tags=["data-analysis"])


class DataAnalysisCreate(BaseModel):
    name: Optional[str] = None
    ts_codes: Optional[List[str]] = None
    start_rank: Optional[int] = 1
    end_rank: Optional[int] = 1000
    start_date: str = "2020-01-01"
    end_date: str = "2025-12-31"
    feature_fields: Optional[List[str]] = None
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_dates(cls, v: str) -> str:
        return validate_trade_date(v)


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


@router.get("/task/{task_id}")
async def get_analysis_task(task_id: str):
    """Get analysis task status and result."""
    try:
        obj_id = PydanticObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    task = await TaskService.get_task(obj_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = None
    if task.status == TaskStatus.COMPLETED and task.result_id:
        analysis_result = await get_analysis_result_by_task(str(task.id))
        if analysis_result:
            result = {
                "statistics": analysis_result.statistics,
                "histograms": analysis_result.histograms,
                "boxplots": analysis_result.boxplots,
                "missing_data": analysis_result.missing_data,
            }

    return {
        "task_id": str(task.id),
        "status": task.status.value,
        "progress": task.progress,
        "progress_message": task.progress_message,
        "result": result,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.get("/tasks")
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


@router.get("/results")
async def list_analysis_results(limit: int = Query(20, ge=1, le=100)):
    """List analysis results."""
    results = await DataAnalysisResult.find_all().sort(-DataAnalysisResult.created_at).limit(limit).to_list()
    return [
        {
            "id": str(r.id),
            "task_id": r.task_id,
            "name": r.name,
            "ts_codes": r.ts_codes,
            "start_date": to_api_format(r.start_date),
            "end_date": to_api_format(r.end_date),
            "feature_fields": r.feature_fields,
            "created_at": r.created_at.isoformat(),
        }
        for r in results
    ]

@router.delete("/results/{id}")
async def delete_analysis_result(id: str):
    """Delete analysis result by ID."""
    try:
        obj_id = PydanticObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    result = await DataAnalysisResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    await result.delete()
    return {"status": "ok"}
