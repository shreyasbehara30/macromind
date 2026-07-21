from services.agents.runner import AgentRunner

async def scan_macro_feed() -> str:
    # Mock implementation
    return "New macro event: RBI announces unexpected rate cut."

async def check_watchlist_relevance(event: str, watchlist: list) -> str:
    # Mock implementation
    return f"Event '{event}' is highly relevant to banking stocks in watchlist."

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
