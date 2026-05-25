# 标签计算模式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 添加标签计算模式 system，支持 threshold（多阈值）和 trend（均线趋势）两种模式，标签统一使用 -1/0/1

**Architecture:** ModelConfig 添加 label_mode 和三个 per-horizon 阈值字段；helpers.py 中的 _create_classification_labels 使用多阈值，新增 _create_trend_labels（标签值 -1/0/1）；StockDaily 添加 ma_40；前端添加 label_mode 下拉框和新阈值输入

**Tech Stack:** Python/FastAPI, Vue 3/Vuetify, MongoDB/Beanie, Pandas

**审查要点：** 项目中标签实际使用 -1/0/1（不是 0/1/2），示例代码中的 0/1/2 是错误的。helpers.py 中 lambda 已正确使用 -1/0/1。所有实现必须与项目实际规范一致。

---

### Task 1: 更新 constants.py

**Files:**
- Modify: `backend/src/trade_alpha/constants.py`

- [ ] **删除旧常量，添加新常量**

```python
# 删除: DEFAULT_CLASSIFICATION_THRESHOLD: float = 0.02

# Label mode
DEFAULT_LABEL_MODE: str = "threshold"

# Per-horizon classification thresholds（短周期用小阈值，长周期用大阈值）
DEFAULT_CLASSIFICATION_THRESHOLD_3D: float = 0.01
DEFAULT_CLASSIFICATION_THRESHOLD_5D: float = 0.015
DEFAULT_CLASSIFICATION_THRESHOLD_10D: float = 0.02
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/constants.py
git commit -m "feat: add label_mode and per-horizon threshold constants"
```

### Task 2: StockDaily 添加 ma_40 + 指标服务更新

**Files:**
- Modify: `backend/src/trade_alpha/dao/stock_daily.py`
- Modify: `backend/src/trade_alpha/indicators/ma.py`
- Modify: `backend/src/trade_alpha/indicators/service.py`
- Modify: `backend/src/trade_alpha/api/schemas.py`
- Modify: `backend/src/trade_alpha/api/routers/data.py`

- [ ] **dao/stock_daily.py 添加 ma_40 字段**

在 `ma_20` 和 `ma_60` 之间添加：
```python
    ma_20: Optional[float] = None
    ma_40: Optional[float] = None  # 新增
    ma_60: Optional[float] = None
```

- [ ] **indicators/ma.py 添加 40 到默认周期列表**

```python
def calculate_ma(df: pd.DataFrame, periods: list[int] = [5, 10, 20, 40, 60]) -> pd.DataFrame:
```

- [ ] **api/schemas.py 添加 ma_40**

```python
    ma_20: Optional[float] = None
    ma_40: Optional[float] = None  # 新增
    ma_60: Optional[float] = None
```

- [ ] **api/routers/data.py 返回 ma_40**

```python
            "ma_20": r.ma_20,
            "ma_40": r.ma_40,  # 新增
            "ma_60": r.ma_60,
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/dao/stock_daily.py backend/src/trade_alpha/indicators/ma.py backend/src/trade_alpha/api/schemas.py backend/src/trade_alpha/api/routers/data.py
git commit -m "feat: add ma_40 field to StockDaily and indicators"
```

### Task 3: ModelConfig 文档更新

**Files:**
- Modify: `backend/src/trade_alpha/dao/model_config.py`

- [ ] **更新 import，删除旧常量，添加新常量**

```python
from trade_alpha.constants import (
    ...
    # 删除: DEFAULT_CLASSIFICATION_THRESHOLD,
    DEFAULT_LABEL_MODE,
    DEFAULT_CLASSIFICATION_THRESHOLD_3D,
    DEFAULT_CLASSIFICATION_THRESHOLD_5D,
    DEFAULT_CLASSIFICATION_THRESHOLD_10D,
    ...
)
```

- [ ] **ModelConfig 类：删除旧字段，添加新字段**

删除：
```python
    classification_threshold: float = DEFAULT_CLASSIFICATION_THRESHOLD  # 删除
```

添加：
```python
    label_mode: str = DEFAULT_LABEL_MODE
    classification_threshold_3d: float = DEFAULT_CLASSIFICATION_THRESHOLD_3D
    classification_threshold_5d: float = DEFAULT_CLASSIFICATION_THRESHOLD_5D
    classification_threshold_10d: float = DEFAULT_CLASSIFICATION_THRESHOLD_10D
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/dao/model_config.py
git commit -m "feat: add label_mode and per-horizon thresholds to ModelConfig"
```

