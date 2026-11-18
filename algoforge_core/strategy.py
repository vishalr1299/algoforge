from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class StrategySignal:
    strategy_name: str
    instrument: str
    action: Literal["BUY", "SELL", "EXIT", "HOLD"]
    reason: str

class Strategy:
    def on_candle(self, candle: dict[str, float]) -> StrategySignal:
        raise NotImplementedError
