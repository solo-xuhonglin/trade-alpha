"""Model configuration service.

Default value filling rules:
1. classification_horizons: defaults to [3, 5, 10]
2. target_names: generated from classification_horizons, e.g. ["label_3d", "label_5d", "label_10d"]
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
from trade_alpha.constants import DEFAULT_CLASSIFICATION_HORIZONS

logger = get_logger("config_service")

DEFAULT_INDICATOR_FIELDS = [
    "ma_5", "ma_10", "ma_20", "ma_40", "ma_60",
    "macd", "macd_signal", "macd_hist",
    "pct_chg",
    "candle_body_pct", "candle_upper_pct", "candle_lower_pct",
    "close_location_pct", "gap_pct", "gap_fill_pct",
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
    "obv_chg_5", "obv_chg_10", "obv_chg_20",
]


async def create_config(
    name: str,
    model_type: str,
    feature_fields: Optional[List[str]] = None,
    standardize_fields: Optional[List[str]] = None,
    winsorize_fields: Optional[List[str]] = None,
    classification_horizons: Optional[List[int]] = None,
    label_mode: Optional[str] = None,
    classification_threshold_3d: Optional[float] = None,
    classification_threshold_5d: Optional[float] = None,
    classification_threshold_10d: Optional[float] = None,
    classification_threshold_20d: Optional[float] = None,
    xgb_n_estimators: Optional[int] = None,
    xgb_max_depth: Optional[int] = None,
    xgb_learning_rate: Optional[float] = None,
    xgb_min_child_weight: Optional[int] = None,
    xgb_subsample: Optional[float] = None,
    xgb_colsample_bytree: Optional[float] = None,
    lstm_hidden_size: Optional[int] = None,
    lstm_num_layers: Optional[int] = None,
    lstm_dropout: Optional[float] = None,
    lstm_epochs: Optional[int] = None,
    lstm_batch_size: Optional[int] = None,
    lstm_learning_rate: Optional[float] = None,
    lstm_sequence_length: Optional[int] = None,
    lstm_normalization_window: Optional[int] = None,
    use_memmap: Optional[bool] = None,
    label_smoothing: Optional[float] = None,
    early_stopping_patience: Optional[int] = None,
    lstm_weight_decay: Optional[float] = None,
    lr_scheduler_factor: Optional[float] = None,
    lr_scheduler_patience: Optional[int] = None,
    val_size: Optional[float] = None,
) -> ModelConfig:
    """Create model configuration.

    Args:
        name: config name (unique)
        model_type: model type (xgboost/lstm)
        feature_fields: feature field list for model input
        standardize_fields: fields for Z-score normalization
        winsorize_fields: fields for winsorization
        classification_horizons: classification horizon list
        label_mode: label generation mode (threshold/quantile)
        classification_threshold_3d: 3-day classification threshold
        classification_threshold_5d: 5-day classification threshold
        classification_threshold_10d: 10-day classification threshold
        classification_threshold_20d: 20-day classification threshold
        xgb_n_estimators: XGBoost number of trees
        xgb_max_depth: XGBoost max tree depth
        xgb_learning_rate: XGBoost learning rate
        xgb_min_child_weight: XGBoost min child weight
        xgb_subsample: XGBoost subsample ratio
        xgb_colsample_bytree: XGBoost colsample ratio
        lstm_hidden_size: LSTM hidden layer size
        lstm_num_layers: LSTM number of layers
        lstm_dropout: LSTM dropout ratio
        lstm_epochs: LSTM training epochs
        lstm_batch_size: LSTM batch size
        lstm_learning_rate: LSTM learning rate
        lstm_sequence_length: LSTM input sequence length
        label_smoothing: Label smoothing coefficient
        early_stopping_patience: Early stopping patience
        lstm_weight_decay: LSTM L2 regularization weight
        lr_scheduler_factor: Learning rate scheduler decay factor
        lr_scheduler_patience: Learning rate scheduler patience
        val_size: Validation set ratio (by date)
    """
    if not name:
        raise ValueError("name is required")
    if model_type not in ("xgboost", "lstm"):
        raise ValueError(f"model_type must be xgboost or lstm, got: {model_type}")

    existing = await ModelConfig.find_one(ModelConfig.name == name)
    if existing:
        raise ValueError(f"Config already exists: {name}")

    classification_horizons = classification_horizons or DEFAULT_CLASSIFICATION_HORIZONS.copy()

    feature_fields = feature_fields or DEFAULT_INDICATOR_FIELDS.copy()
    standardize_fields = standardize_fields or feature_fields.copy()
    winsorize_fields = winsorize_fields or []

    # Include only non-None fields so DAO model defaults apply
    field_names = ModelConfig.model_fields.keys()
    kwargs = {k: v for k, v in locals().items()
              if k in field_names and v is not None}
    kwargs["created_at"] = datetime.now(timezone.utc)
    kwargs["updated_at"] = datetime.now(timezone.utc)

    config = ModelConfig(**kwargs)
    await config.insert()
    logger.info("create_config", f"Config created: id={config.id} name={name} model_type={model_type}")
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
