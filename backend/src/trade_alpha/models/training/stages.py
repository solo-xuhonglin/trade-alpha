"""训练阶段常量定义"""


class Stage:
    """训练阶段定义"""
    DATA_LOAD = "正在加载数据..."
    LABEL_CALC = "正在计算标签..."
    NORMALIZE = "正在标准化数据..."
    TRAINING = "正在训练模型..."
    EVALUATE = "正在评估模型..."
    ANALYSIS = "正在分析数据..."
    DONE = "完成"