### Task 4: config.py 更新 create_config

**Files:**
- Modify: `backend/src/trade_alpha/models/training/config.py`

- [ ] **更新 import**

```python
from trade_alpha.constants import (
    ...
    # 删除: DEFAULT_CLASSIFICATION_THRESHOLD,
    DEFAULT_LABEL_MODE,
    DEFAULT_CLASSIFICATION_THRESHOLD_3D,
    DEFAULT_CLASSIFICATION_THRESHOLD_5D,
    DEFAULT_CLASSIFICATION_THRESHOLD_10D,
    ...
)
```

- [ ] **更新函数签名和 ModelConfig 构造**

```python
async def create_config(
    ...
    # 删除: classification_threshold: float = 0.02,
    label_mode: str = DEFAULT_LABEL_MODE,
    classification_threshold_3d: float = DEFAULT_CLASSIFICATION_THRESHOLD_3D,
    classification_threshold_5d: float = DEFAULT_CLASSIFICATION_THRESHOLD_5D,
    classification_threshold_10d: float = DEFAULT_CLASSIFICATION_THRESHOLD_10D,
    ...
) -> ModelConfig:
    ...
    config = ModelConfig(
        ...
        label_mode=label_mode,
        classification_threshold_3d=classification_threshold_3d,
        classification_threshold_5d=classification_threshold_5d,
        classification_threshold_10d=classification_threshold_10d,
        ...
    )
```

- [ ] **更新 docstring**

在 docstring 中添加：
```python
        label_mode: Label calculation mode ("threshold" or "trend"), defaults to "threshold"
        classification_threshold_3d: Threshold for label_3d in threshold mode, defaults to 0.01
        classification_threshold_5d: Threshold for label_5d in threshold mode, defaults to 0.015
        classification_threshold_10d: Threshold for label_10d in threshold mode, defaults to 0.02
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/models/training/config.py
git commit -m "feat: update create_config for label_mode and per-horizon thresholds"
```

### Task 5: helpers.py 实现两种标签模式

**Files:**
- Modify: `backend/src/trade_alpha/models/training/helpers.py`

**重要：标签值统一使用 -1/0/1，与项目现有规范一致**

- [ ] **修改 `_create_classification_labels` 使用多阈值（保留原有 -1/0/1 逻辑）**

```python
def _create_classification_labels(df: pd.DataFrame, horizons: List[int],
                                   threshold_3d: float = 0.01,
                                   threshold_5d: float = 0.015,
                                   threshold_10d: float = 0.02) -> pd.DataFrame:
    threshold_map = {3: threshold_3d, 5: threshold_5d, 10: threshold_10d}
    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()
        for horizon in horizons:
            future_pct = (group["close"].shift(-horizon) - group["close"]) / group["close"]
            threshold = threshold_map.get(horizon, 0.02)
            group[f"label_{horizon}d"] = future_pct.map(
                lambda x: 1 if x > threshold else (-1 if x < -threshold else 0) if pd.notna(x) else None
            )
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)
```

- [ ] **新增 `_create_trend_labels` 函数（标签值 -1/0/1，与项目规范一致）**

```python
def _create_trend_labels(df: pd.DataFrame, horizons: List[int]) -> pd.DataFrame:
    """Create labels using MA trend logic.

    标签值统一使用 -1/0/1（与项目现有规范一致）：
    - 1: 上涨趋势（up）
    - 0: 横盘（neutral）
    - -1: 下跌趋势（down）

    Constants:
    - 3d: close>ma_20, ma_5>ma_5.shift(2), threshold 0.005
    - 5d: close>ma_40, ma_10>ma_10.shift(3), threshold 0.008
    - 10d: close>ma_60, ma_20>ma_20.shift(5), threshold 0.01
    """
    label_configs = {
        3: {"ma_base": "ma_20", "ma_slope": "ma_5", "shift": 2, "threshold": 0.005},
        5: {"ma_base": "ma_40", "ma_slope": "ma_10", "shift": 3, "threshold": 0.008},
        10: {"ma_base": "ma_60", "ma_slope": "ma_20", "shift": 5, "threshold": 0.01},
    }

    required_ma = set()
    for h in horizons:
        if h in label_configs:
            required_ma.add(label_configs[h]["ma_base"])
            required_ma.add(label_configs[h]["ma_slope"])

    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()

        for ma_col in required_ma:
            if ma_col not in group.columns:
                raise ValueError(f"Missing required MA column: {ma_col}")

        for horizon in horizons:
            config = label_configs.get(horizon)
            if config is None:
                continue

            ret = group["close"].shift(-horizon) / group["close"] - 1
            trend_up = (group["close"] > group[config["ma_base"]]) & \
                       (group[config["ma_slope"]] > group[config["ma_slope"]].shift(config["shift"]))
            trend_down = (group["close"] < group[config["ma_base"]]) & \
                         (group[config["ma_slope"]] < group[config["ma_slope"]].shift(config["shift"]))

            col = f"label_{horizon}d"
            group[col] = 0  # 默认横盘
            group.loc[trend_up & (ret > config["threshold"]), col] = 1   # 上涨
            group.loc[trend_down & (ret < -config["threshold"]), col] = -1  # 下跌

        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)
```

