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


class ModelConfig(Document):
    """Model config document for MongoDB.

    Attributes:
        name: 配置名称（唯一）
        model_type: 模型类型 (xgboost/lstm)
        feature_fields: 模型输入特征字段列表 (X数据集)
        standardize_fields: 需要Z-score标准化的字段列表
        winsorize_fields: 需要缩尾处理的字段列表
        output_fields: 标准化器输出字段列表 (特征+分类标签)
        classification_horizons: 分类预测周期列表
        classification_threshold: 涨跌分类阈值
        xgb_n_estimators: xgboost 树的数量
        xgb_max_depth: xgboost 树的最大深度
        xgb_learning_rate: xgboost 学习率
        xgb_min_child_weight: xgboost 叶子节点最小权重和
        xgb_subsample: xgboost 样本采样比例
        xgb_colsample_bytree: xgboost 特征采样比例
        created_at: 创建时间
        updated_at: 更新时间
    """

    name: str
    model_type: str
    feature_fields: List[str] = Field(default_factory=list)
    standardize_fields: List[str] = Field(default_factory=list)
    winsorize_fields: List[str] = Field(default_factory=list)
    output_fields: List[str] = Field(default_factory=list)
    classification_horizons: List[int] = Field(default_factory=lambda: [3, 5])
    classification_threshold: float = 0.02
    # xgboost 超参数（仅 model_type="xgboost" 时使用）
    xgb_n_estimators: int = 100
    xgb_max_depth: int = 6
    xgb_learning_rate: float = 0.1
    xgb_min_child_weight: int = 1
    xgb_subsample: float = 1.0
    xgb_colsample_bytree: float = 1.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        name = "model_configs"
        indexes = ["name"]
