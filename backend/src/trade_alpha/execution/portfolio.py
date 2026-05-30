"""Portfolio management for execution pipeline.

PortfolioManager owns cash and positions state during backtest/live trading.
It handles fee calculation, fund reservation (pre-deduct), settlement
(merge/addition after order fill), and cancellation (refund on unfilled).
All fee inputs/outputs are computed internally — callers never pass fee values.
"""

from typing import Dict, List, Optional, Tuple

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.logging import get_logger

logger = get_logger("execution.portfolio")


class PortfolioManager:
    """Manage cash, positions and fee calculation.

    Core flow:
      1. Strategy calls reserve_funds(ts_code, price, close_prices) when
         deciding to buy. PortfolioManager checks capacity limits, calculates
         affordable shares (multiples of 100), pre-deducts cash + fee.
      2. On settlement, settle_buy() reverses the pre-deduction and
         re-applies with the matched price. settle_sell() deducts sell fees
         and adds proceeds. cancel_reservation() refunds pre-deducted cash.
    """

    def __init__(
        self,
        account_config: AccountConfig,
        initial_capital: float = 100000.0,
        max_positions: int = 10,
        max_position_pct: float = 0.3,
        min_order_value: float = 5000.0,
    ):
        self.cash = initial_capital
        self.positions: Dict[str, PositionEmbed] = {}
        self._account_config = account_config
        self._max_positions = max_positions
        self._max_position_pct = max_position_pct
        self._min_order_value = min_order_value

    # ------------------------------------------------------------------
    # Core public API
    # ------------------------------------------------------------------

    def reserve_funds(self, ts_code: str, price: float,
                      close_prices: Dict[str, float]) -> Tuple[bool, int, float]:
        """Reserve cash for a buy order.

        close_prices is used to calculate total portfolio value
        (cash + positions market value) so that max_position_pct is
        enforced against real market value, not just cash.

        Internal logic:
          1. Already held -> compute remaining capacity under max_position_pct
          2. New buy -> reject if max_positions reached
          3. Calculate affordable shares (100-lot, including buy fee)
          4. Check sufficient cash
          5. Pre-deduct: cash -= shares * price + buy_fee

        Returns:
            (success, shares, fee) — success=True means cash is pre-deducted.
        """
        total_value = self.cash
        for tsc, pos in self.positions.items():
            px = close_prices.get(tsc, 0)
            if px > 0:
                total_value += pos.shares * px

        if ts_code in self.positions:
            pos_value = self.positions[ts_code].shares * price
            max_allowed = total_value * self._max_position_pct
            remaining = max_allowed - pos_value
            if remaining <= self._min_order_value:
                return False, 0, 0
            max_cost = remaining
        else:
            if len(self.positions) >= self._max_positions:
                return False, 0, 0
            max_cost = self.cash * self._max_position_pct

        shares, fee = self._calc_shares(max_cost, price)
        if shares < 100:
            return False, 0, 0
        if shares * price + fee > self.cash:
            return False, 0, 0

        self.cash -= shares * price + fee
        return True, shares, fee

    def settle_buy(self, ts_code: str, stock_name: str,
                   order_shares: int, order_price: float,
                   matched_price: float) -> None:
        """Finalise a filled buy order.

        1. Reverse pre-deduction: cash += order_shares * order_price + buy_fee(order_cost)
        2. Re-apply at matched price: cash -= matched_cost + buy_fee(matched_cost)
        3. Merge into or create position record (weighted avg price, accumulated shares/fees).
        """
        order_cost = order_shares * order_price
        order_fee = self.calc_buy_fee(order_cost)
        self.cash += order_cost + order_fee

        matched_cost = order_shares * matched_price
        matched_fee = self.calc_buy_fee(matched_cost)
        self.cash -= matched_cost + matched_fee

        existing = self.positions.get(ts_code)
        if existing:
            total_shares = existing.shares + order_shares
            total_fee = existing.fee + matched_fee
            avg_price = (existing.shares * existing.buy_price + order_shares * matched_price) / total_shares
            self.positions[ts_code] = PositionEmbed(
                ts_code=ts_code, stock_name=existing.stock_name,
                buy_date=existing.buy_date, buy_price=round(avg_price, 2),
                shares=total_shares, fee=total_fee,
                entry_score=0, entry_3d_prob=0, entry_5d_prob=0,
                hold_days=existing.hold_days,
            )
        else:
            self.positions[ts_code] = PositionEmbed(
                ts_code=ts_code, stock_name=stock_name,
                buy_date="", buy_price=matched_price,
                shares=order_shares, fee=matched_fee,
                entry_score=0, entry_3d_prob=0, entry_5d_prob=0, hold_days=0,
            )

    def settle_sell(self, ts_code: str, shares: int, price: float) -> None:
        """Finalise a filled sell order.

        cash += shares * price - sell_fee - stamp_tax
        Removes the position from portfolio.
        """
        proceeds = shares * price
        fee = self.calc_sell_fee(proceeds)
        tax = self.calc_stamp_tax(proceeds)
        self.cash += proceeds - fee - tax
        self.positions.pop(ts_code, None)

    def cancel_reservation(self, ts_code: str, shares: int, price: float) -> None:
        """Cancel an unfilled buy order, refunding pre-deducted cash."""
        cost = shares * price
        self.cash += cost + self.calc_buy_fee(cost)

    # ------------------------------------------------------------------
    # Read-only helpers
    # ------------------------------------------------------------------

    @property
    def total_position_count(self) -> int:
        return len(self.positions)

    def get_total_value(self, close_prices: Dict[str, float]) -> float:
        """Total portfolio value = cash + positions market value."""
        return self.cash + self.get_market_value(close_prices)

    def get_market_value(self, close_prices: Dict[str, float]) -> float:
        """Market value of all positions = sum(shares * close_price)."""
        total = 0.0
        for ts_code, pos in self.positions.items():
            px = close_prices.get(ts_code, 0)
            if px > 0:
                total += pos.shares * px
        return total

    # ------------------------------------------------------------------
    # Fee helpers (internal, also usable by pipeline for PnL/total_fees)
    # ------------------------------------------------------------------

    def calc_buy_fee(self, cost: float) -> float:
        return max(cost * self._account_config.buy_fee_rate, self._account_config.min_fee)

    def calc_sell_fee(self, cost: float) -> float:
        return max(cost * self._account_config.sell_fee_rate, self._account_config.min_fee)

    def calc_stamp_tax(self, cost: float) -> float:
        return cost * self._account_config.stamp_tax_rate

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_shares(max_cost: float, price: float) -> Tuple[int, float]:
        """Calculate affordable shares (100-lot) and the buy fee.

        Uses an approximate fee rate to estimate — the exact fee computed
        later in settle_buy or cancel_reservation.
        """
        fee_rate = 0.0003
        shares = int(max_cost / (price * (1 + fee_rate)) / 100) * 100
        fee = max(shares * price * fee_rate, 5.0)
        return shares, fee
