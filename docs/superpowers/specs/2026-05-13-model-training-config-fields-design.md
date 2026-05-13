# 模型训练配置字段优化设计方案

> **日期:** 2026-05-13
> **状态:** 待审查

## 1. 目标

优化 ModelConfig 配置字段设计，明确各字段职责，移除训练主流程中的分支判断，确保训练数据与配置完全一致。

## 2. 字段设计

### 2.1 ModelConfig 字段定义

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `feature_fields` | `List[str]` | 自动检测全部指标 | 给模型的X数据集 |
| `standardize_fields` | `List[str]` | feature_fields | 特征字段里需要标准化的部分 |
| `winsorize_fields` | `List[str]` | `[]` | 特征字段里需要缩尾的部分 |
| `output_fields` | `List[str]` | feature_fields + 分类标签 | 标准化器输出字段（X + y标签） |
| `classification_horizons` | `List[int]` | `[3, 5]` | 分类预测周期 |
| `classification_threshold` | `float` | `0.02` | 涨跌分类阈值 |
| `model_type` | `str` | - | 模型类型 (xgboost/lstm) |
| `name` | `str` | - | 配置名称（唯一） |

### 2.2 字段关系图

```
feature_fields ─────────────────────────┐
      │                               │
      ├─ standardize_fields ⊆ ────────┤
      │                               │
      └─ winsorize_fields ⊆ ──────────┤
                                     │
output_fields = feature_fields ──────┤
            + 分类标签(label_*) ─────┘
```

### 2.3 字段职责

- **feature_fields**：模型输入特征（X数据集）
- **standardize_fields**：Z-score 标准化的字段（z-score 变换）
- **winsorize_fields**：缩尾处理的字段（截断极端值）
- **output_fields**：标准化器的输出字段，包含特征和分类标签

## 3. 默认值填充逻辑

在 `config_service.create_config()` 中填充默认值：

```python
async def create_config(
    name: str,
    model_type: str,
    feature_fields: Optional[List[str]] = None,
    standardize_fields: Optional[List[str]] = None,
    winsorize_fields: Optional[List[str]] = None,
    output_fields: Optional[List[str]] = None,
    classification_horizons: Optional[List[int]] = None,
    classification_threshold: float = 0.02,
) -> ModelConfig:
    classification_horizons = classification_horizons or [3, 5]
    target_names = [f"label_{h}d" for h in classification_horizons]

    feature_fields = feature_fields or _get_default_feature_fields()
    standardize_fields = standardize_fields or feature_fields
    winsorize_fields = winsorize_fields or []
    output_fields = output_fields or feature_fields + target_names

    config = ModelConfig(
        name=name,
        model_type=model_type,
        feature_fields=feature_fields,
        standardize_fields=standardize_fields,
        winsorize_fields=winsorize_fields,
        output_fields=output_fields,
        classification_horizons=classification_horizons,
        classification_threshold=classification_threshold,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
```

## 4. 训练流程（无分支判断）

训练时直接使用配置中的值：

```python
async def create_training(...):
    config = await get_config_by_id(config_id)

    normalizer = CrossSectionalNormalizer(
        standardize_fields=config.standardize_fields,
        winsorize_fields=config.winsorize_fields,
        output_fields=config.output_fields,
    )

    combined_normalized = normalizer.normalize(
        combined[config.output_fields + ["trade_date", "ts_code"]]
    )

    X = combined_normalized[config.feature_fields].values
    y = combined_normalized[target_names].values
```

## 5. 修改文件清单

### 5.1 数据模型
- `backend/src/trade_alpha/dao/model_config.py`：新增 standardize_fields, winsorize_fields, output_fields 字段

### 5.2 服务层
- `backend/src/trade_alpha/predict/config_service.py`：更新 create_config 填充默认值逻辑
- `backend/src/trade_alpha/predict/training_service.py`：移除分支判断，直接使用配置值

### 5.3 标准化器
- `backend/src/trade_alpha/predict/normalizers/cross_sectional.py`：确认 output_fields 参数已实现

### 5.4 API 层
- `backend/src/trade_alpha/api/routers/model_configs.py`：更新 Schema

### 5.5 测试
- `backend/tests/trade_alpha/integration/test_42_model_config_service.py`：测试配置创建
- `backend/tests/trade_alpha/integration/test_51_training_service.py`：测试训练服务

## 6. 集成测试注意事项

**历史数据兼容性问题**：
- 旧的历史数据可能不包含新配置的字段值
- 集成测试需要重新创建配置和训练数据

**测试数据重建**：
```python
@pytest.mark.asyncio
async def test_ensure_default_config(self):
    existing = await config_service.get_config_by_name(self.default_config_name)
    if existing:
        await existing.delete()

    config = await config_service.create_config(
        name=self.default_config_name,
        model_type="xgboost",
        classification_horizons=[3, 5],
        classification_threshold=0.02,
    )
```

## 7. 配置示例

### 完整配置
```json
{
  "name": "xgboost-classifier",
  "model_type": "xgboost",
  "feature_fields": ["ma_5", "ma_10", "ma_20", "pct_chg", "vol_ratio_5", "bias_5", "kdj_k", "kdj_d", "kdj_j"],
  "standardize_fields": ["ma_5", "ma_10", "ma_20", "vol_ratio_5"],
  "winsorize_fields": ["pct_chg"],
  "output_fields": ["ma_5", "ma_10", "ma_20", "pct_chg", "vol_ratio_5", "bias_5", "kdj_k", "kdj_d", "kdj_j", "label_3d", "label_5d"],
  "classification_horizons": [3, 5],
  "classification_threshold": 0.02
}
```

### 最小配置（使用所有默认值）
```json
{
  "name": "xgboost-default",
  "model_type": "xgboost"
}
```

## 8. 文档更新

需同步更新以下文档：
- `docs/database-schema.md`：更新 model_configs 表结构
- `docs/api.md`：更新 API Schema
- `docs/system-design.md`：更新模块说明