- [ ] **添加统一入口函数 `create_labels`**

```python
def create_labels(df: pd.DataFrame, horizons: List[int],
                  label_mode: str = "threshold",
                  threshold_3d: float = 0.01,
                  threshold_5d: float = 0.015,
                  threshold_10d: float = 0.02) -> pd.DataFrame:
    """Create labels based on label_mode. Labels follow -1/0/1 convention.

    Args:
        df: DataFrame with price and MA data
        horizons: List of horizons (e.g., [3, 5, 10])
        label_mode: "threshold" (涨跌幅阈值) or "trend" (均线趋势)
        threshold_3d/5d/10d: Per-horizon thresholds for threshold mode
    """
    if label_mode == "trend":
        return _create_trend_labels(df, horizons)
    return _create_classification_labels(df, horizons, threshold_3d, threshold_5d, threshold_10d)
```

- [ ] **在 XGBoost classifier.py 和 LSTM classifier.py 中替换调用点**

将 `_create_classification_labels` 调用替换为 `create_labels` 并传入新参数：

```python
# 原代码:
year_df = _create_classification_labels(year_df, config.classification_horizons, config.classification_threshold)

# 替换为:
year_df = create_labels(
    year_df, config.classification_horizons,
    label_mode=config.label_mode,
    threshold_3d=config.classification_threshold_3d,
    threshold_5d=config.classification_threshold_5d,
    threshold_10d=config.classification_threshold_10d,
)
```

同样也修改 pipeline.py。

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/models/training/helpers.py backend/src/trade_alpha/models/xgboost/classifier.py backend/src/trade_alpha/models/lstm/classifier.py backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat: implement two label modes (threshold/trend) with -1/0/1 labels"
```

### Task 6: API 路由支持新字段

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/model_configs.py`

- [ ] **更新 POST/PUT 请求参数**

```python
@router.post("/model-configs")
async def create_model_config(
    ...
    label_mode: str = DEFAULT_LABEL_MODE,
    classification_threshold_3d: Optional[float] = None,
    classification_threshold_5d: Optional[float] = None,
    classification_threshold_10d: Optional[float] = None,
    ...
):
```

在构造参数时传入新字段。

- [ ] **更新 fallback 逻辑**

```python
    config_data = {
        ...
        "label_mode": label_mode,
        "classification_threshold_3d": classification_threshold_3d or DEFAULT_CLASSIFICATION_THRESHOLD_3D,
        "classification_threshold_5d": classification_threshold_5d or DEFAULT_CLASSIFICATION_THRESHOLD_5D,
        "classification_threshold_10d": classification_threshold_10d or DEFAULT_CLASSIFICATION_THRESHOLD_10D,
    }
```

- [ ] **Commit**

```bash
git add backend/src/trade_alpha/api/routers/model_configs.py
git commit -m "feat: update model config API for label_mode and per-horizon thresholds"
```

### Task 7: 前端类型更新

**Files:**
- Modify: `frontend/src/api/modelConfig.ts`

- [ ] **更新 ModelConfig 接口**

```typescript
export interface ModelConfig {
  id: string
  name: string
  model_type: string
  label_mode: string
  feature_fields: string[]
  standardize_fields: string[]
  winsorize_fields: string[]
  classification_horizons: number[]
  classification_threshold_3d: number
  classification_threshold_5d: number
  classification_threshold_10d: number
  ...
}
```

