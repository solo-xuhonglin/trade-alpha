"""Backtest API router."""

from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.predict.training_service import get_training_by_id
from trade_alpha.execution.pipeline import ExecutionPipeline

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run")
async def run_backtest(
    account_config_id: str,
    training_id: str,
    start_date: str,
    end_date: str,
    name: str = "backtest",
    top_n: int = 300,
    max_positions: int = 10,
):
    """Run backtest with execution pipeline."""
    try:
        account_config = await AccountConfig.get(PydanticObjectId(account_config_id))
        if not account_config:
            raise HTTPException(status_code=404, detail="Account config not found")

        training = await get_training_by_id(PydanticObjectId(training_id))
        if not training:
            raise HTTPException(status_code=404, detail="Training not found")

        pipeline = ExecutionPipeline(
            account_config=account_config,
            training_id=PydanticObjectId(training_id),
            mode="backtest",
        )

        result = await pipeline.run_backtest(
            start_date=start_date,
            end_date=end_date,
            name=name,
            top_n=top_n,
            max_positions=max_positions,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{result_id}")
async def get_backtest_result(result_id: str):
    """Get backtest result by ID."""
    from trade_alpha.dao.execution import ExecutionResult

    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result
