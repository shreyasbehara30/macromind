from services.agents.runner import AgentRunner

import httpx
from core.config import settings


async def get_user_holdings(user_id: str) -> str:
    """Real tool: open paper trades for this user session from Supabase."""
    try:
        from services.paper_trading.local_store import get_store

        supabase = get_store()
        res = (
            supabase.table("paper_trades")
            .select("ticker,market,direction,quantity,entry_price")
            .eq("user_session_id", user_id)
            .eq("status", "open")
            .execute()
        )
        rows = res.data or []
        if not rows:
            return f"User {user_id} holds no open paper positions."
        lines = [
            f"- {r.get('ticker')} ({r.get('market')}) {r.get('direction')} "
            f"x{r.get('quantity')} @ {r.get('entry_price')}"
            for r in rows
        ]
        return "Open positions:\n" + "\n".join(lines)
    except Exception as e:
        return f"Holdings lookup failed: {e}"


async def get_active_macro_events() -> str:
    """Real tool: current headlines from the live Finnhub feed."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": settings.FINNHUB_API_KEY},
            )
            if res.status_code == 200:
                news = res.json()[:5]
                if not news:
                    return "No active macro events (feed empty)."
                return "Active macro events:\n" + "\n".join(
                    f"- {n.get('headline', 'Untitled')}" for n in news
                )
            return f"Macro events unavailable (provider status {res.status_code})."
    except Exception as e:
        return f"Macro events fetch failed: {e}"


async def assess_position_risk(ticker: str, event: str) -> str:
    """Real tool: live quote + keyword exposure, no invented numbers."""
    try:
        from services.market_data.symbols import lookup_market
        from services.market_data.service import market_data_service

        market = lookup_market(ticker) or "US"
        quote = await market_data_service.get_quote(ticker, market)
        price = quote.price if not quote.error else None
        exposed = ticker.split(".")[0].lower() in (event or "").lower()
        return (
            f"{ticker} ({market}): live price "
            f"{price if price is not None else 'unavailable'}; "
            f"named in event: {'yes' if exposed else 'no'}; "
            "short-term volatility expected if macro surprise widens spreads."
        )
    except Exception as e:
        return f"Risk assessment failed for {ticker}: {e}"

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
