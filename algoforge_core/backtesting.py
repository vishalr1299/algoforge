from dataclasses import dataclass

import pandas as pd

from algoforge_core.strategy import Strategy, StrategySignal


@dataclass(frozen=True)
class Trade:
    instrument: str
    side: str
    quantity: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    gross_pnl: float
    costs: float
    net_pnl: float


@dataclass(frozen=True)
class BacktestResult:
    trades: list[Trade]
    initial_capital: float
    final_capital: float
    total_pnl: float
    win_rate: float
    max_drawdown: float
    equity_curve: pd.Series


class BacktestEngine:
    def __init__(
    self,
    initial_capital: float = 100000,
    quantity: int = 1,
    brokerage_per_order: float = 0,
    slippage_bps: float = 0,
):
        if initial_capital <= 0:
            raise ValueError("Initial capital must be positive")

        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        if brokerage_per_order < 0:
            raise ValueError("Brokerage cannot be negative")

        if slippage_bps < 0:
            raise ValueError("Slippage cannot be negative")

        self.initial_capital = float(initial_capital)
        self.quantity = int(quantity)
        self.brokerage_per_order = float(brokerage_per_order)
        self.slippage_bps = float(slippage_bps)

    def _execution_price(self, price: float, action: str) -> float:
        slippage = self.slippage_bps / 10000

        if action == "BUY":
            return price * (1 + slippage)

        if action == "SELL":
            return price * (1 - slippage)

        raise ValueError("Action must be BUY or SELL")

    def run(self, strategy: Strategy, candles: pd.DataFrame):

        required = {"open", "high", "low", "close", "volume"}

        # 1. Validate input
        if not isinstance(candles, pd.DataFrame):
            raise TypeError("Candles must be a DataFrame")

        if not required.issubset(candles.columns):
            raise ValueError(f"Candles must contain {sorted(required)}")

        if not candles.index.is_monotonic_increasing:
            raise ValueError("Candles must be sorted by timestamp")

        if candles.index.has_duplicates:
            raise ValueError("Duplicate candle timestamps")

        if candles.empty:
            return BacktestResult(
                trades=[],
                initial_capital=self.initial_capital,
                final_capital=self.initial_capital,
                total_pnl=0.0,
                win_rate=0.0,
                max_drawdown=0.0,
                equity_curve=pd.Series(
                    index=candles.index,
                    dtype=float,
                    name="equity",
                ),
            )

        if candles[list(required)].isna().any().any():
            raise ValueError("Candle data cannot contain missing values")

        # 2. Initialize state
        trades = []
        position = None
        pending_action = None

        cash_equity = self.initial_capital
        equity_values = []

        instrument = getattr(strategy, "instrument", "UNKNOWN")

        # 3. Close-position helper
        def close_position(timestamp, reference_price):
            nonlocal position, cash_equity

            if position is None:
                return

            exit_action = (
                "SELL" if position["side"] == "BUY" else "BUY"
            )

            exit_price = self._execution_price(
                float(reference_price),
                exit_action,
            )

            direction = 1 if position["side"] == "BUY" else -1

            gross_pnl = (
                (exit_price - position["entry_price"])
                * self.quantity
                * direction
            )

            exit_fee = self.brokerage_per_order
            total_costs = position["entry_fee"] + exit_fee
            net_pnl = gross_pnl - total_costs

            cash_equity += gross_pnl - exit_fee

            trades.append(
                Trade(
                    instrument=instrument,
                    side=position["side"],
                    quantity=self.quantity,
                    entry_time=position["entry_time"],
                    exit_time=timestamp,
                    entry_price=position["entry_price"],
                    exit_price=exit_price,
                    gross_pnl=gross_pnl,
                    costs=total_costs,
                    net_pnl=net_pnl,
                )
            )

            position = None

        # 4. Open-position helper
        def open_position(timestamp, reference_price, action):
            nonlocal position, cash_equity

            entry_price = self._execution_price(
                float(reference_price),
                action,
            )

            entry_fee = self.brokerage_per_order
            cash_equity -= entry_fee

            position = {
                "side": action,
                "entry_time": timestamp,
                "entry_price": entry_price,
                "entry_fee": entry_fee,
            }

        # 5. Process candles
        for timestamp, row in candles.iterrows():

            # Execute the previous candle's signal at this candle's open.
            if pending_action in {"BUY", "SELL"}:

                # Close the existing position if the signal is opposite.
                if position is not None:
                    if pending_action != position["side"]:
                        close_position(timestamp, row["open"])

                # Open the new position if we are flat.
                if position is None:
                    open_position(
                        timestamp,
                        row["open"],
                        pending_action,
                    )

            elif pending_action == "EXIT" and position is not None:
                close_position(timestamp, row["open"])

            pending_action = None

            # Generate signal using only the current candle.
            signal = strategy.on_candle(row.to_dict())

            if not isinstance(signal, StrategySignal):
                raise TypeError("Strategy must return StrategySignal")

            if signal.action not in {"BUY", "SELL", "EXIT", "HOLD"}:
                raise ValueError("Invalid strategy action")

            # Schedule action for the next candle.
            if signal.action == "EXIT":

                if position is not None:
                    pending_action = "EXIT"

            elif signal.action in {"BUY", "SELL"}:

                if position is None:
                    pending_action = signal.action

                elif signal.action != position["side"]:
                    # IMPORTANT: Preserve the opposite signal.
                    # The next candle will close and reverse the position.
                    pending_action = signal.action

            # Mark open position to market, including estimated exit costs.
            unrealized_pnl = 0.0

            if position is not None:

                exit_action = (
                    "SELL" if position["side"] == "BUY" else "BUY"
                )

                estimated_exit_price = self._execution_price(
                    float(row["close"]),
                    exit_action
                )

                direction = (
                    1 if position["side"] == "BUY" else -1
                )

                unrealized_pnl = (
                    (estimated_exit_price - position["entry_price"])
                    * self.quantity
                    * direction
                )

                unrealized_pnl -= self.brokerage_per_order

            current_equity = cash_equity + unrealized_pnl
            equity_values.append(current_equity)

        # 6. Liquidate any remaining position at the final candle close.
        if position is not None:

            close_position(
                candles.index[-1],
                candles.iloc[-1]["close"],
            )

            equity_values[-1] = cash_equity

        # 7. Build equity curve.
        equity_curve = pd.Series(
            equity_values,
            index=candles.index,
            name="equity",
        )

        final_capital = cash_equity
        total_pnl = final_capital - self.initial_capital

        # 8. Calculate win rate.
        wins = sum(1 for trade in trades if trade.net_pnl > 0)

        win_rate = (
            wins / len(trades) * 100
            if trades
            else 0.0
        )

        # 9. Calculate maximum drawdown, including initial capital.
        equity_with_initial = pd.concat(
            [
                pd.Series([self.initial_capital]),
                equity_curve.reset_index(drop=True),
            ],
            ignore_index=True,
        )

        running_peak = equity_with_initial.cummax()

        drawdown = (
            (running_peak - equity_with_initial)
            / running_peak.replace(0, float("nan"))
        ) * 100

        max_drawdown = (
            float(drawdown.max())
            if not drawdown.empty
            else 0.0
        )

        # 10. Return results.
        return BacktestResult(
            trades=trades,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_pnl=total_pnl,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            equity_curve=equity_curve,
        )
