import json
import logging
import time
from redis.asyncio import Redis
from core.config import settings
from services.market_data.schema import QuoteResponse
from services.market_data.providers.nse import NSEMarketProvider
from services.market_data.providers.us import USMarketProvider
from services.market_data.providers.crypto import CryptoProvider
from datetime import datetime

logger = logging.getLogger(__name__)

# Process-local quote cache. Every page polls the same handful of symbols
# every 10-20s; without this each poll re-hits Yahoo/CoinGecko/AlphaVantage
# (the last two rate-limit aggressively). 30s TTL, timestamped data.
_MEM_TTL_SECONDS = 30
_mem_cache: dict[str, tuple[float, QuoteResponse]] = {}

# Redis is unreachable in this environment (host does not resolve). Remember
# a failure briefly instead of paying a doomed lookup on every quote.
_redis_dead_until: float = 0.0
_REDIS_RETRY_SECONDS = 300.0


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
                self.redis = Redis.from_url(
                    redis_url, decode_responses=True,
                    socket_connect_timeout=2, socket_timeout=2,
                )
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")

    def _redis_usable(self) -> bool:
        return self.redis is not None and time.time() >= _redis_dead_until

    def _redis_failed(self) -> None:
        global _redis_dead_until
        _redis_dead_until = time.time() + _REDIS_RETRY_SECONDS

    async def get_quote(self, symbol: str, market: str) -> QuoteResponse:
        market = market.upper()
        cache_key = f"quote:{market}:{symbol}"

        hit = _mem_cache.get(cache_key)
        if hit and time.time() - hit[0] < _MEM_TTL_SECONDS:
            return hit[1]

        if self._redis_usable():
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Convert string back to datetime if necessary
                    quote = QuoteResponse(**data)
                    _mem_cache[cache_key] = (time.time(), quote)
                    return quote
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
                self._redis_failed()

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
        if quote.error is None:
            _mem_cache[cache_key] = (time.time(), quote)
            if self._redis_usable():
                try:
                    # Cache valid quote for 60 seconds
                    quote_dict = quote.model_dump(mode='json')
                    await self.redis.setex(cache_key, 60, json.dumps(quote_dict))
                except Exception as e:
                    logger.warning(f"Redis set failed: {e}")
                    self._redis_failed()

        return quote

market_data_service = MarketDataService()
