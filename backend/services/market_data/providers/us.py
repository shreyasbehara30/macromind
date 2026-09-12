import asyncio
import yfinance as yf
import httpx
import logging
from datetime import datetime, timezone
from core.config import settings
from services.market_data.providers.base import MarketDataProvider
from services.market_data.schema import QuoteResponse

logger = logging.getLogger(__name__)

def _fetch_fast_info(symbol: str):
    # Blocking network call: always run in a thread, never on the event loop.
    ticker = yf.Ticker(symbol)
    info = ticker.fast_info
    return info.last_price, info.previous_close

class USMarketProvider(MarketDataProvider):
    """
    Fetches US equity prices using Finnhub, fallback to Alpha Vantage, then yfinance.
    """
    async def get_quote(self, symbol: str) -> QuoteResponse:
        # 1. Try Finnhub
        if settings.FINNHUB_API_KEY:
            try:
                url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={settings.FINNHUB_API_KEY}"
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=5.0)
                    resp.raise_for_status()
                    data = resp.json()
                    if "c" in data and data["c"] != 0:
                        c = data["c"]
                        pc = data["pc"]
                        change = c - pc
                        change_percent = (change / pc) * 100 if pc else 0
                        return QuoteResponse(
                            symbol=symbol, price=c, change=change, change_percent=change_percent,
                            currency="USD", market="US", timestamp=datetime.now(timezone.utc),
                            source="Finnhub"
                        )
            except Exception as e:
                logger.warning(f"Finnhub failed for {symbol}: {e}. Falling back to Alpha Vantage.")

        # 2. Try Alpha Vantage
        if settings.ALPHA_VANTAGE_API_KEY:
            try:
                url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={settings.ALPHA_VANTAGE_API_KEY}"
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=5.0)
                    resp.raise_for_status()
                    data = resp.json()
                    quote = data.get("Global Quote", {})
                    if quote:
                        price = float(quote.get("05. price", 0))
                        change = float(quote.get("09. change", 0))
                        change_percent_str = quote.get("10. change percent", "0%").strip("%")
                        change_percent = float(change_percent_str)
                        return QuoteResponse(
                            symbol=symbol, price=price, change=change, change_percent=change_percent,
                            currency="USD", market="US", timestamp=datetime.now(timezone.utc),
                            source="AlphaVantage"
                        )
            except Exception as e:
                logger.warning(f"Alpha Vantage failed for {symbol}: {e}. Falling back to yfinance.")

        # 3. Fallback to yfinance
        try:
            price, prev_close = await asyncio.to_thread(_fetch_fast_info, symbol)
            change = price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close else 0.0

            return QuoteResponse(
                symbol=symbol, price=price, change=change, change_percent=change_percent,
                currency="USD", market="US", timestamp=datetime.now(timezone.utc),
                source="yfinance"
            )
        except Exception as e:
            logger.error(f"yfinance failed for {symbol}: {e}")
            return QuoteResponse(
                symbol=symbol, price=0.0, change=0.0, change_percent=0.0,
                currency="USD", market="US", timestamp=datetime.now(timezone.utc),
                source="Unknown", error=str(e)
            )
