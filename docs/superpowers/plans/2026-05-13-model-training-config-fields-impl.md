# 模型训练配置字段优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 ModelConfig 配置字段，新增 standardize_fields, winsorize_fields, output_fields 字段，训练和预测使用同一固定配置。

**Architecture:** ModelConfig 新增三个配置字段，训练和预测流程统一使用配置值，移除分支判断逻辑。

**Tech Stack:** Python, Beanie, MongoDB, pandas, numpy

---

## 文件修改清单

```
backend/src/trade_alpha/dao/model_config.py      # 数据模型
backend/src/trade_alpha/predict/config_service.py  # 配置服务
backend/src/trade_alpha/predict/training_service.py # 训练服务
backend/src/trade_alpha/api/routers/model_configs.py  # API Router
backend/tests/trade_alpha/integration/test_42_model_config_service.py  # 配置服务测试
backend/tests/trade_alpha/integration/test_51_training_service.py  # 训练服务测试
docs/database-schema.md  # 数据库文档
docs/api.md  # API 文档
```

---

## 依赖顺序图

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6
```

---

### Task 1: 修改 ModelConfig 数据模型

**Files:**
- Modify: `backend/src/trade_alpha/dao/model_config.py`

- [ ] **Step 1: 添加新字段到 ModelConfig**

修改 `backend/src/trade_alpha/dao/model_config.py`，在 `feature_fields` 之后添加三个新字段：

```python
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field
from beanie import Document


class ModelConfig(Document):
    """Model config document for MongoDB."""

    name: str
    model_type: str
    feature_fields: List[str] = Field(default_factory=list)
    standardize_fields: List[str] = Field(default_factory=list)
    winsorize_fields: List[str] = Field(default_factory=list)
    output_fields: List[str] = Field(default_factory=list)
    classification_horizons: List[int] = Field(default_factory=lambda: [3, 5])
    classification_threshold: float = 0.02
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        name = "model_configs"
        indexes = ["name"]
```

- [ ] **Step 2: 运行测试验证数据模型**

Run: `cd backend && pytest tests/trade_alpha/integration/test_42_model_config_service.py -v -k "test_ensure_default_config" --tb=short`
Expected: 可能有 schema 相关错误，待 Task 5 处理旧数据

---

### Task 2: 修改 config_service

**Files:**
- Modify: `backend/src/trade_alpha/predict/config_service.py`

- [ ] **Step 1: 添加预定义指标常量 (25个字段)**

在 `backend/src/trade_alpha/predict/config_service.py` 文件开头添加：

```python
DEFAULT_INDICATOR_FIELDS = [
    "ma_5", "ma_10", "ma_20", "ma_60",
    "macd", "macd_signal", "macd_hist",
    "pct_chg",
    "bias_5", "bias_10", "bias_20", "bias_60",
    "close_pct_rank_5", "close_pct_rank_10", "close_pct_rank_20", "close_pct_rank_60",
    "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60",
    "kdj_k", "kdj_d", "kdj_j",
    "boll_upper", "boll_middle", "boll_lower",
]
```

- [ ] **Step 2: 修改 create_config 函数签名和默认值填充**

替换 `create_config` 函数为：

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
    """Create model configuration."""
    if not name:
        raise ValueError("name is required")
    if model_type not in ("xgboost", "lstm"):
        raise ValueError(f"model_type must be xgboost or lstm, got: {model_type}")

    existing = await ModelConfig.find_one(ModelConfig.name == name)
    if existing:
        raise ValueError(f"Config already exists: {name}")

    classification_horizons = classification_horizons or [3, 5]
    target_names = [f"label_{h}d" for h in classification_horizons]

    feature_fields = feature_fields or DEFAULT_INDICATOR_FIELDS.copy()
    standardize_fields = standardize_fields or feature_fields.copy()
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
    await config.insert()
    logger.info(f"Config created: id={config.id} name={name} model_type={model_type}")
    return config
```

- [ ] **Step 3: 验证 config_service**

