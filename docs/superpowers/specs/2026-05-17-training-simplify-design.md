# 训练流程简化设计

## 背景

当前训练流程使用按年加载-按月标准化-按月累积的方式，存在两个问题：

1. **流程过度复杂**：内层按月循环使进度粒度过细，训练阶段逐月显示进度对用户没有实际帮助
2. **内存未优化**：虽然原始数据是按年加载的，但标准化后的数据通过 `all_X.append()` 逐月累积，最后 `np.vstack()` 合并时所有标准化数据同时驻留内存

本规格将训练流程简化为按年维度处理，去掉内层月份循环。

## 改动范围

只修改一个文件：

- `backend/src/trade_alpha/predict/training_service.py` — 主流程简化

## 设计

### 主流程变化

**当前（按月循环）：**

```
for year in years:
    加载 year 年数据
    计算 year 年标签
    for month in year_month_list:
        标准化 month 月
        all_X.append(month 数据)
        all_y.append(month 数据)
```

**改为（按年）：**

```
for year in years:
    加载 year 年数据
    计算 year 年标签
    标准化 year 年整年数据
    all_X.append(year 数据)
    all_y.append(year 数据)
```

- 内层 `for month` 循环完全移除
- 每年只做一次标准化，应用 `CrossSectionalNormalizer` 处理整年 DataFrame
- 每年只 append 一次到 all_X/all_y
- 最后仍然是 `np.vstack(all_X) + fit()` 一次训练

### 函数调整

| 当前 | 改为 |
|------|------|
| `_normalize_month(df, config)` → 按月标准化 | `_normalize_data(df, config)` → 通用标准化，函数体不变 |
| `format_progress("norm", year, month=1)` | `format_progress("norm", year)` — 不带 month 参数 |
| `format_progress("train", year, month=1)` | 不再需要，最终只调用一次 `format_progress("done")` |

### 进度回调

进度回调简化，总阶段数从 `len(years) * 2 + 1` 改为 `len(years) * 2 + 1`（阶段数实际上不变，只是内层循环被移除，每个阶段现在对应整年的操作）：

- 阶段 1~n：加载年份 (n = 总年数)
- 阶段 n+1~2n：计算标签
- 阶段 2n+1：训练完成

注意：标准化不再单独统计为一个阶段（它属于"计算标签"阶段之后、append 之前的隐式步骤），这样进度不会被按月循环稀释。

### 回测进度

不涉及此次改动，保留按月更新。

### 不修改的代码

- `_load_year_data()` — 不变
- `_create_classification_labels()` — 不变
- `_create_classifier()` — 不变
- `XGBoostClassifier` — 不变
- `CrossSectionalNormalizer` — 不变
- `get_year_months()` — 保留，用于获取年份列表
- `format_progress()` — 函数签名不变，只改调用参数
- `date_utils.py` — 不变

## 验证

1. 运行 `backend/scripts/test_training_small.py`，确认训练成功
2. 通过 API 触发训练，查询任务进度，确认 progress_message 简洁明了
