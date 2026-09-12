import logging
import time
from collections import defaultdict
from core.config import settings
from services.agents.alert_monitoring import alert_monitoring_agent

logger = logging.getLogger(__name__)

class AnomalyWatcher:
    def __init__(self):
        # symbol -> [(timestamp, price), ...]
        self.price_history = defaultdict(list)
        
        # Hardcoded NSE Circuit Breaker logic limits (SEBI rules: 10%, 15%, 20%)
        self.circuit_breaker_thresholds = [10.0, 15.0, 20.0]
        
        # Simple global list to hold active flags for the dashboard
        self.active_flags = []
        # Recent alert-agent decisions surfaced via GET /api/alerts.
        self.recent_decisions = []

    async def check_tick(self, symbol: str, price: float, timestamp: float = None):
        """Pure python logic: Zero LLM involvement. Fast latency check."""
        if not timestamp:
            timestamp = time.time()
            
        history = self.price_history[symbol]
        history.append((timestamp, price))
        
        # Prune old data (older than ANOMALY_WINDOW_MINUTES)
        window_seconds = settings.ANOMALY_WINDOW_MINUTES * 60
        cutoff_time = timestamp - window_seconds
        self.price_history[symbol] = [(t, p) for (t, p) in history if t >= cutoff_time]
        
        # Calculate move in the rolling window
        if len(self.price_history[symbol]) > 1:
            oldest_price = self.price_history[symbol][0][1]
            move_percent = abs((price - oldest_price) / oldest_price) * 100
            
            # 1. Check Circuit Breaker (Mainly for index or individual stocks in India, but applied generically here for mock)
            if symbol in ["^NSEI", "NIFTY"]:
                for cb in self.circuit_breaker_thresholds:
                    if move_percent >= (cb - 0.5): # approaching within 0.5%
                        flag = f"CIRCUIT BREAKER WARNING: {symbol} approaching {cb}% move!"
                        if flag not in self.active_flags:
                            self.active_flags.append(flag)
                            logger.warning(flag)

            # 2. Check 1.5% Rolling Window Anomaly
            if move_percent >= settings.ANOMALY_THRESHOLD_PERCENT:
                logger.info(f"Anomaly detected for {symbol}: {move_percent:.2f}% move in {settings.ANOMALY_WINDOW_MINUTES}m")
                # Out-of-cycle agent trigger
                await self._trigger_alert_agent(symbol, move_percent, price)
                
                # Reset history for this symbol to avoid spamming the agent every subsequent tick
                self.price_history[symbol] = [(timestamp, price)]

    async def _trigger_alert_agent(self, symbol: str, move_percent: float, current_price: float):
        # Formulate explicit task for the agent
        task = f"Asset {symbol} just moved {move_percent:.2f}% rapidly. Current price is {current_price}. Determine if this warrants a high-severity alert to users."
        try:
            # We run the agent synchronously or async depending on the runner.
            # Assuming runner.run() is async
            decision = await alert_monitoring_agent.run(task)
            logger.info(f"Alert Agent Decision for {symbol}: {decision}")
            import time as _time

            self.recent_decisions.append(
                {
                    "symbol": symbol,
                    "move_percent": round(move_percent, 2),
                    "price": current_price,
                    "decision": decision,
                    "at": _time.time(),
                }
            )
            self.recent_decisions = self.recent_decisions[-50:]
        except Exception as e:
            logger.error(f"Failed to run Alert Monitoring Agent out-of-cycle: {e}")

anomaly_watcher = AnomalyWatcher()
