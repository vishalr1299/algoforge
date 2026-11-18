import pandas as pd

from algoforge_core.market_data.historical_store import (
    save_candles,
    get_candles,
)


def sample_data():
    return pd.DataFrame({
        "timestamp": [
            "2026-11-16 09:15:00+05:30",
            "2026-11-16 09:20:00+05:30",
            "2026-11-16 09:25:00+05:30",
            "2026-11-16 09:30:00+05:30",
            "2026-11-16 09:35:00+05:30",
        ],
        "open": [25000, 25020, 25015, 25040, 25035],
        "high": [25030, 25035, 25045, 25050, 25055],
        "low": [24990, 25010, 25005, 25025, 25020],
        "close": [25020, 25015, 25040, 25035, 25050],
        "volume": [12000, 13500, 11000, 14500, 16000],
    })


def test_save_and_retrieve_candles(tmp_path):
    db = tmp_path / "test.db"

    saved = save_candles(
        db, "SAMPLE_NIFTY", "5minute", sample_data()
    )

    result = get_candles(db, "SAMPLE_NIFTY", "5minute")

    assert saved == 5
    assert len(result) == 5
    assert result["close"].iloc[-1] == 25050


def test_duplicate_candles_are_updated_not_duplicated(tmp_path):
    db = tmp_path / "test.db"
    data = sample_data()

    save_candles(db, "SAMPLE_NIFTY", "5minute", data)
    save_candles(db, "SAMPLE_NIFTY", "5minute", data)

    result = get_candles(db, "SAMPLE_NIFTY", "5minute")

    assert len(result) == 5

    # Change the first candle's close and save it again.
    updated = data.iloc[[0]].copy()
    updated.loc[:, "close"] = 25025
    updated.loc[:, "high"] = 25030

    save_candles(db, "SAMPLE_NIFTY", "5minute", updated)

    result = get_candles(db, "SAMPLE_NIFTY", "5minute")

    assert len(result) == 5
    assert result["close"].iloc[0] == 25025


def test_date_range_filtering(tmp_path):
    db = tmp_path / "test.db"

    save_candles(db, "SAMPLE_NIFTY", "5minute", sample_data())

    result = get_candles(
        db,
        "SAMPLE_NIFTY",
        "5minute",
        start="2026-11-16 09:20:00+05:30",
        end="2026-11-16 09:30:00+05:30",
    )

    assert len(result) == 3


def test_empty_database_returns_empty_result(tmp_path):
    db = tmp_path / "empty.db"

    result = get_candles(db, "SAMPLE_NIFTY", "5minute")

    assert result.empty
    assert result.index.name == "timestamp"
