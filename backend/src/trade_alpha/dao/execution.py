"""ExecutionResult Document model."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from beanie import Document, PydanticObjectId
from pymongo import IndexModel


class AccountSnapshotEmbed(BaseModel):
    """Embedded account snapshot."""

    name: str
    initial_capital: float
    buy_fee_rate: float
    sell_fee_rate: float
    stamp_tax_rate: float
    min_fee: float


class StrategySnapshotEmbed(BaseModel):
    """Embedded strategy config snapshot."""

    name: str
    type: str
    min_order_value: float = 50000.0
    stop_loss_pct: float = -0.1
    max_hold_days: int = 180
    min_hold_days: int = 5
    buy_threshold: float = 0.3
    sell_threshold: float = -0.05
    max_positions: Optional[int] = 6
    max_position_pct: Optional[float] = 0.2
    sell_rank_pct: Optional[float] = 0.15
    hold_score_threshold: Optional[float] = 0.1
    use_momentum_boost: bool = False
    momentum_window: int = 12
    max_momentum_bonus: float = 0.15
    use_momentum_penalty: bool = False
    use_explosion_filter: bool = False
    explosion_price_threshold: float = 0.08
    explosion_volume_ratio: float = 3.0
    explosion_window: int = 5
    use_trend_bonus: bool = False
    trend_bonus_window: int = 15
    trend_bonus_scale: float = 0.03
    trend_r2_threshold: float = 0.30
    trend_max_bonus: float = 0.1
    use_trend_penalty: bool = False
    ranking_smooth_window: int = 8
    ranking_smooth_alpha: float = 0.3
    score_decline_threshold: float = 0.05
    use_score_decline_filter: bool = False
    full_position_pnl_weight: float = 0.5
    use_full_position_sell: bool = False
    full_position_threshold: float = 0.90
    full_position_days: int = 5
    full_position_score_window: int = 15
    full_position_sell_count: int = 1
    use_rank_up_priority: bool = False
    rank_up_window: int = 3
    rank_up_count: int = 1
    rank_up_min_score: float = -0.1
    rank_up_min_improvement_pct: float = 0.15
    market_smooth_alpha: float = 0.3
    market_smooth_window: int = 5
    top_n_retention_pct: float = 0.20
    retention_days: int = 5
    correlation_window: int = 5
    use_phase_strategy: bool = True
    max_daily_buys: int = 2
    atr_stop_multiplier: float = 3.0
    atr_trail_rate: float = 0.5
    rotation_bottom_pct: float = 0.60
    rotation_rank_min_pct: float = 0.30
    rotation_rank_max_pct: float = 0.70
    rotation_use_reversal_check: bool = True
    rotation_was_top_pct: float = 0.15
    rotation_pullback_window: int = 5
    rotation_was_top_window: int = 60
    sel_trend_slope_weight: float = 1.0
    sel_trend_arrangement_weight: float = 1.0
    sel_close_position_20_weight: float = 1.0
    sel_close_position_60_weight: float = 1.0
    sel_bias_20_weight: float = 1.0
    sel_bias_60_weight: float = 1.0
    sel_atr_14_weight: float = 0.3
    sel_log_mv_weight: float = 1.0
    sel_rank_rise_weight: float = 0.2
    sel_ewma_alpha: float = 0.7
    use_weighted_score: bool = False
    weighted_score_factor: float = 0.2
    use_hold_protection: bool = False


class ModelSnapshotEmbed(BaseModel):
    """Embedded model config snapshot."""

    name: str
    model_type: str
    feature_fields: List[str] = Field(default_factory=list)
    standardize_fields: List[str] = Field(default_factory=list)
    winsorize_fields: List[str] = Field(default_factory=list)
    classification_horizons: List[int] = Field(default_factory=list)
    label_mode: str = "trend"
    classification_threshold_3d: float = 0.01
    classification_threshold_5d: float = 0.015
    classification_threshold_10d: float = 0.02
    xgb_n_estimators: int = 100
    xgb_max_depth: int = 6
    xgb_learning_rate: float = 0.1
    xgb_min_child_weight: int = 1
    xgb_subsample: float = 1.0
    xgb_colsample_bytree: float = 1.0
    lstm_hidden_size: int = 64
    lstm_num_layers: int = 2
    lstm_dropout: float = 0.2
    lstm_epochs: int = 50
    lstm_batch_size: int = 256
    lstm_learning_rate: float = 0.0003
    lstm_sequence_length: int = 60
    lstm_normalization_window: int = 120
    use_memmap: bool = False
    lstm_weight_decay: float = 0.0005
    lr_scheduler_factor: float = 0.5
    lr_scheduler_patience: int = 3
    val_size: float = 0.2
    label_smoothing: float = 0.1
    early_stopping_patience: int = 5


class ExecutionResult(Document):
    """Execution result document for MongoDB."""

    account_config_id: PydanticObjectId
    training_id: PydanticObjectId
    name: str
    mode: str = Field(default="backtest")
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    total_fees: float = 0.0
    ts_code: Optional[str] = None
    stock_name: Optional[str] = None
    ts_codes: List[str] = Field(default_factory=list)
    baseline_return: Optional[float] = None
    excess_return: Optional[float] = None
    baseline_max_drawdown: Optional[float] = None
    baseline_annual_return: Optional[float] = None
    baseline_volatility: Optional[float] = None
    baseline_sharpe_ratio: Optional[float] = None
    annual_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    volatility: Optional[float] = None
    avg_hold_days: Optional[float] = None
    trade_win_rate: Optional[float] = None
    account_snapshot: Optional[AccountSnapshotEmbed] = None
    model_snapshot: Optional[ModelSnapshotEmbed] = None
    strategy_snapshot: Optional[StrategySnapshotEmbed] = None
    range_n: Optional[int] = None
    top_n: Optional[int] = None
    momentum_n: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="completed")

    class Settings:
        name = "execution_results"
        indexes = [
            "account_config_id",
            "training_id",
            "ts_code",
            IndexModel("name", unique=True),
        ]
