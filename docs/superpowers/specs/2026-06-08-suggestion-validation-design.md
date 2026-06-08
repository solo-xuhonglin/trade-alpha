# 建议验证设计文档

## 概述

在现有每日建议列表页面中，展示历史建议的 N 日实际涨跌幅，与预测概率做对比，验证建议质量。

## 需求

- 不新增加页面，不新增 API 接口
- 在现有 `GET /live-suggestion/suggestions` 接口返回中增加实际涨跌幅字段
- 前端在现有每日建议表格中增加「实际涨跌幅」和「方向是否正确」列
- 支持多周期：3d / 5d / 10d / 20d（与模型预测的 `up_prob_*` 方向一致）
- 涵盖买入和卖出建议

## 数据来源

| 数据 | 来源 |
|------|------|
| 建议数据 | `LiveOrderSuggestion`（trade_date, ts_code, composite_score, up_prob_3d/5d/10d/20d, reason 等） |
| 实际价格 | `StockDaily`（ts_code + trade_date 的 close 价格） |

## 后端改动

### 接口变更：`GET /live-suggestion/suggestions`

现有逻辑不变，在返回逐条建议时增加以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `actual_return_3d` | float/null | 建议日 → 第 3 个交易日的实际涨跌幅（%） |
| `actual_return_5d` | float/null | 建议日 → 第 5 个交易日的实际涨跌幅（%） |
| `actual_return_10d` | float/null | 建议日 → 第 10 个交易日的实际涨跌幅（%） |
| `actual_return_20d` | float/null | 建议日 → 第 20 个交易日的实际涨跌幅（%） |
| `direction_correct_3d` | bool/null | `up_prob_3d > 0.5` 且实际涨 > 0，或 `< 0.5` 且实际跌 < 0 |
| `direction_correct_5d` | bool/null | 同上 |
| `direction_correct_10d` | bool/null | 同上 |
| `direction_correct_20d` | bool/null | 同上 |

未到期的返回 `null`。

### 计算逻辑

模型的 `up_prob_Nd` 对应 N 个**交易日**的收益率（模型标签用 `shift(-N)` 生成），验证时也需要用 N 个交易日后的收盘价。

```python
# list_suggestions 查询建议列表（现有逻辑不变）
suggestions = await LiveOrderSuggestion.find(...).to_list()
items = [_suggestion_to_dict(s) for s in suggestions]
if not suggestions:
    return {"items": items, ...}

# 1. 确定查询范围：所有建议中最早的 trade_date ~ 最晚的 trade_date + 20 个交易日
min_date = min(s.trade_date for s in suggestions)
max_date = max(s.trade_date for s in suggestions)
# 预留 20 个交易日的窗口 + 30 个日历日缓冲
end_date = (datetime.strptime(max_date, "%Y%m%d") + timedelta(days=50)).strftime("%Y%m%d")

# 2. 按 ts_code 分组批量查 stock_daily，按日期排序
ts_codes = list(set(s.ts_code for s in suggestions))
daily_records = await StockDaily.find(
    StockDaily.ts_code.in_(ts_codes),
    StockDaily.trade_date >= min_date,
    StockDaily.trade_date <= end_date,
).sort(+StockDaily.trade_date).to_list()

# 3. 构建每个 ts_code 的有序日期→收盘价映射
from collections import defaultdict
from bisect import bisect_left

ts_dates = defaultdict(list)  # ts_code -> [(trade_date, close)]
for doc in daily_records:
    ts_dates[doc.ts_code].append((doc.trade_date, doc.close))

# 4. 逐条计算
for s, item in zip(suggestions, items):
    dates_with_close = ts_dates.get(s.ts_code, [])
    if not dates_with_close:
        continue
    # 找到建议日所在位置
    all_dates = [d for d, _ in dates_with_close]
    base_idx = bisect_left(all_dates, s.trade_date)
    if base_idx >= len(all_dates) or all_dates[base_idx] != s.trade_date:
        continue  # 建议日本身无数据
    base_close = dates_with_close[base_idx][1]
    if not base_close:
        continue

    for n in [3, 5, 10, 20]:
        target_idx = base_idx + n
        if target_idx < len(dates_with_close):
            target_close = dates_with_close[target_idx][1]
            if target_close:
                ret = (target_close - base_close) / base_close * 100
                item[f"actual_return_{n}d"] = round(ret, 2)
                prob = getattr(s, f"up_prob_{n}d", None)
                if prob is not None:
                    item[f"direction_correct_{n}d"] = (prob > 0.5 and ret > 0) or (prob < 0.5 and ret < 0)
```

### 关键设计点

- **N = 交易日数**：与模型训练一致，`base_idx + N` 取第 N 个后续交易日的收盘价，而不是日历日
- **批量预查**：一次查完所有需要的数据，避免逐条 N+1 查询
- **二分查找定位**：用 `bisect_left` 定位建议日在有序列表中的位置，复杂度 O(log M)
- **建议日本身**：建议日对应的是该日的收盘价（close），代表该日收盘时的行情

### 异常处理

| 场景 | 处理 |
|------|------|
| 未来日期（未到期） | `null` |
| 停牌/退市（查不到数据） | `null` |
| 非交易日对齐 | 取最近的前一个交易日 |

### 文件改动

- `backend/src/trade_alpha/api/routers/live_suggestion.py` — 修改 `list_suggestions` 函数，在返回前增加验证数据计算

## 前端改动

### 文件

- `frontend/src/views/LiveDailySuggestionsView.vue`

### 表格列变化

在现有「预测上涨概率」列后增加两组列：

1. **实际涨跌幅（% ）** — 4 列：3d / 5d / 10d / 20d
   - 正值红色，负值绿色
   - 未到期显示 `—`
2. **方向是否正确** — 4 列：3d / 5d / 10d / 20d
   - ✓ 正确（绿色图标）
   - ✗ 错误（红色图标）
   - `—` 未到期 / 无数据

### 表头结构（与现有列合并）

```
排名 | 股票 | 综合评分 | 预测上涨概率(3d/5d/10d/20d) | 实际涨跌幅(3d/5d/10d/20d) | 方向正确(3d/5d/10d/20d) | ...
```

建议用子列头分组展示，Vuetify `v-data-table` 的 `group-header` slots 实现。

## 测试

### 后端集成测试

在 `test_65_live_suggestion.py` 中新增：

- `test_suggestion_validation_returns` — 验证建议的 `actual_return_*` 字段返回正确
- `test_suggestion_validation_future_date` — 测试未到期日期返回 `null`
- `test_suggestion_validation_direction` — 测试方向判断逻辑

### 前端 E2E 测试

在现有的每日建议页面测试中检查：

- 实际涨跌幅列存在且格式正确
- 方向正确列显示 ✓ 或 ✗

## 不涉及

- 不新增 API 路由
- 不新增 MongoDB 文档/集合
- 不新增定时任务
- 不新增前端页面/路由