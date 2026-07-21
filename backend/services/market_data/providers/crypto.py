import httpx
import logging
from datetime import datetime, timezone
from services.market_data.providers.base import MarketDataProvider
from services.market_data.schema import QuoteResponse

logger = logging.getLogger(__name__)

class CryptoProvider(MarketDataProvider):
    """
    Fetches Crypto prices from CoinGecko API.
    """
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"

    async def get_quote(self, symbol: str) -> QuoteResponse:
        # CoinGecko expects full coin names or specific ids like 'bitcoin', 'ethereum' for simple price
        # Or search by symbol to get ID, but for simplicity we map common symbols
        symbol_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "USDT": "tether",
            "BNB": "binancecoin",
            "SOL": "solana"
        }
        
        cg_id = symbol_map.get(symbol.upper(), symbol.lower())
        
        url = f"{self.base_url}/simple/price?ids={cg_id}&vs_currencies=usd&include_24hr_change=true"
        
        headers = {}
        from core.config import settings
        if settings.COINGECKO_API_KEY:
            headers["x-cg-demo-api-key"] = settings.COINGECKO_API_KEY
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                if cg_id not in data:
                    return QuoteResponse(
                        symbol=symbol, price=0.0, change=0.0, change_percent=0.0,
                        currency="USD", market="CRYPTO", timestamp=datetime.now(timezone.utc),
                        source="CoinGecko", error=f"Symbol {symbol} not found"
                    )
                    
                price = data[cg_id].get("usd", 0.0)
                change_percent = data[cg_id].get("usd_24h_change", 0.0)
                change = price * (change_percent / 100) if change_percent else 0.0
                
                return QuoteResponse(
                    symbol=symbol.upper(),
                    price=price,
                    change=change,
                    change_percent=change_percent,
                    currency="USD",
                    market="CRYPTO",
                    timestamp=datetime.now(timezone.utc),
                    source="CoinGecko"
                )
            except Exception as e:
                logger.error(f"CoinGecko API error for {symbol}: {e}")
                return QuoteResponse(
                    symbol=symbol, price=0.0, change=0.0, change_percent=0.0,
                    currency="USD", market="CRYPTO", timestamp=datetime.now(timezone.utc),
                    source="CoinGecko", error=str(e)
                )
