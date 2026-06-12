# 后端脚本说明

## 目录

`backend/scripts/` 下的脚本按用途分为四类：

| 类别 | 脚本 | 说明 |
|------|------|------|
| **策略评估** | `train_model.py` | 训练预测模型 |
| | `backtest_single.py` | 单股票策略评估 |
| | `backtest_portfolio.py` | 组合策略评估 |
| | `run_live_suggestion.py` | 运行实盘建议流水线（不需要账户配置） |
| **数据管理** | `activate_stocks.py` | 将有指标数据且超过200条的股票设为 active |
| | `check_stock_sync_status.py` | 检查股票同步状态 |
| | `clean_stock_data.py` | 清理股票数据 |
| | `reset_business_data.py` | 重置业务数据 |
| | `backfill_data_count.py` | 回填股票日线数据条数和最新日期 |
| | `calculate_indicators.py` | 计算新指标（RSI、ATR、OBV）- 并行版本 |
| | `fast_calculate_indicators.py` | 快速计算新指标（RSI、ATR、OBV）- 优化版本 |
| **持仓管理** | `sync_live_portfolio.py` | 同步实盘持仓（增/删/改） |
| **服务管理** | `check_server.py` | 检查后端服务是否运行 |
| **测试调试** | `test_trades.py` | 检查回测结果和交易记录数据 |
| | `check_prediction_scores.py` | 检查回测快照中的预测分数 |
| | `clean_backtests.py` | 清理所有回测结果、快照和交易记录 |

---

## 策略评估

### train_model.py — 训练预测模型

```bash
python scripts/train_model.py
python scripts/train_model.py --train-start 20160101 --train-end 20241231
```

流程：
1. 获取所有活跃股票（排除测试股票）
2. 筛选有足够数据的股票
3. 创建/使用 `prod_model_config` 模型配置
4. 删除旧的 `prod_training` 训练记录
5. 执行训练，保存为 `prod_training`

### backtest_single.py — 单股票策略评估

```bash
# 单只股票
python scripts/backtest_single.py --ts-code 000858.SZ

# 批量模式（遍历所有活跃股票）
python scripts/backtest_single.py
```

流程：
1. 按名称 `prod_training` 查找训练记录
2. 创建/使用 `prod_account_config` 账户配置
3. 执行单股票回测
4. 批量模式输出对比表格

可选参数：`--backtest-start`、`--backtest-end`

### backtest_multi.py — 多股票策略评估

```bash
python scripts/backtest_multi.py
python scripts/backtest_multi.py --max-positions 20
```

流程：
1. 按名称 `prod_training` 查找训练记录
2. 创建/使用 `prod_account_config` 账户配置
3. 筛选有数据的股票
4. 执行组合回测
5. 输出结果（含基线比较）

可选参数：`--backtest-start`、`--backtest-end`、`--max-positions`

---

## 数据管理

### check_stock_sync_status.py

```bash
python scripts/check_stock_sync_status.py
```

检查数据库中各股票的同步状态统计（pending 数量、active 数量等）。

### clean_stock_data.py

```bash
python scripts/clean_stock_data.py
```

清理所有股票数据：删除日线数据和股票列表，用于重新同步。

### reset_business_data.py

```bash
python scripts/reset_business_data.py
```

重置业务数据：清理账户配置、策略配置、模型配置、训练结果、回测结果等，保留股票数据。

### backfill_data_count.py

```bash
python scripts/backfill_data_count.py
```

从 `stock_daily` 集合聚合统计每只股票的日线数据条数和最新交易日，回填到 `stock_list` 的 `data_count` 和 `latest_date` 字段。该数据由调度器每小时自动更新，此脚本用于手动触发或初始回填。

### calculate_indicators.py

```bash
python scripts/calculate_indicators.py
python scripts/calculate_indicators.py --ts-codes 002594.SZ 600519.SH
python scripts/calculate_indicators.py --limit 10 --concurrency 10
```

