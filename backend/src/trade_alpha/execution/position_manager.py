"""Position management module for trade execution."""

from typing import Dict, List, Optional

from trade_alpha.dao import AccountConfig
from .schemas import OrderSuggestion, StockSignal


class PositionManager:
    """Position manager for allocating capital based on trading signals."""

    def __init__(
        self,
        account_config: AccountConfig,
        max_position_pct: float = 0.3,
        min_order_value: float = 5000,
    ):
        self.account_config = account_config
        self.max_position_pct = max_position_pct
        self.min_order_value = min_order_value

    async def allocate(
        self,
        signals: List[StockSignal],
        current_portfolio: Dict[str, int] = {},
        current_cash: float = 0,
    ) -> List[OrderSuggestion]:
        """
        Allocate capital based on signals and generate order suggestions.

        Args:
            signals: List of stock signals
            current_portfolio: Current holdings {ts_code: shares}
            current_cash: Current available cash

        Returns:
            List of order suggestions
        """
        if not signals:
            return []

        # Filter low strength signals
        filtered_signals = [s for s in signals if s.signal_strength >= 0.3]
        
        if not filtered_signals:
            return []

        # Sort by signal strength descending
        sorted_signals = sorted(filtered_signals, key=lambda x: x.signal_strength, reverse=True)

        total_value = current_cash
        for ts_code, shares in current_portfolio.items():
            for signal in sorted_signals:
                if signal.ts_code == ts_code:
                    total_value += signal.current_price * shares
                    break

        if total_value <= 0:
            total_value = self.account_config.initial_capital

        max_position_value = total_value * self.max_position_pct
        suggestions: List[OrderSuggestion] = []

        for signal in sorted_signals:
            # Calculate current position value
            current_shares = current_portfolio.get(signal.ts_code, 0)
            current_position_value = current_shares * signal.current_price

            # Determine target allocation based on signal strength
            allocation_weight = signal.signal_strength / sum(s.signal_strength for s in sorted_signals)
            target_value = total_value * allocation_weight

            # Apply max position constraint
            target_value = min(target_value, max_position_value - current_position_value)

            if target_value <= 0:
                continue

            # Ensure minimum order value
            if target_value < self.min_order_value:
                continue

            # Calculate suggested shares (round down to nearest 100 shares)
            suggested_shares = int(target_value / signal.current_price // 100) * 100

            if suggested_shares <= 0:
                continue

            # Determine action based on existing position
            action = "buy"
            if current_shares > 0:
                additional_shares = suggested_shares - current_shares
                if additional_shares > 0:
                    suggested_shares = additional_shares
                else:
                    continue

            risk_notes = None
            if target_value >= max_position_value:
                risk_notes = "接近最大仓位限制"

            suggestion = OrderSuggestion(
                ts_code=signal.ts_code,
                stock_name="",
                action=action,
                suggested_price=signal.current_price,
                suggested_shares=suggested_shares,
                signal_strength=signal.signal_strength,
                position_reason=signal.reason,
                risk_notes=risk_notes,
                prediction_data=signal.prediction,
            )
            suggestions.append(suggestion)

        return suggestions
