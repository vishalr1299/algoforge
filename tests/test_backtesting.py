import pandas as pd
import pytest

from algoforge_core.backtesting import BacktestEngine
from algoforge_core.strategy import StrategySignal


class ScriptedStrategy:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.instrument = "TEST_NIFTY"
        self.name = "Test Strategy"

    def on_candle(self, candle):
        action = next(self.actions)

        return StrategySignal(
            strategy_name=self.name,
            instrument=self.instrument,
            action=action,
            reason="Automated test"
        )


def make_candles():
    return pd.DataFrame(
        {
            "open": [100, 101, 105, 110],
            "high": [102, 103, 107, 112],
            "low": [98, 99, 103, 108],
            "close": [100, 102, 106, 111],
            "volume": [1000, 1000, 1000, 1000],
        },
        index=pd.date_range(
            "2026-11-16 09:15",
            periods=4,
            freq="5min",
            tz="Asia/Kolkata"
        )
    )


def test_long_trade_profit():
    strategy = ScriptedStrategy(
        ["BUY", "HOLD", "EXIT", "HOLD"]
    )

    engine = BacktestEngine(
        initial_capital=100000,
        quantity=2
    )

    result = engine.run(strategy, make_candles())

    assert len(result.trades) == 1
    assert result.trades[0].side == "BUY"
    assert result.trades[0].entry_price == 101
    assert result.trades[0].exit_price == 110
    assert result.trades[0].net_pnl == 18


def test_short_trade_profit():
    strategy = ScriptedStrategy(
        ["SELL", "HOLD", "EXIT", "HOLD"]
    )

    engine = BacktestEngine(
        initial_capital=100000,
        quantity=2
    )

    result = engine.run(strategy, make_candles())

    assert len(result.trades) == 1
    assert result.trades[0].side == "SELL"
    assert result.trades[0].net_pnl == -18


def test_next_candle_execution():
    strategy = ScriptedStrategy(
        ["BUY", "HOLD", "EXIT", "HOLD"]
    )

    result = BacktestEngine(quantity=1).run(
        strategy, make_candles()
    )

    trade = result.trades[0]

    assert trade.entry_time == make_candles().index[1]
    assert trade.exit_time == make_candles().index[3]


def test_open_position_closed_at_final_candle():
    strategy = ScriptedStrategy(
        ["BUY", "HOLD", "HOLD", "HOLD"]
    )

    result = BacktestEngine(quantity=1).run(
        strategy, make_candles()
    )

    assert len(result.trades) == 1
    assert result.trades[0].exit_price == 111
    assert result.trades[0].exit_time == make_candles().index[-1]


def test_brokerage_and_slippage_are_deducted():
    strategy = ScriptedStrategy(
        ["BUY", "HOLD", "EXIT", "HOLD"]
    )

    result = BacktestEngine(
        quantity=2,
        brokerage_per_order=5,
        slippage_bps=10
    ).run(strategy, make_candles())

    trade = result.trades[0]

    assert trade.costs == 10
    assert trade.entry_price == pytest.approx(101.101)
    assert trade.exit_price == pytest.approx(109.89)
    assert trade.net_pnl == pytest.approx(7.578)


def test_position_reversal_from_long_to_short():
    strategy = ScriptedStrategy(
        ["BUY", "HOLD", "SELL", "HOLD"]
    )

    engine = BacktestEngine(
        initial_capital=100000,
        quantity=2
    )

    result = engine.run(strategy, make_candles())

    assert len(result.trades) == 2

    # First position should be long.
    assert result.trades[0].side == "BUY"

    # Second position should be short.
    assert result.trades[1].side == "SELL"

    # First trade closes when the reversal executes.
    assert result.trades[0].exit_time == result.trades[1].entry_time


def test_position_reversal_from_short_to_long():
    strategy = ScriptedStrategy(
        ["SELL", "HOLD", "BUY", "HOLD"]
    )

    engine = BacktestEngine(
        initial_capital=100000,
        quantity=2
    )

    result = engine.run(strategy, make_candles())

    assert len(result.trades) == 2

    # First position should be short.
    assert result.trades[0].side == "SELL"

    # Second position should be long.
    assert result.trades[1].side == "BUY"

    # Both trades should execute their reversal at the same timestamp.
    assert result.trades[0].exit_time == result.trades[1].entry_time
