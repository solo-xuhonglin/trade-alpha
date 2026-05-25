"""Training orchestration - dispatches to models, does not handle data internally."""

import os
from datetime import datetime, timezone
from typing import Optional, List, Dict
from beanie import PydanticObjectId
import pandas as pd
import numpy as np

from trade_alpha.dao import TrainingResult, PredictionResult, StockDaily
from trade_alpha.task.service import TaskService
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.models.xgboost.normalizer import normalize as xgb_normalize
from trade_alpha.models.factory import create_classifier
from trade_alpha.logging import get_logger

logger = get_logger("models.training.trainer")
MODELS_DIR = "models"


async def create_training(config_id, name, ts_codes, start_date, end_date, task_id=None):
    config = await get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    classifier = create_classifier(config)

    await TaskService.update_progress(task_id, 10, "正在初始化...")
    metrics = await classifier.train(ts_codes, start_date, end_date, task_id)

    await TaskService.update_progress(task_id, 95, "正在保存结果...")

    training = TrainingResult(
        config_id=config_id, name=name,
        ts_codes=ts_codes, start_date=start_date, end_date=end_date,
        feature_fields=config.feature_fields,
        classification_horizons=config.classification_horizons,
        model_metrics=metrics,
        created_at=datetime.now(timezone.utc),
    )
    await training.insert()

    os.makedirs(os.path.join(MODELS_DIR, str(config_id)), exist_ok=True)
    model_path = os.path.join(MODELS_DIR, str(config_id), f"{training.id}.pkl")
    classifier.save(model_path)
    training.model_path = model_path
    await training.save()

    logger.info(f"Training completed: name={name} id={training.id} samples={metrics.get('sample_count')}")
    return training


async def get_training_by_id(training_id: PydanticObjectId) -> Optional[TrainingResult]:
    return await TrainingResult.get(training_id)


async def get_training_by_name(name: str) -> Optional[TrainingResult]:
    return await TrainingResult.find_one(TrainingResult.name == name)


async def list_trainings(config_id: PydanticObjectId = None) -> List[TrainingResult]:
    if config_id:
        return await TrainingResult.find(TrainingResult.config_id == config_id).sort(-TrainingResult.created_at).to_list()
    return await TrainingResult.find_all().sort(-TrainingResult.created_at).to_list()


async def delete_training(training_id: PydanticObjectId) -> bool:
    training = await TrainingResult.get(training_id)
    if not training:
        return False
    if training.model_path and os.path.exists(training.model_path):
        os.remove(training.model_path)
    await PredictionResult.find(PredictionResult.training_result_id == training_id).delete()
    await training.delete()
    return True


async def delete_training_by_name(name: str) -> bool:
    training = await get_training_by_name(name)
    if not training:
        return False
    return await delete_training(training.id)