删除 `classification_threshold: number`

- [ ] **Commit**

```bash
git add frontend/src/api/modelConfig.ts
git commit -m "feat: update modelConfig API type for label_mode and per-horizon thresholds"
```

### Task 8: 前端 ModelConfigView.vue UI 更新

**Files:**
- Modify: `frontend/src/views/ModelConfigView.vue`

- [ ] **替换旧阈值和 horizon，添加 label_mode 和三个新阈值输入**

```html
<v-divider class="mb-4"></v-divider>
<div class="text-subtitle-2 text-medium-emphasis mb-2">训练标签参数</div>
<v-row>
  <v-col cols="12" sm="6">
    <v-combobox v-model="form.classification_horizons" :items="[1, 2, 3, 5, 10, 20]" label="预测周期" multiple chips small-chips></v-combobox>
  </v-col>
  <v-col cols="12" sm="6">
    <v-select v-model="form.label_mode" :items="[
      { title: '涨跌幅阈值', value: 'threshold' },
      { title: '均线趋势', value: 'trend' }
    ]" label="标签计算模式"
      hint="threshold: 基于未来涨跌幅; trend: 基于均线位置和斜率" persistent-hint></v-select>
  </v-col>
  <template v-if="form.label_mode === 'threshold'">
    <v-col cols="12" sm="4">
      <v-text-field v-model.number="form.classification_threshold_3d" label="3日涨跌阈值" type="number" step="0.005" hint="短周期，小阈值" persistent-hint></v-text-field>
    </v-col>
    <v-col cols="12" sm="4">
      <v-text-field v-model.number="form.classification_threshold_5d" label="5日涨跌阈值" type="number" step="0.005" hint="中周期" persistent-hint></v-text-field>
    </v-col>
    <v-col cols="12" sm="4">
      <v-text-field v-model.number="form.classification_threshold_10d" label="10日涨跌阈值" type="number" step="0.005" hint="长周期，大阈值" persistent-hint></v-text-field>
    </v-col>
  </template>
</v-row>
```

- [ ] **更新 defaultForm**

```javascript
const defaultForm = {
  ...
  label_mode: 'threshold',
  classification_threshold_3d: 0.01,
  classification_threshold_5d: 0.015,
  classification_threshold_10d: 0.02,
  ...
}
```

删除 `classification_threshold: 0.02`

- [ ] **更新推荐参数配置**

在 `xgbRecommendedParams` 和 `lstmRecommendedParams` 中添加 label_mode 和三个新阈值。

- [ ] **更新 openDialog 中的编辑回填**

```javascript
  label_mode: (item as any).label_mode || 'threshold',
  classification_threshold_3d: (item as any).classification_threshold_3d ?? 0.01,
  classification_threshold_5d: (item as any).classification_threshold_5d ?? 0.015,
  classification_threshold_10d: (item as any).classification_threshold_10d ?? 0.02,
```

删除 `classification_threshold: item.classification_threshold`

- [ ] **Commit**

```bash
git add frontend/src/views/ModelConfigView.vue
git commit -m "feat: add label_mode selector and per-horizon threshold inputs to model config UI"
```

### Task 9: 更新文档

**Files:**
- Modify: `docs/api.md`
- Modify: `docs/database-schema.md`

- [ ] **api.md - 更新参数表**

将 `classification_threshold` 行替换为以下四行：
```markdown
| `label_mode` | string | "threshold" | 标签计算模式，可选 "threshold"/"trend" |
| `classification_threshold_3d` | float | 0.01 | label_3d 的涨跌阈值 |
| `classification_threshold_5d` | float | 0.015 | label_5d 的涨跌阈值 |
| `classification_threshold_10d` | float | 0.02 | label_10d 的涨跌阈值 |
```

- [ ] **database-schema.md - 更新 JSON 示例**

将 `classification_threshold` 替换为新的四个字段。

- [ ] **Commit**

```bash
git add docs/api.md docs/database-schema.md
git commit -m "docs: update API and schema docs for label_mode and per-horizon thresholds"
```

### Task 10: 测试验证

- [ ] **运行后端测试**

```bash
cd backend && pytest tests/ -v --timeout=60
```

- [ ] **前端构建检查**

```bash
cd frontend && npm run build
```

- [ ] **如有失败，修复后重新运行**

- [ ] **最终提交并推送**

```bash
git push origin main
```
