from services.agents.runner import AgentRunner

import httpx
from core.config import settings


async def scan_macro_feed() -> str:
    """Real tool: latest macro headlines from the live Finnhub feed."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": settings.FINNHUB_API_KEY},
            )
            if res.status_code == 200:
                news = res.json()[:5]
                if not news:
                    return "Macro feed is currently empty (provider returned no items)."
                lines = [
                    f"- {n.get('headline', 'Untitled')} ({n.get('source', 'unknown')})"
                    for n in news
                ]
                return "Latest macro events:\n" + "\n".join(lines)
            return f"Macro feed unavailable (provider status {res.status_code})."
    except Exception as e:
        return f"Macro feed fetch failed: {e}"


async def check_watchlist_relevance(event: str, watchlist: list) -> str:
    """Real tool: keyword overlap between the event text and watchlist symbols."""
    try:
        symbols = [str(s) for s in (watchlist or [])]
        if not symbols:
            return "Watchlist is empty; no position is directly exposed to the event."
        event_lower = (event or "").lower()
        hits = [s for s in symbols if s.lower().split(".")[0] in event_lower]
        if hits:
            return f"Event mentions {', '.join(hits)}; those watchlist positions are directly exposed."
        return (
            f"No watchlist symbol ({', '.join(symbols)}) is named in the event text; "
            "exposure is indirect via sector/market beta only."
        )
    except Exception as e:
        return f"Relevance check failed: {e}"

class AlertMonitoringAgent(AgentRunner):
    def __init__(self):
        super().__init__(
            system_prompt="""
            You are an Alert Monitoring Agent.
            Goal: autonomously judge whether a new event is significant enough to trigger a push notification for a user's watchlist.
            Output a JSON decision: { "trigger_alert": true/false, "alert_message": "...", "reasoning": "..." }
            """,
            tools=[scan_macro_feed, check_watchlist_relevance]
        )

alert_monitoring_agent = AlertMonitoringAgent()
