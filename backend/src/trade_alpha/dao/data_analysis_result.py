from beanie import Document
from datetime import datetime
from typing import Dict, Any, List


class DataAnalysisResult(Document):
    name: str
    task_id: str
    ts_codes: List[str]
    start_date: str
    end_date: str
    feature_fields: List[str]
    statistics: Dict[str, Any]
    histograms: Dict[str, Any]
    boxplots: Dict[str, Any]
    missing_data: Dict[str, Any]
    created_at: datetime

    class Settings:
        name = "data_analysis_results"
