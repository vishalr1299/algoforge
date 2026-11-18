import pytest
from algoforge_core.broker import OrderRequest, PaperBroker

def test_paper_order_is_simulated():
    result = PaperBroker().place_order(OrderRequest("NIFTY_TEST", "NFO", "BUY", 1))
    assert result.simulated is True
    assert result.status == "SIMULATED"

def test_zero_quantity_is_rejected():
    with pytest.raises(ValueError):
        PaperBroker().place_order(OrderRequest("NIFTY_TEST", "NFO", "BUY", 0))
