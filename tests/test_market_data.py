import pytest
from algoforge_core.market_data.instruments import parse_instrument_csv, search_instruments
from algoforge_core.market_data.candles import normalize_candles

CSV = ("instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\n"
       "12345,1001,TEST26NOVFUT,TEST,0,2026-11-26,0,0.05,25,FUT,NFO-FUT,NFO\n"
       "12346,1002,TEST26NOV500CE,TEST,0,2026-11-26,500,0.05,25,CE,NFO-OPT,NFO\n")

def test_instrument_parser_and_filter():
    df = parse_instrument_csv(CSV)
    assert len(df) == 2
    assert df.iloc[0]["instrument_token"] == "12345"
    assert len(search_instruments(df, exchange="NFO", instrument_type="CE", underlying="TEST")) == 1

def test_duplicate_instrument_identity_rejected():
    duplicate = CSV + "12347,1003,TEST26NOVFUT,TEST,0,2026-11-26,0,0.05,25,FUT,NFO-FUT,NFO\n"
    with pytest.raises(ValueError, match="Duplicate"):
        parse_instrument_csv(duplicate)

def test_candle_timestamp_normalized_to_utc():
    df = normalize_candles([["2026-11-17T09:15:00+0530", 100, 105, 99, 103, 1000]])
    assert str(df.index.tz) == "UTC"
    assert df.iloc[0]["close"] == 103

def test_invalid_ohlc_rejected():
    with pytest.raises(ValueError, match="high"):
        normalize_candles([["2026-11-17T09:15:00+0530", 100, 98, 99, 103, 1000]])
