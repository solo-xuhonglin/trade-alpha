"""Model configuration service.

Default value filling rules:
1. classification_horizons: defaults to [3, 5]
2. target_names: generated from classification_horizons, e.g. ["label_3d", "label_5d"]
3. feature_fields: defaults to DEFAULT_INDICATOR_FIELDS
4. standardize_fields: defaults to feature_fields
5. winsorize_fields: defaults to empty list
6. output_fields: defaults to feature_fields + target_names
"""

from datetime import datetime, timezone
from typing import Optional, List
from beanie import PydanticObjectId
from trade_alpha.dao import ModelConfig, TrainingResult
from trade_alpha.logging import get_logger

logger = get_logger("config_service")

DEFAULT_INDICATOR_FIELDS = [
    "ma_5", "ma_10", "ma_20", "ma_60",
    "macd", "macd_signal", "macd_hist",
    "pct_chg",
    "bias_5", "bias_10", "bias_20", "bias_60",
    "close_position_5", "close_position_10", "close_position_20", "close_position_60",
    "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60",
    "kdj_k", "kdj_d", "kdj_j",
    "boll_upper", "boll_middle", "boll_lower", "boll_position",
    "rsi_6", "rsi_12",
    "trend_arrangement_5", "trend_arrangement_10", "trend_arrangement_20",
    "trend_slope_5", "trend_slope_10", "trend_slope_20",
    "trend_volume_5", "trend_volume_10", "trend_volume_20",
    "trend_stability_5", "trend_stability_10", "trend_stability_20",
    "obv",
]


async def create_config(
    name: str,
    model_type: str,
    feature_fields: Optional[List[str]] = None,
    standardize_fields: Optional[List[str]] = None,
    winsorize_fields: Optional[List[str]] = None,
    classification_horizons: Optional[List[int]] = None,
    classification_threshold: float = 0.02,
    xgb_n_estimators: int = 100,
    xgb_max_depth: int = 6,
    xgb_learning_rate: float = 0.1,
    xgb_min_child_weight: int = 1,
    xgb_subsample: float = 1.0,
    xgb_colsample_bytree: float = 1.0,
    lstm_hidden_size: int = 64,
    lstm_num_layers: int = 2,
    lstm_dropout: float = 0.1,
    lstm_epochs: int = 25,
    lstm_batch_size: int = 256,
    lstm_learning_rate: float = 0.001,
    lstm_sequence_length: int = 60,
) -> ModelConfig:
    """Create model configuration.

    Args:
        name: config name (unique)
        model_type: model type (xgboost/lstm)
        feature_fields: feature field list for model input, defaults to all indicators
        standardize_fields: fields for Z-score normalization, defaults to feature_fields
        winsorize_fields: fields for winsorization, defaults to empty
        classification_horizons: classification horizon list, defaults to [3, 5]
        classification_threshold: classification threshold for up/down, defaults to 0.02
        xgb_n_estimators: XGBoost number of trees, defaults to 100
        xgb_max_depth: XGBoost max tree depth, defaults to 6
        xgb_learning_rate: XGBoost learning rate, defaults to 0.1
        xgb_min_child_weight: XGBoost min child weight, defaults to 1
        xgb_subsample: XGBoost subsample ratio, defaults to 1.0
        xgb_colsample_bytree: XGBoost colsample ratio, defaults to 1.0
        lstm_hidden_size: LSTM hidden layer size, defaults to 64
        lstm_num_layers: LSTM number of layers, defaults to 2
        lstm_dropout: LSTM dropout ratio, defaults to 0.1
        lstm_epochs: LSTM training epochs, defaults to 25
        lstm_batch_size: LSTM batch size, defaults to 256
        lstm_learning_rate: LSTM learning rate, defaults to 0.001
        lstm_sequence_length: LSTM input sequence length, defaults to 60
    """
    if not name:
        raise ValueError("name is required")
    if model_type not in ("xgboost", "lstm"):
        raise ValueError(f"model_type must be xgboost or lstm, got: {model_type}")

    existing = await ModelConfig.find_one(ModelConfig.name == name)
    if existing:
        raise ValueError(f"Config already exists: {name}")

    classification_horizons = classification_horizons or [3, 5]

    feature_fields = feature_fields or DEFAULT_INDICATOR_FIELDS.copy()
    standardize_fields = standardize_fields or feature_fields.copy()
    winsorize_fields = winsorize_fields or []

    config = ModelConfig(
        name=name,
        model_type=model_type,
        feature_fields=feature_fields,
        standardize_fields=standardize_fields,
        winsorize_fields=winsorize_fields,
        classification_horizons=classification_horizons,
        classification_threshold=classification_threshold,
        xgb_n_estimators=xgb_n_estimators,
        xgb_max_depth=xgb_max_depth,
        xgb_learning_rate=xgb_learning_rate,
        xgb_min_child_weight=xgb_min_child_weight,
        xgb_subsample=xgb_subsample,
        xgb_colsample_bytree=xgb_colsample_bytree,
        lstm_hidden_size=lstm_hidden_size,
        lstm_num_layers=lstm_num_layers,
        lstm_dropout=lstm_dropout,
        lstm_epochs=lstm_epochs,
        lstm_batch_size=lstm_batch_size,
        lstm_learning_rate=lstm_learning_rate,
        lstm_sequence_length=lstm_sequence_length,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await config.insert()
    logger.info(f"Config created: id={config.id} name={name} model_type={model_type}")
    return config


async def get_config_by_id(config_id: PydanticObjectId) -> Optional[ModelConfig]:
    return await ModelConfig.get(config_id)


async def get_config_by_name(name: str) -> Optional[ModelConfig]:
    return await ModelConfig.find_one(ModelConfig.name == name)


async def list_configs(model_type: str = None) -> List[ModelConfig]:
    if model_type:
        return await ModelConfig.find(ModelConfig.model_type == model_type).sort(-ModelConfig.created_at).to_list()
    return await ModelConfig.find_all().sort(-ModelConfig.created_at).to_list()


async def update_config(config_id: PydanticObjectId, **kwargs) -> Optional[ModelConfig]:
    config = await ModelConfig.get(config_id)
    if not config:
        return None
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    config.updated_at = datetime.now(timezone.utc)
    await config.save()
    return config


async def delete_config(config_id: PydanticObjectId) -> bool:
    config = await ModelConfig.get(config_id)
    if not config:
        return False
    await TrainingResult.find(TrainingResult.config_id == config_id).delete()
    await config.delete()
    logger.info(f"Config deleted: id={config_id}")
    return True
