"""OrderSuggestion Document model for live trading suggestions."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class OrderSuggestion(Document):
    """Live order suggestion document."""

    run_id: PydanticObjectId
    ts_code: str
    stock_name: str

    # 日期
    trade_date: str
    settle_date: str

    # 买卖信息
    action: str                               # "buy"
    order_price: float                        # 最新收盘价
    order_shares: int                         # 建议股数

    # 评分体系
    raw_score: float                          # 模型原始评分
    composite_score: float                    # 加分/扣分调整后
    ranking_score: float = 0.0                # EWMA 平滑后排位分
    rank: int = 0                             # 当日排名

    # 概率
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0

    # 加减分明细
    trend_bonus: float = 0.0
    vol_penalty: float = 0.0
    momentum_bonus: float = 0.0

    # 排除标记
    is_excluded: bool = False
    excluded_reason: Optional[str] = None

    # 状态
    status: str = "pending"
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "order_suggestions"
        indexes = [
            "run_id",
            "ts_code",
            "trade_date",
            "status",
        ]