from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from services.market_data.service import market_data_service
from services.market_data.symbols import MARKETS, lookup_market, resolve_yf_symbol, UnknownMarketError
from services.agents.stock_analysis import stock_analysis_agent
from services.agents.portfolio_impact import portfolio_impact_agent
from services.paper_trading.db import get_supabase
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

from api.paper import router as paper_router
router.include_router(paper_router)

class PickRequest(BaseModel):
    market: str
    horizon: str

@router.get("/dashboard")
async def get_dashboard(request: Request):
    """
    Returns ticker prices, sector momentum, and top macro events.
    """
    import asyncio
    import yfinance as yf
    import httpx
    from core.config import settings

    tickers = [
        ("^NSEI", "NSE"), ("BTC", "CRYPTO"), ("^GSPC", "US")
    ]
    
    tasks = [market_data_service.get_quote(sym, mkt) for sym, mkt in tickers]
    quotes = await asyncio.gather(*tasks, return_exceptions=True)
    
    valid_quotes = [q.model_dump() for q in quotes if not isinstance(q, Exception)]

    try:
        xlk = yf.Ticker("XLK").history(period="5d")
        xlf = yf.Ticker("XLF").history(period="5d")
        it_change = ((xlk['Close'].iloc[-1] - xlk['Close'].iloc[0]) / xlk['Close'].iloc[0]) * 100
        bank_change = ((xlf['Close'].iloc[-1] - xlf['Close'].iloc[0]) / xlf['Close'].iloc[0]) * 100
        sector_momentum = [
            {"sector": "IT", "change": round(it_change, 2)},
            {"sector": "Banking", "change": round(bank_change, 2)}
        ]
    except Exception as e:
        logger.error(f"Sector momentum fetch failed: {e}")
        sector_momentum = []

    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": settings.FINNHUB_API_KEY}
            )
            if res.status_code == 200:
                news = res.json()
                top_events = [
                    {"id": str(n.get('id', i)), "title": n.get('headline', 'News'), "severity": None}
                    for i, n in enumerate(news[:3])
                ]
            else:
                top_events = []
    except Exception as e:
        logger.error(f"Top events fetch failed: {e}")
        top_events = []

    return {
        "tickers": valid_quotes,
        "sector_momentum": sector_momentum,
        "top_events": top_events
    }

@router.get("/events")
async def get_events(request: Request, page: int = 1, limit: int = 10):
    """
    Returns paginated, filterable macro event feed.
    """
    import httpx
    from core.config import settings
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": settings.FINNHUB_API_KEY}
            )
            if res.status_code == 200:
                news = res.json()
                events = []
                for n in news[:limit]:
                    published = n.get('datetime')
                    events.append({
                        "id": str(n.get('id')),
                        "severity": None,
                        "headline": n.get('headline'),
                        "source": n.get('source'),
                        "timestamp": datetime.fromtimestamp(published, tz=timezone.utc).isoformat() if published else None,
                        "sectors": []
                    })
                return {"events": events, "page": page, "total": len(news)}
    except Exception as e:
        logger.error(f"Events fetch failed: {e}")
    return {"events": [], "page": page, "total": 0}

@router.get("/events/{id}/impact")
async def get_event_impact(request: Request, id: str):
    """
    Returns full chain reaction + beneficiary/risk stocks.
    """
    import httpx
    import json
    import re
    from core.config import settings
    from services.agents.macro_research import macro_research_agent
    
    headline = f"Market event {id}"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": settings.FINNHUB_API_KEY}
            )
            if res.status_code == 200:
                news = res.json()
                for n in news:
                    if str(n.get('id')) == id:
                        headline = n.get('headline')
                        break
    except:
        pass
        
    try:
        prompt = f"""
        Analyze the impact of this event: '{headline}'.
        DO NOT call any tools to output the final result. Just return a raw JSON object EXACTLY matching this structure (and nothing else):
        {{
            "title": "{headline}",
            "severity": "<High, Medium or Low, judged from the event itself>",
            "ai_analysis": "brief analysis",
            "chain_reaction": ["point 1", "point 2"],
            "stocks": {{
                "beneficiaries": [{{"ticker": "<ticker>", "reason": "why"}}],
                "pressure": [{{"ticker": "<ticker>", "reason": "why"}}]
            }}
        }}
        """
        response_str = await macro_research_agent.run(prompt)
        json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            return data
        else:
            return json.loads(response_str)
    except Exception as e:
        logger.error(f"Failed to generate impact: {e}")
        return {
            "title": headline,
            "severity": None,
            "ai_analysis": None,
            "chain_reaction": [],
            "stocks": {"beneficiaries": [], "pressure": []}
        }

