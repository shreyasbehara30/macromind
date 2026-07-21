from services.agents.runner import AgentRunner
from services.market_data.service import market_data_service

import httpx
from core.config import settings
import yfinance as yf

async def get_live_price(symbol: str, market: str) -> str:
    quote = await market_data_service.get_quote(symbol, market)
    return quote.model_dump_json()

async def get_sector_momentum(sector: str) -> str:
    """Gets recent performance of a sector using an ETF proxy via yfinance."""
    sector_etf_map = {
        "tech": "XLK", "finance": "XLF", "healthcare": "XLV", 
        "energy": "XLE", "consumer": "XLY", "industrial": "XLI"
    }
    etf = sector_etf_map.get(sector.lower(), "SPY")
    try:
        ticker = yf.Ticker(etf)
        hist = ticker.history(period="5d")
        if not hist.empty and len(hist) >= 2:
            start = hist['Close'].iloc[0]
            end = hist['Close'].iloc[-1]
            pct_change = ((end - start) / start) * 100
            return f"Momentum for {sector} (proxy {etf}): {pct_change:.2f}% over 5 days."
        return f"Sector {sector} momentum: Unknown (failed to fetch)"
    except Exception as e:
        return f"Error fetching sector momentum: {e}"

async def search_recent_company_news(symbol: str) -> str:
    """Fetches recent news for a specific stock symbol."""
    try:
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=7)
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"https://finnhub.io/api/v1/company-news",
                params={
                    "symbol": symbol,
                    "from": start.strftime("%Y-%m-%d"),
                    "to": end.strftime("%Y-%m-%d"),
                    "token": settings.FINNHUB_API_KEY
                }
            )
            if res.status_code == 200:
                news = res.json()
                if not news:
                    return f"No recent news found for {symbol}."
                formatted = "\n".join([f"- {n['headline']}: {n['summary']}" for n in news[:3]])
                return f"Recent news for {symbol}:\n{formatted}"
            return f"Failed to fetch news for {symbol}."
    except Exception as e:
        return f"Error fetching news: {e}"

async def get_macro_signals() -> str:
    """Gets top level macro indicators."""
    try:
        ticker = yf.Ticker("^VIX")
        vix = ticker.history(period="1d")['Close'].iloc[-1]
        return f"Macro signals: VIX is at {vix:.2f}."
    except:
        return "Macro signals: VIX could not be fetched."

class StockAnalysisAgent(AgentRunner):
    def __init__(self):
        super().__init__(
            system_prompt="""
            You are a Stock Analysis Agent. 
            Goal: produce a buy/sell/hold verdict with a confidence score (0-100), entry zone, target, and stop-loss for a given ticker.
            You must output your final verdict as a JSON object containing: 
            verdict, confidence_score, entry_zone, target, stop_loss, reasoning.
            Also, you MUST include the SEBI disclaimer field in the JSON payload:
            "sebi_disclaimer": "This is AI-generated analysis. Not financial advice. Please consult a registered advisor."
            """,
            tools=[get_live_price, get_sector_momentum, search_recent_company_news, get_macro_signals]
        )

stock_analysis_agent = StockAnalysisAgent()
