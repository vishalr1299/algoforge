from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class StrategySignal:
    strategy_name: str
    instrument: str
    action: Literal["BUY", "SELL", "EXIT", "HOLD"]
    reason: str
    stop_loss: float | None = None
    target: float | None = None


class Strategy:
    def on_candle(self, candle: dict[str, float]) -> StrategySignal:
        raise NotImplementedError