Run: `cd backend && python -c "from trade_alpha.predict.config_service import create_config, DEFAULT_INDICATOR_FIELDS; print(DEFAULT_INDICATOR_FIELDS)"`
Expected: 打印出指标列表

---

### Task 3: 修改 training_service

**Files:**
- Modify: `backend/src/trade_alpha/predict/training_service.py`

- [ ] **Step 1: 删除分支判断代码**

删除以下代码：
1. 删除 `RELATIVE_INDICATOR_PREFIXES` 常量（第 25-29 行）
2. 删除 `_get_default_feature_fields` 函数（第 38-45 行）

- [ ] **Step 2: 修改 create_training 函数**

找到 `create_training` 函数（约第 58-180 行），修改以下部分：

替换原来根据 config.feature_fields 判断的逻辑（第 109-112 行）：
```python
# 原来：
if config.feature_fields:
    feature_fields = config.feature_fields
else:
    feature_fields = _get_default_feature_fields(combined.columns.tolist())
```

改为直接使用配置值：
```python
feature_fields = config.feature_fields
standardize_fields = config.standardize_fields
winsorize_fields = config.winsorize_fields
output_fields = config.output_fields
```

- [ ] **Step 3: 修改 normalizer 初始化**

替换原来（第 116-122 行）：
```python
# 原来：
if config.normalizer_fields:
    normalizer = CrossSectionalNormalizer(
        standardize_fields=feature_fields,
        **config.normalizer_fields
    )
else:
    normalizer = CrossSectionalNormalizer(standardize_fields=feature_fields)
```

改为：
```python
normalizer = CrossSectionalNormalizer(
    standardize_fields=standardize_fields,
    winsorize_fields=winsorize_fields,
    output_fields=output_fields,
)
```

- [ ] **Step 4: 修改标准化器输入**

替换原来（第 124 行）：
```python
# 原来：
combined_normalized = normalizer.normalize(combined[feature_fields + ["trade_date", "ts_code"]])
```

改为：
```python
combined_normalized = normalizer.normalize(combined[output_fields + ["trade_date", "ts_code"]])
```

- [ ] **Step 5: 修改 predict_with_training 函数**

找到 `predict_with_training` 函数（约第 204-264 行），修改 normalizer 初始化部分。

替换原来（第 225-231 行）：
```python
# 原来：
if config.normalizer_fields:
    normalizer = CrossSectionalNormalizer(
        standardize_fields=training.feature_fields,
        **config.normalizer_fields
    )
else:
    normalizer = CrossSectionalNormalizer(standardize_fields=training.feature_fields)
```

改为：
```python
normalizer = CrossSectionalNormalizer(
    standardize_fields=config.standardize_fields,
    winsorize_fields=config.winsorize_fields,
    output_fields=config.output_fields,
)
```

- [ ] **Step 6: 运行类型检查**

Run: `cd backend && python -m py_compile src/trade_alpha/predict/training_service.py`
Expected: 无输出表示语法正确

---

### Task 4: 更新 API Router

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/model_configs.py`

- [ ] **Step 1: 更新 ConfigCreate Schema**

替换 `ConfigCreate` 类为：

```python
class ConfigCreate(BaseModel):
    name: str
    model_type: str
    feature_fields: Optional[List[str]] = None
    standardize_fields: Optional[List[str]] = None
    winsorize_fields: Optional[List[str]] = None
    output_fields: Optional[List[str]] = None
    classification_horizons: Optional[List[int]] = None
    classification_threshold: Optional[float] = None
```

- [ ] **Step 2: 更新 ConfigUpdate Schema**

替换 `ConfigUpdate` 类为：

```python
class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    feature_fields: Optional[List[str]] = None
    standardize_fields: Optional[List[str]] = None
    winsorize_fields: Optional[List[str]] = None
    output_fields: Optional[List[str]] = None
    classification_horizons: Optional[List[int]] = None
    classification_threshold: Optional[float] = None
