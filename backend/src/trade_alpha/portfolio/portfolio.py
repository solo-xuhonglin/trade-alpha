"""Portfolio management module."""

from dataclasses import dataclass


@dataclass
class Trade:
    """Trade record."""
    date: str
    action: str
    price: float
    shares: int
    fee: float
    cash_after: float
    position_after: int


class Portfolio:
    """Account portfolio management."""

    def __init__(
        self,
        initial_capital: float,
        buy_fee_rate: float = 0.0003,
        sell_fee_rate: float = 0.0003,
        stamp_tax_rate: float = 0.001,
        min_fee: float = 5.0,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.position = 0
        self.buy_fee_rate = buy_fee_rate
        self.sell_fee_rate = sell_fee_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.min_fee = min_fee
        self.trades: list[Trade] = []

    def _calculate_buy_fee(self, price: float, shares: int) -> float:
        """Calculate buy fee."""
        amount = price * shares
        fee = amount * self.buy_fee_rate
        return max(fee, self.min_fee)

    def _calculate_sell_fee(self, price: float, shares: int) -> float:
        """Calculate sell fee including stamp tax."""
        amount = price * shares
        fee = amount * self.sell_fee_rate + amount * self.stamp_tax_rate
        return max(fee, self.min_fee)

    def buy(self, date: str, price: float, shares: int) -> Trade:
        """Buy shares."""
        fee = self._calculate_buy_fee(price, shares)
        total_cost = price * shares + fee

        if total_cost > self.cash:
            raise ValueError("Insufficient cash")

        self.cash -= total_cost
        self.position += shares

        trade = Trade(
            date=date,
            action="buy",
            price=price,
            shares=shares,
            fee=fee,
            cash_after=self.cash,
            position_after=self.position,
        )
        self.trades.append(trade)
        return trade

    def sell(self, date: str, price: float, shares: int) -> Trade:
        """Sell shares."""
        if shares > self.position:
            raise ValueError("Insufficient position")

        fee = self._calculate_sell_fee(price, shares)
        total_revenue = price * shares - fee

        self.cash += total_revenue
        self.position -= shares

        trade = Trade(
            date=date,
            action="sell",
            price=price,
            shares=shares,
            fee=fee,
            cash_after=self.cash,
            position_after=self.position,
        )
        self.trades.append(trade)
        return trade
