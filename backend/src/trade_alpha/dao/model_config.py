"""ModelConfig Document model.

字段关系说明:
- feature_fields: 模型输入特征 (X数据集)
- standardize_fields: 需要Z-score标准化的字段 (通常与feature_fields相同)
- winsorize_fields: 需要缩尾处理的字段 (通常为空)
- output_fields: 标准化器输出字段 (feature_fields + 分类标签)

默认值逻辑 (在 config_service.create_config 中):
- feature_fields 默认使用 DEFAULT_INDICATOR_FIELDS
- standardize_fields 默认与 feature_fields 相同
- winsorize_fields 默认空列表
- output_fields 默认 feature_fields + 分类标签列表
"""

from datetime import datetime
from typing import Optional, List
from pydantic import Field
from beanie import Document
from trade_alpha.constants import (
    DEFAULT_CLASSIFICATION_HORIZONS,
    DEFAULT_CLASSIFICATION_THRESHOLD,
    DEFAULT_XGB_N_ESTIMATORS,
    DEFAULT_XGB_MAX_DEPTH,
    DEFAULT_XGB_LEARNING_RATE,
    DEFAULT_XGB_MIN_CHILD_WEIGHT,
    DEFAULT_XGB_SUBSAMPLE,
    DEFAULT_XGB_COLSAMPLE_BYTREE,
    DEFAULT_LSTM_HIDDEN_SIZE,
    DEFAULT_LSTM_NUM_LAYERS,
    DEFAULT_LSTM_DROPOUT,
    DEFAULT_LSTM_EPOCHS,
    DEFAULT_LSTM_BATCH_SIZE,
    DEFAULT_LSTM_LEARNING_RATE,
    DEFAULT_LSTM_SEQUENCE_LENGTH,
    DEFAULT_LSTM_NORMALIZATION_WINDOW,
    DEFAULT_LSTM_WEIGHT_DECAY,
    DEFAULT_LR_SCHEDULER_FACTOR,
    DEFAULT_LR_SCHEDULER_PATIENCE,
    DEFAULT_VAL_SIZE,
    DEFAULT_LABEL_SMOOTHING,
    DEFAULT_EARLY_STOPPING_PATIENCE,
)


class ModelConfig(Document):
    """Model config document for MongoDB.

    Attributes:
        name: 配置名称（唯一）
        model_type: 模型类型 (xgboost/lstm)
        feature_fields: 模型输入特征字段列表 (X数据集)
        standardize_fields: 需要Z-score标准化的字段列表
        winsorize_fields: 需要缩尾处理的字段列表
        classification_horizons: 分类预测周期列表
        classification_threshold: 涨跌分类阈值
        xgb_n_estimators: xgboost 树的数量
        xgb_max_depth: xgboost 树的最大深度
        xgb_learning_rate: xgboost 学习率
        xgb_min_child_weight: xgboost 叶子节点最小权重和
        xgb_subsample: xgboost 样本采样比例
        xgb_colsample_bytree: xgboost 特征采样比例
        lstm_hidden_size: lstm 隐藏层大小
        lstm_num_layers: lstm 层数
        lstm_dropout: lstm dropout 比例
        lstm_epochs: lstm 训练轮数
        lstm_batch_size: lstm 批次大小
        lstm_learning_rate: lstm 学习率
        lstm_sequence_length: lstm 序列长度
        lstm_normalization_window: lstm 标准化统计量计算窗口（默认 300 天）
        created_at: 创建时间
        updated_at: 更新时间
    """

    name: str
    model_type: str
    feature_fields: List[str] = Field(default_factory=list)
    standardize_fields: List[str] = Field(default_factory=list)
    winsorize_fields: List[str] = Field(default_factory=list)
    classification_horizons: List[int] = Field(default_factory=lambda: DEFAULT_CLASSIFICATION_HORIZONS.copy())
    classification_threshold: float = DEFAULT_CLASSIFICATION_THRESHOLD
    # xgboost 超参数（仅 model_type="xgboost" 时使用）
    xgb_n_estimators: int = DEFAULT_XGB_N_ESTIMATORS
    xgb_max_depth: int = DEFAULT_XGB_MAX_DEPTH
    xgb_learning_rate: float = DEFAULT_XGB_LEARNING_RATE
    xgb_min_child_weight: int = DEFAULT_XGB_MIN_CHILD_WEIGHT
    xgb_subsample: float = DEFAULT_XGB_SUBSAMPLE
    xgb_colsample_bytree: float = DEFAULT_XGB_COLSAMPLE_BYTREE
    # lstm 超参数（仅 model_type="lstm" 时使用）
    lstm_hidden_size: int = DEFAULT_LSTM_HIDDEN_SIZE
    lstm_num_layers: int = DEFAULT_LSTM_NUM_LAYERS
    lstm_dropout: float = DEFAULT_LSTM_DROPOUT
    lstm_epochs: int = DEFAULT_LSTM_EPOCHS
    lstm_batch_size: int = DEFAULT_LSTM_BATCH_SIZE
    lstm_learning_rate: float = DEFAULT_LSTM_LEARNING_RATE
    lstm_sequence_length: int = DEFAULT_LSTM_SEQUENCE_LENGTH
    lstm_normalization_window: int = DEFAULT_LSTM_NORMALIZATION_WINDOW
    lstm_weight_decay: float = DEFAULT_LSTM_WEIGHT_DECAY
    lr_scheduler_factor: float = DEFAULT_LR_SCHEDULER_FACTOR
    lr_scheduler_patience: int = DEFAULT_LR_SCHEDULER_PATIENCE
    val_size: float = DEFAULT_VAL_SIZE
    label_smoothing: float = DEFAULT_LABEL_SMOOTHING
    early_stopping_patience: int = DEFAULT_EARLY_STOPPING_PATIENCE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        name = "model_configs"
        indexes = ["name"]
