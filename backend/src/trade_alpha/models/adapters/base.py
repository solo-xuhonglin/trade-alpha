from abc import ABC, abstractmethod
from typing import List, Optional
import pandas as pd
import numpy as np


class BaseTrainerAdapter(ABC):
    """训练适配器基类，处理模型特定的训练逻辑"""

    @abstractmethod
    def create_normalizer(self, config, target_names: List[str]):
        """创建适合该模型的标准化器

        Args:
            config: ModelConfig对象
            target_names: 目标列名列表

        Returns:
            标准化器实例
        """
        pass

    @abstractmethod
    def create_classifier(self, config):
        """创建分类器实例

        Args:
            config: ModelConfig对象

        Returns:
            分类器实例
        """
        pass

    def train(self, classifier, X: np.ndarray, y: np.ndarray, target_names: List[str]):
        """训练模型
        
        Args:
            classifier: 分类器实例
            X: 特征数据
            y: 标签数据
            target_names: 目标列名列表
        """
        classifier.fit(X, y, target_names)


class BaseExecutorAdapter(ABC):
    """执行适配器基类，处理模型特定的回测/实时预测逻辑"""

    @abstractmethod
    def create_normalizer(self, config):
        """创建适合该模型的标准化器

        Args:
            config: ModelConfig对象

        Returns:
            标准化器实例
        """
        pass

    @abstractmethod
    async def load_prediction_data(
        self,
        current_date: str,
        ts_codes: List[str],
        config,
        data_loader
    ) -> pd.DataFrame:
        """加载预测所需的数据

        Args:
            current_date: 当前日期
            ts_codes: 股票代码列表
            config: ModelConfig对象
            data_loader: DataLoader实例

        Returns:
            加载的数据DataFrame
        """
        pass

    @abstractmethod
    def prepare_features(
        self,
        df: pd.DataFrame,
        ts_code: str,
        config
    ) -> Optional[np.ndarray]:
        """为单只股票准备模型输入特征

        Args:
            df: 标准化后的数据
            ts_code: 股票代码
            config: ModelConfig对象

        Returns:
            特征数组，或None（如果数据不足）
        """
        pass
