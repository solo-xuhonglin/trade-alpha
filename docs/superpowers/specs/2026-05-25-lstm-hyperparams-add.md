# LSTM 训练参数新增

## 概述

将 LSTM 训练中硬编码的参数提取到模型配置中，使其可通过前端 UI 调整。

## 新增参数

| 参数名 | 默认值 | 说明 | 分组 |
|--------|--------|------|------|
| lstm_weight_decay | 1e-4 | L2 正则化系数，防止过拟合 | 训练参数 |
| lr_scheduler_factor | 0.5 | 学习率调度器衰减因子 | 训练参数 |
| lr_scheduler_patience | 3 | 学习率调度器等待轮数 | 训练参数 |
| val_size | 0.2 | 验证集比例（按日期划分） | 数据参数 |

## 参数顺序（LSTM 参数区域）

数据参数 > 网络结构 > 训练参数

1. lstm_sequence_length - 输入序列长度（天数）
2. lstm_normalization_window - 标准化统计窗口（天数）
3. val_size - 验证集比例
4. lstm_hidden_size - 隐藏层维度，控制模型容量
5. lstm_num_layers - LSTM 层数
6. lstm_dropout - Dropout 比例，防止过拟合
7. lstm_weight_decay - L2 正则化系数
8. lr_scheduler_factor - 学习率衰减因子
9. lr_scheduler_patience - 学习率调度器等待轮数
10. lstm_epochs - 最大训练轮数
11. lstm_batch_size - 每批训练样本数
12. lstm_learning_rate - 学习率
13. early_stopping_patience - 验证 AUC 不提升时停止的轮数
14. label_smoothing - 标签平滑系数
