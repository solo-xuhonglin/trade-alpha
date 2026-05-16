# 后端脚本说明

## 目录

`backend/scripts/` 下的脚本按用途分为三类：

| 类别 | 脚本 | 说明 |
|------|------|------|
| **策略评估** | `train_model.py` | 训练预测模型 |
| | `backtest_single.py` | 单股票策略评估 |
| | `backtest_portfolio.py` | 组合策略评估 |
| **数据管理** | `activate_stocks.py` | 将有指标数据且超过200条的股票设为 active |
| | `check_stock_sync_status.py` | 检查股票同步状态 |
| | `clean_stock_data.py` | 清理股票数据 |
| | `reset_business_data.py` | 重置业务数据 |
| **服务管理** | `check_server.py` | 检查后端服务是否运行 |
| **测试调试** | `test_trades.py` | 检查交易记录数据 |

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
2. 创建/使用 `prod_portfolio` 账户配置
3. 执行单股票回测
4. 批量模式输出对比表格

可选参数：`--backtest-start`、`--backtest-end`

### backtest_portfolio.py — 组合策略评估

```bash
python scripts/backtest_portfolio.py
python scripts/backtest_portfolio.py --max-positions 20
```

流程：
1. 按名称 `prod_training` 查找训练记录
2. 创建/使用 `prod_portfolio` 账户配置
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

---

## 服务管理

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

# 重启服务（删除日志）
service.bat restart

# 重启服务（保留日志）
service.bat restart -KeepLogs
```

> 服务管理优先使用 `service.bat` / `service.ps1`，检查服务状态优先使用 `check_server.py`。

---

## 测试调试

### test_trades.py

```bash
python scripts/test_trades.py
```

检查数据库中的回测结果和交易记录数据，同时直接测试 API 函数。
