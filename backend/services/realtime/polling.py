import logging
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.config import settings
from services.market_data.service import market_data_service
from services.realtime.anomaly import anomaly_watcher
from services.agents.macro_research import macro_research_agent

logger = logging.getLogger(__name__)

from services.paper_trading.settlement import settle_paper_trades

# In a real app, this would be fetched from the DB
WATCHLISTED_NON_US_TICKERS = [
    ("RELIANCE.NS", "NSE"),
    ("TCS.NS", "NSE"),
    ("BTC", "CRYPTO"),
    ("ETH", "CRYPTO")
]

class PollingService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        
    def start(self):
        # Add job for 20-second tight polling
        self.scheduler.add_job(
            self.poll_prices, 
            'interval', 
            seconds=20, 
            id='tight_price_polling',
            replace_existing=True
        )
        
        # Add job for paper trade settlement
        self.scheduler.add_job(
            settle_paper_trades,
            'interval',
            seconds=20,
            id='paper_trade_settlement',
            replace_existing=True
        )
        
        # Add job for 5-minute news polling
        self.scheduler.add_job(
            self.poll_news,
            'interval',
            seconds=settings.NEWS_POLL_INTERVAL_HIGH_PRIORITY,
            id='priority_news_polling',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("PollingService started with 20s price and 5m news intervals.")

    async def poll_prices(self):
        """Poll NSE, BSE, Crypto every 20 seconds and feed into AnomalyWatcher."""
        for symbol, market in WATCHLISTED_NON_US_TICKERS:
            try:
                # Force bypass cache by calling provider directly or clearing it, 
                # but MarketDataService uses a 60s cache. Let's assume we update the cache 
                # inside the provider logic or just call it directly.
                quote = await market_data_service.get_quote(symbol, market)
                if quote and quote.price > 0:
                    # check_tick processes the new data point
                    await anomaly_watcher.check_tick(symbol, quote.price, time.time())
            except Exception as e:
                logger.error(f"Error polling {symbol} ({market}): {e}")

    async def poll_news(self):
        """Poll high-priority news sources every 5 minutes."""
        try:
            logger.info("Running priority news poll...")
            # We trigger the macro research agent explicitly for breaking news
            task = "Scan priority breaking news sources (Reuters, RBI, Fed) for high-severity events in the last 5 minutes."
            await macro_research_agent.run(task)
        except Exception as e:
            logger.error(f"Error polling news: {e}")

    def stop(self):
        self.scheduler.shutdown()

polling_service = PollingService()
