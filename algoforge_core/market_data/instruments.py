from __future__ import annotations
from io import StringIO
from pathlib import Path
import pandas as pd

REQUIRED = {"instrument_token", "exchange_token", "tradingsymbol", "name", "last_price",
            "expiry", "strike", "tick_size", "lot_size", "instrument_type", "segment", "exchange"}

def parse_instrument_csv(source: str | Path) -> pd.DataFrame:
    if isinstance(source, Path):
        df = pd.read_csv(source, dtype={"instrument_token": "string", "exchange_token": "string"})
    elif "\n" in source or source.lstrip().startswith("instrument_token,"):
        df = pd.read_csv(StringIO(source), dtype={"instrument_token": "string", "exchange_token": "string"})
    else:
        df = pd.read_csv(source, dtype={"instrument_token": "string", "exchange_token": "string"})
    missing = REQUIRED.difference(df.columns)
    if missing:
        raise ValueError(f"Missing instrument columns: {sorted(missing)}")
    for col in ["instrument_token", "exchange_token", "tradingsymbol", "instrument_type", "segment", "exchange"]:
        df[col] = df[col].astype("string").str.strip()
    df["name"] = df["name"].astype("string").str.strip().replace("", pd.NA)
    df["expiry"] = pd.to_datetime(df["expiry"], errors="coerce").dt.date
    for col in ["strike", "tick_size", "lot_size", "last_price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["instrument_token", "tradingsymbol", "exchange"]:
        if df[col].isna().any() or (df[col].str.len() == 0).any():
            raise ValueError(f"{col} cannot be empty")
    if df["tick_size"].isna().any() or (df["tick_size"] <= 0).any():
        raise ValueError("tick_size must be positive")
    if df["lot_size"].isna().any() or (df["lot_size"] <= 0).any():
        raise ValueError("lot_size must be positive")
    df["lot_size"] = df["lot_size"].astype("int64")
    if df.duplicated(["exchange", "tradingsymbol"]).any():
        raise ValueError("Duplicate exchange + tradingsymbol identity")
    return df.reset_index(drop=True)

def search_instruments(df: pd.DataFrame, text: str = "", exchange: str | None = None,
                       instrument_type: str | None = None, underlying: str | None = None) -> pd.DataFrame:
    result = df.copy()
    if text:
        mask = result["tradingsymbol"].str.contains(text, case=False, na=False) | result["name"].str.contains(text, case=False, na=False)
        result = result[mask]
    if exchange:
        result = result[result["exchange"].str.upper() == exchange.upper()]
    if instrument_type:
        result = result[result["instrument_type"].str.upper() == instrument_type.upper()]
    if underlying:
        mask = result["name"].str.contains(underlying, case=False, na=False) | result["tradingsymbol"].str.contains(underlying, case=False, na=False)
        result = result[mask]
    return result.reset_index(drop=True)
