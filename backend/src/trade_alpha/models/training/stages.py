"""训练阶段常量定义"""

from dataclasses import dataclass


@dataclass
class Stage:
    """训练阶段定义
    
    Attributes:
        message: 阶段描述文本
        start_pct: 起始百分比
        end_pct: 结束百分比
    """
    message: str
    start_pct: float
    end_pct: float
    
    @property
    def pct(self) -> float:
        """返回起始百分比（用于进度更新）"""
        return self.start_pct


DATA_LOAD = Stage("正在加载数据...", 0, 30)
LABEL_CALC = Stage("正在计算标签...", 30, 40)
NORMALIZE = Stage("正在标准化数据...", 40, 50)
TRAINING = Stage("正在训练模型...", 50, 85)
EVALUATE = Stage("正在评估模型...", 85, 95)
ANALYSIS = Stage("正在分析数据...", 95, 98)
DONE = Stage("完成", 100, 100)
