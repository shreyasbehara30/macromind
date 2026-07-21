from typing import Literal, Optional
from pydantic import BaseModel
from datetime import datetime

class QuoteResponse(BaseModel):
    symbol: str
    price: float
    change: float
    change_percent: float
    currency: str = "USD"
    currency_symbol: str = "$"
    market: Literal["NSE", "BSE", "US", "CRYPTO", "FOREX", "COMMODITY"]
    timestamp: datetime
    source: str
    error: Optional[str] = None