```

- [ ] **Step 3: 更新 create_config 调用**

找到 `@router.post("")` 装饰的 `create_config` 函数（约第 33-45 行），更新调用参数：

```python
@router.post("")
async def create_config(body: ConfigCreate):
    """Create model configuration."""
    try:
        return await config_service.create_config(
            name=body.name,
            model_type=body.model_type,
            feature_fields=body.feature_fields,
            standardize_fields=body.standardize_fields,
            winsorize_fields=body.winsorize_fields,
            output_fields=body.output_fields,
            classification_horizons=body.classification_horizons,
            classification_threshold=body.classification_threshold or 0.02,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 4: 验证 API**

Run: `cd backend && python -c "from trade_alpha.api.routers.model_configs import ConfigCreate, ConfigUpdate; print('OK')"`
Expected: OK

---

### Task 5: 更新集成测试

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_42_model_config_service.py`
- Modify: `backend/tests/trade_alpha/integration/test_51_training_service.py`

- [ ] **Step 1: 更新 test_42_model_config_service.py**

找到 `test_ensure_default_config` 方法，添加删除旧配置的逻辑：

```python
@pytest.mark.asyncio
async def test_ensure_default_config(self):
    """Ensure default config exists for Layer 5 tests."""
    existing = await config_service.get_config_by_name(self.default_config_name)
    if existing:
        await existing.delete()

    config = await config_service.create_config(
        name=self.default_config_name,
        model_type="xgboost",
        classification_horizons=[3, 5],
        classification_threshold=0.02,
    )
    assert config.feature_fields == DEFAULT_INDICATOR_FIELDS
    assert config.standardize_fields == DEFAULT_INDICATOR_FIELDS
    assert config.winsorize_fields == []
    assert "label_3d" in config.output_fields
    assert "label_5d" in config.output_fields
```

- [ ] **Step 2: 运行配置服务测试**

Run: `cd backend && pytest tests/trade_alpha/integration/test_42_model_config_service.py -v`
Expected: PASS

- [ ] **Step 3: 更新 test_51_training_service.py**

找到测试中创建配置的代码，删除旧配置后重新创建：

```python
# 在测试开始前
existing = await config_service.get_config_by_name("test_training_config")
if existing:
    await existing.delete()

config = await config_service.create_config(
    name="test_training_config",
    model_type="xgboost",
)
```

- [ ] **Step 4: 运行训练服务测试**

Run: `cd backend && pytest tests/trade_alpha/integration/test_51_training_service.py -v`
Expected: PASS

---

### Task 6: 更新文档

**Files:**
- Modify: `docs/database-schema.md`
- Modify: `docs/api.md`

- [ ] **Step 1: 更新 database-schema.md**

找到 `model_configs` 部分，添加新字段说明：

```markdown
| `standardize_fields` | array | Z-score 标准化的字段列表 |
| `winsorize_fields` | array | 缩尾处理的字段列表 |
| `output_fields` | array | 标准化器输出字段（特征+标签） |
```

- [ ] **Step 2: 更新 api.md**

找到 `创建配置` 的请求体示例，添加新字段：

```json
{
  "name": "xgboost-classifier",
  "model_type": "xgboost",
  "feature_fields": ["ma_5", "ma_10", "ma_20"],
  "standardize_fields": ["ma_5", "ma_10"],
  "winsorize_fields": [],
  "output_fields": ["ma_5", "ma_10", "ma_20", "label_3d", "label_5d"],
  "classification_horizons": [3, 5],
  "classification_threshold": 0.02
}
```

- [ ] **Step 3: 提交文档更新**

```bash
git add docs/database-schema.md docs/api.md
git commit -m "docs: update model_configs schema and API docs"
```

---

## 最终验证

```bash
cd backend && pytest tests/trade_alpha/integration/test_42_model_config_service.py tests/trade_alpha/integration/test_51_training_service.py -v
```

Expected: 所有测试 PASS

---

## 自检清单

- [ ] ModelConfig 有 4 个字段：feature_fields, standardize_fields, winsorize_fields, output_fields
- [ ] config_service.create_config 默认填充逻辑正确
- [ ] training_service 无分支判断，直接使用配置值
- [ ] 训练和预测使用相同的标准化器配置
- [ ] 集成测试删除旧配置后重新创建
- [ ] 文档同步更新
