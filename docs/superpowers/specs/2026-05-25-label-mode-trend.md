# 标签计算模式 - 均线趋势模式

## 概述

在模型配置中新增 `label_mode` 字段，支持两种标签计算模式：
- `threshold`（现有）：基于未来涨跌幅阈值的三分类，标签值为 -1/0/1
- `trend`（新增）：基于均线主体 + 均线斜率方向确认的三分类，标签值为 -1/0/1

## 字段变更

### 删除字段
| 字段 | 说明 |
|------|------|
| `classification_threshold` | 旧的单阈值，已废弃 |

### ModelConfig 新增字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `label_mode` | str | "threshold" | 标签计算模式，可选 "threshold"/"trend" |
| `classification_threshold_3d` | float | 0.01 | label_3d 的涨跌阈值（threshold 模式，短周期用小阈值） |
| `classification_threshold_5d` | float | 0.015 | label_5d 的涨跌阈值（threshold 模式） |
| `classification_threshold_10d` | float | 0.02 | label_10d 的涨跌阈值（threshold 模式，长周期用大阈值） |

### StockDaily 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `ma_40` | Optional[float] | 40日均线 |

## 阈值模式逻辑（现有逻辑，使用多阈值）

每个 horizon 使用各自的阈值，标签值遵循项目规范 -1/0/1：
```
future_pct = (close[-h] - close) / close
label =  1  if future_pct > threshold_Nd       (上涨)
         0  if -threshold_Nd <= future_pct <= threshold_Nd  (横盘)
        -1  if future_pct < -threshold_Nd      (下跌)
```

## 均线趋势模式逻辑（新增）

每个 horizon 使用均线主体 + 均线斜率作为方向确认，标签值遵循项目规范 -1/0/1：

| 期限 | 均线主体 | 方向确认 | 上涨阈值 | 下跌阈值 |
|------|---------|---------|---------|---------|
| 3日 | close > ma_20 | ma_5斜率向上(ma_5>ma_5.shift(2)) | 未来3日涨幅>0.005 | 未来3日跌幅<-0.005 |
| 5日 | close > ma_40 | ma_10斜率向上(ma_10>ma_10.shift(3)) | 未来5日涨幅>0.008 | 未来5日跌幅<-0.008 |
| 10日 | close > ma_60 | ma_20斜率向上(ma_20>ma_20.shift(5)) | 未来10日涨幅>0.01 | 未来10日跌幅<-0.01 |

标签规则：
- 条件不满足或涨跌幅不足时默认 → **0（横盘）**
- 均线主体向上 + 方向确认向上 + 涨幅达标 → **1（上涨）**
- 均线主体向下 + 方向确认向下 + 跌幅达标 → **-1（下跌）**

趋势模式的阈值是固定常量，不通过前端配置。

## 标签值统一说明

两种模式均使用 -1/0/1 三分类，与项目现有规范一致：
- **-1**: 下跌（down）
- **0**: 横盘（neutral）
- **1**: 上涨（up）

模型训练时内部映射为 0/1/2 索引用于交叉熵损失，预测时再映射回 -1/0/1 输出。

## 修改文件

### 后端
1. `constants.py` - 新增常量（label_mode, per-horizon thresholds），删除旧常量
2. `dao/stock_daily.py` - 新增 `ma_40` 字段
3. `dao/model_config.py` - 新增/删除字段
4. `models/training/config.py` - `create_config` 支持变更
5. `models/training/helpers.py` - 新增 `_create_trend_labels`，修改 `_create_classification_labels` 使用多阈值
6. `indicators/ma.py` - MA 周期列表添加 40
7. `api/schemas.py` - 响应 schema 添加 ma_40
8. `api/routers/data.py` - 返回数据中添加 ma_40
9. `api/routers/model_configs.py` - 支持 label_mode 和新的阈值字段

### 前端
1. `api/modelConfig.ts` - 接口类型更新
2. `ModelConfigView.vue` - 添加"标签计算模式"下拉框，移除旧阈值，添加三个新阈值输入

### 文档
1. `api.md` - 更新参数表
2. `database-schema.md` - 更新 JSON 示例
