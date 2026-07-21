import asyncio
import json
import logging
import websockets
from core.config import settings
from services.market_data.service import market_data_service
from services.realtime.anomaly import anomaly_watcher
from datetime import datetime

logger = logging.getLogger(__name__)

# Mock list of watchlisted US tickers for free tier (up to 50 symbols)
WATCHLISTED_US_TICKERS = ["BINANCE:BTCUSDT", "AAPL", "MSFT", "TSLA", "NVDA"]

class FinnhubWebsocketClient:
    def __init__(self):
        self.uri = f"wss://ws.finnhub.io?token={settings.FINNHUB_API_KEY}"
        self.enabled = settings.FINNHUB_WEBSOCKET_ENABLED
        self.task = None

    async def start(self):
        if not self.enabled or not settings.FINNHUB_API_KEY:
            logger.info("Finnhub Websocket is disabled or missing API key.")
            return

        logger.info("Starting Finnhub Websocket Client...")
        self.task = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            try:
                async with websockets.connect(self.uri) as ws:
                    # Subscribe to tickers
                    for ticker in WATCHLISTED_US_TICKERS:
                        await ws.send(json.dumps({"type": "subscribe", "symbol": ticker}))
                    
                    logger.info("Connected and subscribed to Finnhub WS")
                    
                    while True:
                        message = await ws.recv()
                        data = json.loads(message)
                        
                        if data.get("type") == "trade":
                            for trade in data.get("data", []):
                                symbol = trade["s"]
                                price = trade["p"]
                                timestamp = trade["t"] / 1000.0  # Finnhub provides ms
                                
                                # Update cache and check anomaly
                                await self._handle_trade(symbol, price, timestamp)
            except Exception as e:
                logger.error(f"Finnhub WS error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _handle_trade(self, symbol: str, price: float, timestamp: float):
        # No quote-cache write here. A trade tick carries a price but no previous
        # close, so any change/change_percent written from it would be fabricated.
        # Quotes are served by the REST providers, which return real change values.
        await anomaly_watcher.check_tick(symbol, price, timestamp)

    async def stop(self):
        if self.task:
            self.task.cancel()

finnhub_ws_client = FinnhubWebsocketClient()
