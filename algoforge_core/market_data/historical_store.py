import sqlite3
from pathlib import Path

import pandas as pd

from algoforge_core.market_data.candles import normalize_candles


def _prepare_candles(candles):
    """Convert candle input into the standard normalized format."""
    if isinstance(candles, pd.DataFrame):
        data = candles.copy()

        if "timestamp" not in data.columns:
            if data.index.name == "timestamp":
                data = data.reset_index()
            else:
                raise ValueError("Candles must contain a timestamp column or index")

        return normalize_candles(data)

    return normalize_candles(candles)


def _validate_identity(instrument_token, interval):
    if not str(instrument_token).strip():
        raise ValueError("instrument_token cannot be empty")

    if not str(interval).strip():
        raise ValueError("interval cannot be empty")


def _utc_string(value):
    if value is None:
        return None

    return pd.to_datetime(value, utc=True).isoformat()


def save_candles(
    db_path,
    instrument_token,
    interval,
    candles
):
    """
    Save normalized historical candles into SQLite.

    Existing candles with the same instrument, interval and
    timestamp are updated.
    """
    _validate_identity(instrument_token, interval)

    df = _prepare_candles(candles)

    if df.empty:
        return 0

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [
        (
            str(instrument_token),
            str(interval),
            timestamp.isoformat(),
            float(row.open),
            float(row.high),
            float(row.low),
            float(row.close),
            int(row.volume),
        )
        for timestamp, row in df.iterrows()
    ]

    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS historical_candles (
                instrument_token TEXT NOT NULL,
                interval TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                PRIMARY KEY (
                    instrument_token,
                    interval,
                    timestamp
                )
            )
        """)

        connection.executemany("""
            INSERT OR REPLACE INTO historical_candles
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

    return len(rows)


def get_candles(
    db_path,
    instrument_token,
    interval,
    start=None,
    end=None
):
    """
    Retrieve historical candles for an instrument and interval.

    Optional start and end timestamps filter the requested range.
    Returned timestamps are UTC.
    """
    _validate_identity(instrument_token, interval)

    db_path = Path(db_path)

    if not db_path.exists():
        return normalize_candles([])

    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM historical_candles
        WHERE instrument_token = ?
          AND interval = ?
    """

    params = [str(instrument_token), str(interval)]

    if start is not None:
        query += " AND timestamp >= ?"
        params.append(_utc_string(start))

    if end is not None:
        query += " AND timestamp <= ?"
        params.append(_utc_string(end))

    query += " ORDER BY timestamp ASC"

    with sqlite3.connect(db_path) as connection:
        df = pd.read_sql_query(query, connection, params=params)

    if df.empty:
        return normalize_candles([])

    return normalize_candles(df)
