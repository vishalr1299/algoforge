import pandas as pd

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

def normalize_candles(records) -> pd.DataFrame:
    if isinstance(records, pd.DataFrame):
        df = records.copy()
    else:
        df = pd.DataFrame(records, columns=COLUMNS[:len(records[0])] if records else COLUMNS)
    if df.empty:
        empty = pd.DataFrame(columns=COLUMNS[1:])
        empty.index = pd.DatetimeIndex([], tz="UTC", name="timestamp")
        return empty
    if not set(COLUMNS).issubset(df.columns):
        raise ValueError(f"Candles must contain {COLUMNS}")
    df = df[COLUMNS].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    if df["timestamp"].isna().any():
        raise ValueError("Invalid candle timestamp")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[["open", "high", "low", "close", "volume"]].isna().any().any():
        raise ValueError("OHLCV values must be numeric and non-null")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be positive")
    if (df["volume"] < 0).any():
        raise ValueError("Volume cannot be negative")
    if (df["high"] < df[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("Candle high is inconsistent with OHLC values")
    if (df["low"] > df[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("Candle low is inconsistent with OHLC values")
    df = df.sort_values("timestamp")
    if df["timestamp"].duplicated().any():
        raise ValueError("Duplicate candle timestamps")
    df["volume"] = df["volume"].astype("int64")
    return df.set_index("timestamp")
