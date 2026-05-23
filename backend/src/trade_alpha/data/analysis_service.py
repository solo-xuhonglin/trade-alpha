"""Data analysis service module."""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from beanie import PydanticObjectId
from trade_alpha.dao import StockDaily, DataAnalysisResult, Task
from trade_alpha.utils.date_utils import to_db_format
from trade_alpha.logging import get_logger

logger = get_logger("analysis_service")


def calculate_outlier_rate(vals: pd.Series) -> float:
    """Calculate outlier rate using IQR method."""
    q1 = vals.quantile(0.25)
    q3 = vals.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outlier_count = ((vals < lower) | (vals > upper)).sum()
    return outlier_count / len(vals) if len(vals) > 0 else 0.0


def compute_field_analysis(df: pd.DataFrame, feature_fields: List[str]) -> Dict[str, Any]:
    """Analyze fields in a DataFrame and return statistics/histograms/boxplots/missing_data.

    Pure function - no database dependency. Can be reused by both
    run_data_analysis (raw data) and training pipeline (normalized data).

    Args:
        df: DataFrame containing feature_fields columns
        feature_fields: List of field names to analyze

    Returns:
        Dict with keys: statistics, histograms, boxplots, missing_data
    """
    statistics = {}
    histograms = {}
    boxplots = {}
    missing_data = {}

    for field in feature_fields:
        if field not in df.columns:
            continue

        vals = df[field].dropna()
        if len(vals) == 0:
            continue

        statistics[field] = {
            "mean": float(vals.mean()),
            "std": float(vals.std()),
            "median": float(vals.median()),
            "q1": float(vals.quantile(0.25)),
            "q3": float(vals.quantile(0.75)),
            "min": float(vals.min()),
            "max": float(vals.max()),
            "missing_rate": float(1 - len(vals) / len(df)),
            "outlier_rate": float(calculate_outlier_rate(vals)),
        }

        try:
            counts, bins = np.histogram(vals.dropna(), bins=30)
            histograms[field] = {
                "bins": [float(b) for b in bins],
                "counts": [int(c) for c in counts],
            }
        except Exception:
            pass

        q1 = vals.quantile(0.25)
        q3 = vals.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = vals[(vals < lower_bound) | (vals > upper_bound)].tolist()

        boxplots[field] = {
            "min": float(vals.min()),
            "q1": float(q1),
            "median": float(vals.median()),
            "q3": float(q3),
            "max": float(vals.max()),
            "outliers": [float(o) for o in outliers[:100]],
        }

        missing_data[field] = {
            "total": len(df),
            "missing": int(df[field].isna().sum()),
            "rate": float(df[field].isna().mean()),
        }

    return {
        "statistics": statistics,
        "histograms": histograms,
        "boxplots": boxplots,
        "missing_data": missing_data,
    }


async def run_data_analysis(
    ts_codes: List[str],
    start_date: str,
    end_date: str,
    feature_fields: List[str],
    task_id: Optional[PydanticObjectId] = None,
) -> Dict[str, Any]:
    """Run data analysis and return results."""

    async def update_progress(progress: float, message: str):
        if task_id:
            await Task.find_one(Task.id == task_id).update(
                {"$set": {"progress": progress, "progress_message": message}}
            )

    # Convert date format to match database format (YYYYMMDD)
    start_date = to_db_format(start_date)
    end_date = to_db_format(end_date)

    await update_progress(10, "正在加载数据...")

    all_dfs = []
    for idx, ts_code in enumerate(ts_codes):
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
        ).sort(StockDaily.trade_date).to_list()
        if records:
            df = pd.DataFrame([r.model_dump() for r in records])
            df["ts_code"] = ts_code
            all_dfs.append(df)
        await update_progress(10 + (idx + 1) / len(ts_codes) * 60, f"正在处理 {idx+1}/{len(ts_codes)} 只股票...")

    if not all_dfs:
        raise ValueError("No data found")

    await update_progress(70, "正在计算统计数据...")
    df = pd.concat(all_dfs, ignore_index=True)

    await update_progress(80, "正在生成分析结果...")
    result = compute_field_analysis(df, feature_fields)

    await update_progress(95, "正在保存结果...")

    return result


async def save_analysis_result(
    task_id: str,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
    feature_fields: List[str],
    result: Dict[str, Any],
) -> str:
    """Save analysis result to database."""
    analysis_result = DataAnalysisResult(
        name=name,
        task_id=task_id,
        ts_codes=ts_codes,
        start_date=start_date,
        end_date=end_date,
        feature_fields=feature_fields,
        statistics=result["statistics"],
        histograms=result["histograms"],
        boxplots=result["boxplots"],
        missing_data=result["missing_data"],
        created_at=datetime.now(timezone.utc),
    )
    await analysis_result.insert()
    return str(analysis_result.id)


async def get_analysis_result_by_task(task_id: str) -> Optional[DataAnalysisResult]:
    """Get analysis result by task id."""
    return await DataAnalysisResult.find_one(
        DataAnalysisResult.task_id == task_id
    )
