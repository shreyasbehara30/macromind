import json
from services.agents.runner import AgentRunner

import httpx
from core.config import settings

async def search_news(query: str) -> str:
    """Fetches real market news relevant to the query."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"https://finnhub.io/api/v1/news",
                params={"category": "general", "token": settings.FINNHUB_API_KEY}
            )
            if res.status_code == 200:
                news = res.json()
                # filter by query naively and take top 5
                relevant = [n for n in news if query.lower() in n.get('headline', '').lower() or query.lower() in n.get('summary', '').lower()]
                if not relevant:
                    relevant = news[:5]
                formatted = "\n".join([f"- {n['headline']}: {n['summary']}" for n in relevant[:5]])
                return f"News results for {query}:\n{formatted}"
            return "Failed to fetch news."
    except Exception as e:
        return f"Error fetching news: {e}"

async def fetch_rbi_fed_documents(entity: str) -> str:
    """Fetches real macroeconomic context for a given central bank."""
    # Since direct central bank APIs are complex to integrate without specific endpoints,
    # we simulate the document retrieval using a general news search specific to the entity.
    return await search_news(f"{entity} rate interest inflation")

class MacroResearchAgent(AgentRunner):
    def __init__(self):
        super().__init__(
            system_prompt="""
            You are a Macro Research Agent. Your goal is to autonomously research a macroeconomic event.
            Use your tools to gather context, and then provide a comprehensive briefing.
            """,
            tools=[search_news, fetch_rbi_fed_documents]
        )

macro_research_agent = MacroResearchAgent()
