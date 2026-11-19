import pandas as pd
import pytest

from algoforge_core.backtesting import BacktestEngine
from algoforge_core.strategy import StrategySignal
from algoforge_core.risk import RiskConfig, RiskManager


class SignalStrategy:
    def __init__(self, first_signal):
        self.first_signal = first_signal
        self.call_count = 0
        self.instrument = "TEST_NIFTY"

    def on_candle(self, candle):
        self.call_count += 1

        if self.call_count == 1:
            return self.first_signal

        return StrategySignal(
            strategy_name="Risk Test",
            instrument=self.instrument,
            action="HOLD",
            reason="No new signal",
        )


def make_risk_candles():
    return pd.DataFrame(
        {
            "open": [100, 101, 105, 110],
            "high": [102, 103, 107, 112],
            "low": [98, 99, 94, 108],
            "close": [100, 102, 106, 111],
            "volume": [1000, 1000, 1000, 1000],
        },
        index=pd.date_range(
            "2026-11-16 09:15",
            periods=4,
            freq="5min",
            tz="Asia/Kolkata",
        ),
    )


def make_signal(action, stop_loss=None, target=None):
    return StrategySignal(
        strategy_name="Risk Test",
        instrument="TEST_NIFTY",
        action=action,
        reason="V0.5 integration test",
        stop_loss=stop_loss,
        target=target,
    )


def test_buy_stop_loss_execution():
    strategy = SignalStrategy(
        make_signal("BUY", stop_loss=95)
    )

    result = BacktestEngine(quantity=2).run(
        strategy, make_risk_candles()
    )

    assert len(result.trades) == 1
    assert result.trades[0].side == "BUY"
    assert result.trades[0].exit_price == 95


def test_sell_stop_loss_execution():
    strategy = SignalStrategy(
        make_signal("SELL", stop_loss=106)
    )

    result = BacktestEngine(quantity=2).run(
        strategy, make_risk_candles()
    )

    assert len(result.trades) == 1
    assert result.trades[0].side == "SELL"
    assert result.trades[0].exit_price == 106


def test_buy_target_execution():
    strategy = SignalStrategy(
        make_signal("BUY", target=106)
    )

    result = BacktestEngine(quantity=2).run(
        strategy, make_risk_candles()
    )

    assert len(result.trades) == 1
    assert result.trades[0].side == "BUY"
    assert result.trades[0].exit_price == 106


def test_stop_loss_has_priority_when_both_levels_hit():
    strategy = SignalStrategy(
        make_signal("BUY", stop_loss=95, target=105)
    )

    result = BacktestEngine(quantity=2).run(
        strategy, make_risk_candles()
    )

    assert len(result.trades) == 1
    assert result.trades[0].exit_price == 95


def test_dynamic_position_sizing():
    strategy = SignalStrategy(
        make_signal("BUY", stop_loss=96)
    )

    manager = RiskManager(
        RiskConfig(risk_per_trade_pct=1.0)
    )

    result = BacktestEngine(
        initial_capital=100000,
        risk_manager=manager,
        use_dynamic_sizing=True,
    ).run(strategy, make_risk_candles())

    assert len(result.trades) == 1
    assert result.trades[0].quantity == 200


def test_dynamic_sizing_requires_stop_loss():
    strategy = SignalStrategy(
        make_signal("BUY")
    )

    with pytest.raises(ValueError, match="requires a stop-loss"):
        BacktestEngine(
            use_dynamic_sizing=True
        ).run(strategy, make_risk_candles())