@router.post("/picks")
async def get_picks(request: Request, body: PickRequest):
    """
    Returns AI Stock Picks array based on market.
    """
    import json
    import re
    from services.agents.stock_analysis import stock_analysis_agent
    from services.agents.pick_parsing import (
        parse_price_range,
        parse_single_price,
        validate_against_quote,
    )

    try:
        # Each candidate carries its market explicitly.
        if body.market.upper() == "US":
            candidates = [("AAPL", "US"), ("MSFT", "US")]
        else:
            candidates = [("RELIANCE.NS", "NSE"), ("HDFCBANK.NS", "NSE")]

        picks = []
        for ticker, market in candidates:
            prompt = f"Analyze ticker {ticker} and provide a trade setup. DO NOT call any tools to output the final result. Just return a raw JSON object with keys: verdict, entry_zone, target, stop_loss, confidence_score, reasoning."
            try:
                response_str = await stock_analysis_agent.run(prompt)
                json_match = re.search(r'\{.*\}', response_str, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    data = json.loads(response_str)

                verdict = str(data.get("verdict", "")).upper()
                if "LONG" in verdict or "BUY" in verdict:
                    side = "LONG"
                elif "SHORT" in verdict or "SELL" in verdict:
                    side = "SHORT"
                else:
                    logger.error(f"Discarding pick for {ticker}: unusable verdict {data.get('verdict')!r}")
                    continue

                entry_range = parse_price_range(data.get("entry_zone"))
                target = parse_single_price(data.get("target"))
                stop_loss = parse_single_price(data.get("stop_loss"))
                confidence_raw = parse_single_price(data.get("confidence_score"))

                if entry_range is None or target is None or stop_loss is None or confidence_raw is None:
                    logger.error(
                        f"Discarding pick for {ticker}: unparseable levels "
                        f"(entry_zone={data.get('entry_zone')!r}, target={data.get('target')!r}, "
                        f"stop_loss={data.get('stop_loss')!r}, confidence={data.get('confidence_score')!r})"
                    )
                    continue

                entry_low, entry_high = entry_range

                # Validate against the live quote. Same code path as everything else.
                quote = await market_data_service.get_quote(ticker, market)
                if quote.error or quote.price <= 0:
                    logger.error(f"Discarding pick for {ticker}: no live quote to validate against ({quote.error})")
                    continue

                rejection = validate_against_quote(
                    ticker, entry_low, entry_high, target, stop_loss, side, quote.price
                )
                if rejection:
                    logger.error(f"Rejecting model pick for {ticker}: {rejection}")
                    continue

                picks.append({
                    "ticker": ticker,
                    "market": market,
                    "side": side,
                    "entry_low": entry_low,
                    "entry_high": entry_high,
                    "target": target,
                    "stop_loss": stop_loss,
                    "confidence": min(max(confidence_raw / 100.0, 0.0), 1.0),
                    "reason": data.get("reasoning"),
                    "event": None
                })
            except Exception as e:
                logger.error(f"Failed to analyze {ticker}: {e}")

        return {"picks": picks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/symbols/search")
async def search_symbols(request: Request, q: str = ""):
    import httpx
    from core.config import settings
    query = q.lower()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://finnhub.io/api/v1/search",
                params={"q": query, "token": settings.FINNHUB_API_KEY}
            )
            if res.status_code == 200:
                results = res.json().get('result', [])
                # Finnhub search returns no exchange field. Market comes from the
                # registry or is null; it is never assumed to be US.
                symbols = [
                    {
                        "ticker": r.get('symbol'),
                        "name": r.get('description'),
                        "market": lookup_market(r.get('symbol')),
                        "type": r.get('type'),
                    }
                    for r in results[:10]
                ]
                return {"symbols": symbols}
    except Exception as e:
        logger.error(f"Search error: {e}")

    return {"symbols": []}

@router.get("/market_data/quote/{market}/{ticker}")
async def get_market_quote(request: Request, market: str, ticker: str):
    """
    Single quote for one symbol.

    Delegates to MarketDataService.get_quote, the same call /api/dashboard makes.
    There is deliberately no second quote code path here: no direct provider
    access, no separate caching.
    """
    market = market.upper()
    if market not in MARKETS:
        raise HTTPException(status_code=400, detail=f"Unsupported market {market!r}")

    quote = await market_data_service.get_quote(ticker, market)
    if quote.error:
        raise HTTPException(status_code=502, detail=quote.error)
    return quote


@router.get("/history")
async def get_history(request: Request, symbol: str, market: str, timeframe: str = "1d"):
    """
    Returns OHLCV history for lightweight-charts using yfinance.

    `market` is required and decides how the symbol maps to a yfinance ticker.
    The ticker string is never inspected to guess an exchange.
    """
    import yfinance as yf

    try:
        query_symbol = resolve_yf_symbol(symbol, market)
    except UnknownMarketError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        # Map timeframes to yfinance intervals/periods
        interval_map = {
            "1m": ("1m", "7d"),
            "5m": ("5m", "60d"),
            "15m": ("15m", "60d"),
            "1H": ("1h", "730d"),
            "1D": ("1d", "max"),
            "1W": ("1wk", "max")
        }
        interval, period = interval_map.get(timeframe.upper(), ("1d", "1y"))
        if timeframe.lower() == "1h":
            interval = "1h"

        ticker = yf.Ticker(query_symbol)
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            return {"data": []}

        # yfinance emits NaN rows for non-trading gaps. They are not candles, and
        # NaN is not JSON-serialisable, so drop them rather than shipping holes.
        df = df.dropna(subset=["Open", "High", "Low", "Close"])

        # Format for lightweight-charts: time (unix timestamp), open, high, low, close, value (volume)
        data = []
        for index, row in df.iterrows():
            volume = row["Volume"]
            data.append({
                "time": int(index.timestamp()),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "value": float(volume) if volume == volume else 0.0,  # NaN != NaN
            })

        return {"data": data}
    except Exception as e:
        logger.error(f"Error fetching history for {symbol} ({market}): {e}")
        raise HTTPException(status_code=502, detail=f"History unavailable for {symbol}")


@router.get("/details")
async def get_details(request: Request, symbol: str, market: str):
    import yfinance as yf

    try:
        query_symbol = resolve_yf_symbol(symbol, market)
    except UnknownMarketError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        info = yf.Ticker(query_symbol).info
        return {
            "open": info.get("regularMarketOpen", info.get("open", 0)),
            "dayHigh": info.get("dayHigh", 0),
            "dayLow": info.get("dayLow", 0),
            "volume": info.get("volume", 0),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh", 0),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow", 0),
            "marketCap": info.get("marketCap", 0),
            "peRatio": info.get("trailingPE", 0),
            "dividendYield": info.get("dividendYield", 0) * 100 if info.get("dividendYield") else 0,
            "sector": info.get("sector", "Unknown"),
            "longName": info.get("longName", symbol)
        }
    except Exception as e:
        logger.error(f"Error fetching details for {symbol} ({market}): {e}")
        raise HTTPException(status_code=502, detail=f"Details unavailable for {symbol}")