计算新指标（RSI、ATR、OBV）并存储到数据库，支持并行处理。该脚本调用 `indicators.service.calculate_all_indicators`，默认处理所有 `active` 状态的股票。

可选参数：
- `--ts-codes`: 指定股票代码列表
- `--limit`: 限制处理股票数量（用于测试）
- `--concurrency`: 并发任务数，默认 20

### fast_calculate_indicators.py

```bash
python scripts/fast_calculate_indicators.py
python scripts/fast_calculate_indicators.py --ts-codes 002594.SZ 600519.SH
python scripts/fast_calculate_indicators.py --limit 10 --concurrency 10
```

快速计算新指标（RSI、ATR、OBV）的优化版本，直接使用 pandas 计算并分批更新数据库，不重复计算已有指标。性能优于 `calculate_indicators.py`，适合大规模批量处理。

可选参数：
- `--ts-codes`: 指定股票代码列表
- `--limit`: 限制处理股票数量（用于测试）
- `--concurrency`: 并发任务数，默认 20

---

## 持仓管理

### sync_live_portfolio.py — 同步实盘持仓

通过 JSON 文件指定目标持仓，自动对比当前 API 中的持仓数据并执行增/删/改操作。

```bash
# 预览变更（不实际执行）
python scripts/sync_live_portfolio.py positions.json --dry-run

# 实际执行同步
python scripts/sync_live_portfolio.py positions.json
```

#### JSON 格式

```json
{
    "603256.SH": {"name": "宏和科技", "shares": 1000, "cost_price": 189.789},
    "688347.SH": {"name": "华虹公司", "shares": 900, "cost_price": 209.056},
    "unknown_1": {"name": "生益科技", "shares": 1500, "cost_price": 147.757}
}
```

- **已知 ts_code**：直接以 `ts_code` 为 key
- **未知 ts_code**：key 使用任意不含 `.` 的字符串，脚本会自动通过名称搜索匹配股票代码
- 脚本会删除目标中不存在的持仓、更新股数/成本价变化的持仓、新增目标中未有的持仓

---

## 服务管理

### 前置条件

使用 `service.bat` / `service.ps1` 管理服务前，需确保后端虚拟环境已创建并安装依赖：

```bash
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

`service.ps1` 会使用 `backend\.venv\Scripts\python.exe` 启动后端。如果虚拟环境缺少依赖（如 `fastapi`），后端进程会静默失败。

### check_server.py

```bash
python scripts/check_server.py
```

通过健康检查接口检查后端服务是否运行。可用 `service.ps1` 或 `service.bat` 管理服务启停：

```powershell
# 启动服务
service.bat start

# 停止服务
service.bat stop

# 重启服务（自动清理 debug.log、info.log、warning.log、error.log）
service.bat restart
```

> 服务管理优先使用 `service.bat` / `service.ps1`，检查服务状态优先使用 `check_server.py`。

---

## 测试调试

### test_trades.py

```bash
python scripts/test_trades.py
```

检查数据库中的回测结果和交易记录数据，同时直接测试 API 函数。支持查看最新回测的详细交易列表。

### check_prediction_scores.py

```bash
python scripts/check_prediction_scores.py
python scripts/check_prediction_scores.py --ts-code 601398.SH
```

检查回测快照中指定股票（默认比亚迪）的预测分数分布。输出分数范围、正负比例、前 10 条和最后 10 条记录。

### clean_backtests.py

```bash
python scripts/clean_backtests.py
```

清理数据库中所有回测结果、关联的快照和交易记录。用于在模型迭代后需要全量重跑回测的场景。

### test_training_small.py

```bash
python scripts/test_training_small.py
```

用单只股票（比亚迪 `002594.SZ`）和 `test_model_config` 配置快速测试训练流程，带进度回调输出。用于训练流程的开发调试，训练结果保存为 `test_run`。
