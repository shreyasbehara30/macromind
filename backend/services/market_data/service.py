import json
import logging
from redis.asyncio import Redis
from core.config import settings
from services.market_data.schema import QuoteResponse
from services.market_data.providers.nse import NSEMarketProvider
from services.market_data.providers.us import USMarketProvider
from services.market_data.providers.crypto import CryptoProvider
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketDataService:
    def __init__(self):
        self.nse_provider = NSEMarketProvider()
        self.us_provider = USMarketProvider()
        self.crypto_provider = CryptoProvider()
        
        # Setup Upstash Redis
        self.redis = None
        if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
            # We construct the redis connection string from REST URL.
            # In a real setup, using standard redis:// URI might be easier if provided.
            # Assuming user provides standard redis:// URL in UPSTASH_REDIS_REST_URL for now.
            try:
                redis_url = settings.UPSTASH_REDIS_REST_URL
                if redis_url.startswith("http"):
                    host = redis_url.split("://")[-1]
                    redis_url = f"rediss://default:{settings.UPSTASH_REDIS_REST_TOKEN}@{host}:6379"
                self.redis = Redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")

    async def get_quote(self, symbol: str, market: str) -> QuoteResponse:
        market = market.upper()
        cache_key = f"quote:{market}:{symbol}"
        
        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Convert string back to datetime if necessary
                    return QuoteResponse(**data)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        # Fetch from provider
        quote = None
        if market in ["NSE", "BSE"]:
            quote = await self.nse_provider.get_quote(symbol, market)
            if quote and not getattr(quote, 'error', None):
                quote.currency = "INR"
                quote.currency_symbol = "₹"
        elif market in ["US", "FOREX", "COMMODITY"]:
            quote = await self.us_provider.get_quote(symbol)
            if quote and not getattr(quote, 'error', None):
                quote.currency = "USD"
                quote.currency_symbol = "$"
        elif market == "CRYPTO":
            quote = await self.crypto_provider.get_quote(symbol)
            if quote and not getattr(quote, 'error', None):
                quote.currency = "USD"
                quote.currency_symbol = "$"
        else:
            quote = QuoteResponse(
                symbol=symbol, price=0.0, change=0.0, change_percent=0.0,
                currency="USD", currency_symbol="$", market=market, timestamp=datetime.utcnow(),
                source="Unknown", error="Unsupported market"
            )

        # Cache result
        if quote.error is None and self.redis:
            try:
                # Cache valid quote for 60 seconds
                quote_dict = quote.model_dump(mode='json')
                await self.redis.setex(cache_key, 60, json.dumps(quote_dict))
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")

        return quote

market_data_service = MarketDataService()
