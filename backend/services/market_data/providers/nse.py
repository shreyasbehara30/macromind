import asyncio
import yfinance as yf
import logging
from datetime import datetime, timezone
from services.market_data.providers.base import MarketDataProvider
from services.market_data.schema import QuoteResponse
from services.market_data.symbols import resolve_yf_symbol

logger = logging.getLogger(__name__)

def _fetch_fast_info(yf_symbol: str):
    # Blocking network call: always run in a thread, never on the event loop.
    ticker = yf.Ticker(yf_symbol)
    info = ticker.fast_info
    return info.last_price, info.previous_close

class NSEMarketProvider(MarketDataProvider):
    """
    Fetches NSE/BSE equity prices using yfinance.
    (NSE direct API could be added here, with session cookie rotation,
    but yfinance is extremely resilient for free tier).
    """
    async def get_quote(self, symbol: str, market: str = "NSE") -> QuoteResponse:
        try:
            # The caller states the market; it is not derived from the suffix.
            yf_symbol = resolve_yf_symbol(symbol, market)

            price, prev_close = await asyncio.to_thread(_fetch_fast_info, yf_symbol)
            change = price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close else 0.0

            return QuoteResponse(
                symbol=symbol, price=price, change=change, change_percent=change_percent,
                currency="INR", market=market, timestamp=datetime.now(timezone.utc),
                source="yfinance"
            )
        except Exception as e:
            logger.error(f"yfinance failed for {symbol} ({market}): {e}")
            return QuoteResponse(
                symbol=symbol, price=0.0, change=0.0, change_percent=0.0,
                currency="INR", market=market, timestamp=datetime.now(timezone.utc),
                source="Unknown", error=str(e)
            )
