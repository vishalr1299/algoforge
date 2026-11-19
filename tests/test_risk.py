import pytest

from algoforge_core.risk import RiskConfig, RiskManager


def test_calculate_buy_quantity():
    manager = RiskManager(RiskConfig(1.0))

    quantity = manager.calculate_quantity(
        capital=100000,
        entry_price=100,
        stop_loss_price=95,
        side="BUY",
    )

    assert quantity == 200


def test_calculate_sell_quantity():
    manager = RiskManager(RiskConfig(1.0))

    quantity = manager.calculate_quantity(
        capital=100000,
        entry_price=100,
        stop_loss_price=105,
        side="SELL",
    )

    assert quantity == 200


def test_quantity_respects_lot_size():
    manager = RiskManager(RiskConfig(1.0))

    quantity = manager.calculate_quantity(
        capital=100000,
        entry_price=100,
        stop_loss_price=95,
        side="BUY",
        lot_size=25,
    )

    assert quantity == 200
    assert quantity % 25 == 0


def test_invalid_buy_stop_loss():
    manager = RiskManager()

    with pytest.raises(ValueError):
        manager.validate_trade_levels(
            "BUY", 100, 105
        )


def test_invalid_sell_stop_loss():
    manager = RiskManager()

    with pytest.raises(ValueError):
        manager.validate_trade_levels(
            "SELL", 100, 95
        )


def test_invalid_buy_target():
    manager = RiskManager()

    with pytest.raises(ValueError):
        manager.validate_trade_levels(
            "BUY", 100, 95, 90
        )


def test_risk_budget_too_small_for_one_lot():
    manager = RiskManager(RiskConfig(0.01))

    with pytest.raises(ValueError):
        manager.calculate_quantity(
            capital=1000,
            entry_price=100,
            stop_loss_price=95,
            side="BUY",
            lot_size=50,
        )


def test_invalid_risk_percentage():
    with pytest.raises(ValueError):
        RiskConfig(0)


def test_invalid_capital():
    manager = RiskManager()

    with pytest.raises(ValueError):
        manager.calculate_quantity(
            capital=0,
            entry_price=100,
            stop_loss_price=95,
            side="BUY",
        )
