from dataclasses import dataclass

@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    exchange: str
    side: str
    quantity: int

@dataclass(frozen=True)
class OrderResult:
    order_id: str
    status: str
    simulated: bool

class PaperBroker:
    """Local simulator. Never sends exchange orders."""
    def __init__(self):
        self.orders = []

    def place_order(self, order: OrderRequest) -> OrderResult:
        if order.quantity <= 0:
            raise ValueError("quantity must be positive")
        if order.side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        result = OrderResult(f"PAPER-{len(self.orders)+1:06d}", "SIMULATED", True)
        self.orders.append(result)
        return result
