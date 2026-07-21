from abc import ABC, abstractmethod
from services.market_data.schema import QuoteResponse

class MarketDataProvider(ABC):
    @abstractmethod
    async def get_quote(self, symbol: str) -> QuoteResponse:
        pass