MOCK_USER_SESSION = "mock_session_user_1"
# Session-local fallback when Supabase is unreachable. Starts empty: it holds only
# what the user actually added during this process's lifetime.
IN_MEMORY_WATCHLIST = []

@router.get("/watchlist")
async def get_watchlist(request: Request):
    try:
        supabase = get_supabase()
        response = supabase.table("watchlist").select("*").eq("user_session_id", MOCK_USER_SESSION).execute()
        return {"watchlist": response.data}
    except Exception as e:
        return {"watchlist": IN_MEMORY_WATCHLIST}

@router.post("/watchlist")
async def add_to_watchlist(request: Request, item: dict):
    try:
        supabase = get_supabase()
        data = {"ticker": item["ticker"], "market": item.get("market", "UNKNOWN"), "user_session_id": MOCK_USER_SESSION}
        supabase.table("watchlist").insert(data).execute()
        return {"status": "added"}
    except Exception:
        # Check if exists
        if not any(w["ticker"] == item["ticker"] for w in IN_MEMORY_WATCHLIST):
            IN_MEMORY_WATCHLIST.append({"ticker": item["ticker"], "market": item.get("market", "UNKNOWN")})
        return {"status": "added_mock"}

@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(request: Request, ticker: str):
    try:
        supabase = get_supabase()
        supabase.table("watchlist").delete().eq("user_session_id", MOCK_USER_SESSION).eq("ticker", ticker).execute()
        return {"status": "removed"}
    except Exception:
        global IN_MEMORY_WATCHLIST
        IN_MEMORY_WATCHLIST = [w for w in IN_MEMORY_WATCHLIST if w["ticker"] != ticker]
        return {"status": "removed_mock"}

@router.get("/alerts")
async def get_alerts(request: Request):
    return {"alerts": []}
