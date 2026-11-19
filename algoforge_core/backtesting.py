from dataclasses import dataclass

import pandas as pd

from algoforge_core.strategy import Strategy, StrategySignal
from algoforge_core.risk import RiskManager


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
        risk_manager: RiskManager | None = None,
        use_dynamic_sizing: bool = False,
        lot_size: int = 1,
    ):
        if initial_capital <= 0:
            raise ValueError("Initial capital must be positive")

        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        if brokerage_per_order < 0:
            raise ValueError("Brokerage cannot be negative")

        if slippage_bps < 0:
            raise ValueError("Slippage cannot be negative")

        if lot_size <= 0:
            raise ValueError("Lot size must be positive")

        self.initial_capital = float(initial_capital)
        self.quantity = int(quantity)
        self.brokerage_per_order = float(brokerage_per_order)
        self.slippage_bps = float(slippage_bps)

        self.risk_manager = risk_manager or RiskManager()
        self.use_dynamic_sizing = bool(use_dynamic_sizing)
        self.lot_size = int(lot_size)

    def _execution_price(self, price: float, action: str) -> float:
        slippage = self.slippage_bps / 10000

        if action == "BUY":
            return price * (1 + slippage)

        if action == "SELL":
            return price * (1 - slippage)

        raise ValueError("Action must be BUY or SELL")

    def run(self, strategy: Strategy, candles: pd.DataFrame):

        required = {"open", "high", "low", "close", "volume"}

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

        trades = []
        position = None
        pending_signal = None

        cash_equity = self.initial_capital
        equity_values = []

        instrument = getattr(strategy, "instrument", "UNKNOWN")

        # Close an existing position.
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
                * position["quantity"]
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
                    quantity=position["quantity"],
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

        # Open a position using fixed or dynamically calculated quantity.
        def open_position(timestamp, reference_price, signal):
            nonlocal position, cash_equity

            action = signal.action

            entry_price = self._execution_price(
                float(reference_price),
                action,
            )

            stop_loss = getattr(signal, "stop_loss", None)
            target = getattr(signal, "target", None)

            if stop_loss is not None:
                self.risk_manager.validate_trade_levels(
                    side=action,
                    entry_price=entry_price,
                    stop_loss_price=float(stop_loss),
                    target_price=(
                        float(target) if target is not None else None
                    ),
                )

            elif target is not None:
                target = float(target)

                if target <= 0:
                    raise ValueError("Target price must be positive")

                if action == "BUY" and target <= entry_price:
                    raise ValueError("BUY target must be above entry")

                if action == "SELL" and target >= entry_price:
                    raise ValueError("SELL target must be below entry")

            if self.use_dynamic_sizing:

                if stop_loss is None:
                    raise ValueError(
                        "Dynamic sizing requires a stop-loss price"
                    )

                trade_quantity = self.risk_manager.calculate_quantity(
                    capital=cash_equity,
                    entry_price=entry_price,
                    stop_loss_price=float(stop_loss),
                    side=action,
                    lot_size=self.lot_size,
                )

            else:
                trade_quantity = self.quantity

            entry_fee = self.brokerage_per_order
            cash_equity -= entry_fee

            position = {
                "side": action,
                "quantity": trade_quantity,
                "entry_time": timestamp,
                "entry_price": entry_price,
                "entry_fee": entry_fee,
                "stop_loss": (
                    float(stop_loss) if stop_loss is not None else None
                ),
                "target": (
                    float(target) if target is not None else None
                ),
            }

        # Check intrabar stop-loss and target levels.
        def check_exit_levels(timestamp, row):
            if position is None:
                return

            side = position["side"]
            stop = position["stop_loss"]
            target = position["target"]

            open_price = float(row["open"])
            high_price = float(row["high"])
            low_price = float(row["low"])

            # Stop-loss has priority if both levels are touched.
            if side == "BUY" and stop is not None:

                if open_price <= stop:
                    close_position(timestamp, open_price)
                    return

                if low_price <= stop:
                    close_position(timestamp, stop)
                    return

            elif side == "SELL" and stop is not None:

                if open_price >= stop:
                    close_position(timestamp, open_price)
                    return

                if high_price >= stop:
                    close_position(timestamp, stop)
                    return

            # Target execution uses the target price conservatively.
            if side == "BUY" and target is not None:

                if high_price >= target:
                    close_position(timestamp, target)
                    return

            elif side == "SELL" and target is not None:

                if low_price <= target:
                    close_position(timestamp, target)
                    return

        # Process historical candles.
        for timestamp, row in candles.iterrows():

            # Execute the previous candle's signal at the current open.
            if pending_signal is not None:

                action = pending_signal.action

                if action in {"BUY", "SELL"}:

                    if position is not None:
                        if action != position["side"]:
                            close_position(timestamp, row["open"])

                    if position is None:
                        open_position(
                            timestamp,
                            row["open"],
                            pending_signal,
                        )

                elif action == "EXIT" and position is not None:
                    close_position(timestamp, row["open"])

            pending_signal = None

            # Check stop-loss and target on the current candle.
            check_exit_levels(timestamp, row)

            # Generate a new signal using the current candle.
            signal = strategy.on_candle(row.to_dict())

            if not isinstance(signal, StrategySignal):
                raise TypeError("Strategy must return StrategySignal")

            if signal.action not in {"BUY", "SELL", "EXIT", "HOLD"}:
                raise ValueError("Invalid strategy action")

            if signal.action == "EXIT":

                if position is not None:
                    pending_signal = signal

            elif signal.action in {"BUY", "SELL"}:

                if position is None:
                    pending_signal = signal

                elif signal.action != position["side"]:
                    pending_signal = signal

            # Mark open positions to market.
            unrealized_pnl = 0.0

            if position is not None:

                exit_action = (
                    "SELL" if position["side"] == "BUY" else "BUY"
                )

                estimated_exit_price = self._execution_price(
                    float(row["close"]),
                    exit_action,
                )

                direction = (
                    1 if position["side"] == "BUY" else -1
                )

                unrealized_pnl = (
                    (estimated_exit_price - position["entry_price"])
                    * position["quantity"]
                    * direction
                )

                unrealized_pnl -= self.brokerage_per_order

            current_equity = cash_equity + unrealized_pnl
            equity_values.append(current_equity)

        # Liquidate any remaining position at the final candle close.
        if position is not None:

            close_position(
                candles.index[-1],
                candles.iloc[-1]["close"],
            )

            equity_values[-1] = cash_equity

        equity_curve = pd.Series(
            equity_values,
            index=candles.index,
            name="equity",
        )

        final_capital = cash_equity
        total_pnl = final_capital - self.initial_capital

        wins = sum(1 for trade in trades if trade.net_pnl > 0)

        win_rate = (
            wins / len(trades) * 100
            if trades
            else 0.0
        )

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

        return BacktestResult(
            trades=trades,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_pnl=total_pnl,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            equity_curve=equity_curve,
        )
