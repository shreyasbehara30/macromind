from services.agents.runner import AgentRunner

async def get_user_holdings(user_id: str) -> str:
    # Mock implementation
    return "User holdings: TCS (NSE), RELIANCE (NSE), AAPL (US), BTC (CRYPTO)."

async def get_active_macro_events() -> str:
    # Mock implementation
    return "Active events: US Fed Interest Rate Decision (High), India Retail Inflation Drops (Medium)."

async def assess_position_risk(ticker: str, event: str) -> str:
    # Mock implementation
    return f"Risk assessment for {ticker} given {event}: Moderate risk, likely volatile in short term."

class PortfolioImpactAgent(AgentRunner):
    def __init__(self):
        super().__init__(
            system_prompt="""
            You are a Portfolio Impact Agent.
            Goal: given a user's watchlist/holdings and active macro events, return position-specific impact assessments.
            """,
            tools=[get_user_holdings, get_active_macro_events, assess_position_risk]
        )

portfolio_impact_agent = PortfolioImpactAgent()
