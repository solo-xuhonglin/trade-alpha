"""Model configuration service.

字段默认值填充逻辑:
1. classification_horizons: 默认为 [3, 5]
2. target_names: 根据 classification_horizons 生成，如 ["label_3d", "label_5d"]
3. feature_fields: 默认为 DEFAULT_INDICATOR_FIELDS (13个固定指标)
4. standardize_fields: 默认为 feature_fields (标准化所有特征)
5. winsorize_fields: 默认为空列表 (不进行缩尾)
6. output_fields: 默认为 feature_fields + target_names (特征+标签)
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
    "rsi_6", "rsi_12", "atr_14", "obv",
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
) -> ModelConfig:
    """Create model configuration.

    Args:
        name: 配置名称（唯一）
        model_type: 模型类型 (xgboost/lstm)
        feature_fields: 模型输入特征字段列表，默认使用所有指标
        standardize_fields: 需要Z-score标准化的字段列表，默认与feature_fields相同
        winsorize_fields: 需要缩尾处理的字段列表，默认空列表
        classification_horizons: 分类预测周期列表，默认[3, 5]
        classification_threshold: 涨跌分类阈值，默认0.02
        xgb_n_estimators: xgboost 树的数量，默认100
        xgb_max_depth: xgboost 树的最大深度，默认6
        xgb_learning_rate: xgboost 学习率，默认0.1
        xgb_min_child_weight: xgboost 叶子节点最小权重和，默认1
        xgb_subsample: xgboost 样本采样比例，默认1.0
        xgb_colsample_bytree: xgboost 特征采样比例，默认1.0
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
