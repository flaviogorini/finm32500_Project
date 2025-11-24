from dataclasses import dataclass
from datetime import datetime

from abc import ABC, abstractmethod

@dataclass(frozen=True)
class MarketData:
    timestamp: datetime
    symbol: str
    close_price: float
    open_price: float
    high_price: float
    low_price: float
    volume: int

class Strategy(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def generate_signals(self, tick: MarketData) -> list:
        pass
@dataclass
class Trade:
    symbol: str
    timestamp: datetime
    side: str  # 'BUY' or 'SELL'
    qty: int
    price: float
    pnl: float = 0.0  # profit and loss, default to 0.0



