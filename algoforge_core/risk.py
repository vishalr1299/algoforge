from dataclasses import dataclass
from math import floor


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade_pct: float = 1.0

    def __post_init__(self):
        if not 0 < self.risk_per_trade_pct <= 100:
            raise ValueError(
                "Risk per trade must be greater than 0 and at most 100%"
            )


class RiskManager:

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()

    def validate_trade_levels(
        self,
        side: str,
        entry_price: float,
        stop_loss_price: float,
        target_price: float | None = None,
    ) -> bool:

        if side not in {"BUY", "SELL"}:
            raise ValueError("Side must be BUY or SELL")

        if entry_price <= 0 or stop_loss_price <= 0:
            raise ValueError("Entry and stop-loss prices must be positive")

        if side == "BUY" and stop_loss_price >= entry_price:
            raise ValueError(
                "BUY stop-loss must be below entry price"
            )

        if side == "SELL" and stop_loss_price <= entry_price:
            raise ValueError(
                "SELL stop-loss must be above entry price"
            )

        if target_price is not None:

            if target_price <= 0:
                raise ValueError("Target price must be positive")

            if side == "BUY" and target_price <= entry_price:
                raise ValueError(
                    "BUY target must be above entry price"
                )

            if side == "SELL" and target_price >= entry_price:
                raise ValueError(
                    "SELL target must be below entry price"
                )

        return True

    def calculate_quantity(
        self,
        capital: float,
        entry_price: float,
        stop_loss_price: float,
        side: str,
        point_value: float = 1.0,
        lot_size: int = 1,
    ) -> int:

        if capital <= 0:
            raise ValueError("Capital must be positive")

        if point_value <= 0:
            raise ValueError("Point value must be positive")

        if lot_size <= 0:
            raise ValueError("Lot size must be positive")

        self.validate_trade_levels(
            side=side,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
        )

        risk_budget = (
            capital * self.config.risk_per_trade_pct / 100
        )

        risk_per_unit = (
            abs(entry_price - stop_loss_price) * point_value
        )

        raw_quantity = floor(risk_budget / risk_per_unit)

        # Quantity must respect the instrument's lot size.
        quantity = (raw_quantity // lot_size) * lot_size

        if quantity < lot_size:
            raise ValueError(
                "Risk budget is too small for one complete lot"
            )

        return quantity
