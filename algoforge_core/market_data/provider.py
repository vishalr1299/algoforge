from datetime import datetime
from typing import Protocol
import pandas as pd

class MarketDataProvider(Protocol):
    def get_instruments(self) -> pd.DataFrame: ...
    def get_historical_candles(self, instrument_token: str, interval: str,
                               start: datetime, end: datetime) -> pd.DataFrame: ...
