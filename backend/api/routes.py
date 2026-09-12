import asyncio
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from services.market_data.service import market_data_service
from services.market_data.symbols import MARKETS, lookup_market, resolve_yf_symbol, UnknownMarketError
from services.agents.stock_analysis import stock_analysis_agent
from services.agents.portfolio_impact import portfolio_impact_agent
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

    def _sector_changes():
        # Blocking Yahoo calls: run off the event loop.
        xlk = yf.Ticker("XLK").history(period="5d")
        xlf = yf.Ticker("XLF").history(period="5d")
        it_change = ((xlk['Close'].iloc[-1] - xlk['Close'].iloc[0]) / xlk['Close'].iloc[0]) * 100
        bank_change = ((xlf['Close'].iloc[-1] - xlf['Close'].iloc[0]) / xlf['Close'].iloc[0]) * 100
        return [it_change, bank_change]

    try:
        it_change, bank_change = await asyncio.to_thread(_sector_changes)
        sector_momentum = [
            {"sector": "IT", "change": round(float(it_change), 2)},
            {"sector": "Banking", "change": round(float(bank_change), 2)}
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

@router.get("/global")
async def get_global(request: Request):
    """Global markets board: one live quote per region/asset.

    Every symbol here was verified against the quote path; tickers that
    cannot produce a quote (crude, FX pairs) are excluded rather than
    rendered as zeros.
    """
    import asyncio

    symbols = [
        ("^NSEI", "NSE"),
        ("^GSPC", "US"),
        ("^IXIC", "US"),
        ("^FTSE", "US"),
        ("^N225", "US"),
        ("BTC", "CRYPTO"),
        ("ETH", "CRYPTO"),
        ("Gold", "COMMODITY"),
    ]
    quotes = await asyncio.gather(
        *(market_data_service.get_quote(sym, mkt) for sym, mkt in symbols),
        return_exceptions=True,
    )
    return {
        "markets": [
            q.model_dump() for q in quotes if not isinstance(q, Exception) and not q.error
        ]
    }


@router.get("/events")
async def get_events(request: Request, page: int = 1, limit: int = 10):
    """
    Returns paginated, filterable macro event feed.

    Severity comes from the LLM classifier (services/events/classifier.py),
    not a keyword hack. Classification runs concurrently over the page;
    each headline falls back to Low inside the classifier on failure,
    so the feed degrades to labelled data rather than severity: None.
    """
    from services.events.pipeline import (
        classify_headlines,
        fetch_finnhub_news,
        to_event_dict,
    )
    try:
        news = await fetch_finnhub_news()
        if news:
            page_items = news[:limit]
            headlines = [n.get("headline", "") for n in page_items]
            classified = await classify_headlines(headlines)
            events = [
                to_event_dict(n, c, i)
                for i, (n, c) in enumerate(zip(page_items, classified))
            ]
            return {"events": events, "page": page, "total": len(news)}
    except Exception as e:
        logger.error(f"Events fetch failed: {e}")
    return {"events": [], "page": page, "total": 0}

@router.get("/events/{id}/impact")
async def get_event_impact(request: Request, id: str):
    """
    Returns full chain reaction + beneficiary/risk stocks.

    Primary path is the Review III pipeline
    (classifier -> context_assembler -> impact engine, adapted to the
    frontend shape). The legacy macro_research_agent prompt is the
    fallback so a pipeline failure still returns the DEMO READY shape.
    """
    import json
    import re
    from services.agents.macro_research import macro_research_agent
    from services.events.pipeline import analyze_event, fetch_finnhub_news

    headline = f"Market event {id}"
    try:
        news = await fetch_finnhub_news()
        for n in news:
            if str(n.get('id')) == id:
                headline = n.get('headline')
                break
    except:
        pass

    try:
        return await analyze_event(headline)
    except Exception as e:
        logger.error(f"Pipeline impact failed, falling back to agent prompt: {e}")
        
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

        # Grounding quotes first, concurrently: every candidate needs a live
        # price before the model is asked for levels (without this the model
        # priced AAPL at 140-150 while it traded at 328).
        live_quotes = await asyncio.gather(
            *(market_data_service.get_quote(ticker, market) for ticker, market in candidates)
        )
        grounded = []
        for (ticker, market), quote in zip(candidates, live_quotes):
            if isinstance(quote, Exception) or quote.error or quote.price <= 0:
                logger.error(f"Skipping {ticker}: no live quote to ground the prompt")
                continue
            grounded.append((ticker, market, quote))

        async def _analyse(ticker: str, market: str, quote) -> str:
            price = quote.price
            currency = quote.currency_symbol
            prompt = (
                f"Analyze {ticker} and provide a trade setup.\n\n"
                f"CURRENT LIVE PRICE: {currency}{price:.2f} ({quote.currency}). "
                f"This is the real, current market price as of now. Every level you "
                f"produce MUST be anchored to it.\n\n"
                f"Rules for the levels:\n"
                f"- entry_zone must be within 5% of {price:.2f}, i.e. between "
                f"{price * 0.95:.2f} and {price * 1.05:.2f}. Express it as a narrow "
                f"range like \"{price * 0.99:.2f}-{price * 1.01:.2f}\".\n"
                f"- For a LONG: stop_loss below the entry zone, target above it.\n"
                f"- For a SHORT: stop_loss above the entry zone, target below it.\n"
                f"- Keep target and stop_loss within 25% of {price:.2f}.\n"
                f"- Do not use prices from your training data. {ticker} trades at "
                f"{currency}{price:.2f} right now.\n\n"
                f"DO NOT call any tools to output the final result. Return a raw JSON "
                f"object with keys: verdict, entry_zone, target, stop_loss, "
                f"confidence_score, reasoning."
            )
            return await stock_analysis_agent.run(prompt)

        # Model calls run concurrently: sequential calls made the page take
        # 2x per candidate for no correctness benefit.
        responses = await asyncio.gather(
            *(_analyse(ticker, market, quote) for ticker, market, quote in grounded),
            return_exceptions=True,
        )

        picks = []
        for (ticker, market, quote), response_str in zip(grounded, responses):
            if isinstance(response_str, Exception):
                logger.error(f"Failed to analyze {ticker}: {response_str}")
                continue
            price = quote.price

            try:
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

                # Validate against the same live quote the prompt was grounded in.
                # Unchanged 20% band: grounding the prompt does not excuse the model
                # from producing levels that survive the check.
                rejection = validate_against_quote(
                    ticker, entry_low, entry_high, target, stop_loss, side, price
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


def _watchlist_db():
    """Supabase when reachable, else the local on-disk store.

    No in-memory fallback: both options are real persistence. A watchlist
    that silently lives in one process is indistinguishable from a
    persisted one until the process restarts.
    """
    from services.paper_trading.local_store import get_store

    return get_store()


@router.get("/watchlist")
async def get_watchlist(request: Request):
    supabase = _watchlist_db()
    session_id = request.headers.get("X-Session-Id", MOCK_USER_SESSION)
    try:
        response = (
            supabase.table("watchlist")
            .select("*")
            .eq("user_session_id", session_id)
            .execute()
        )
    except Exception as e:
        logger.error(f"Watchlist read failed: {e}")
        raise HTTPException(status_code=503, detail="Watchlist storage unavailable")

    return {"watchlist": response.data}


@router.post("/watchlist")
async def add_to_watchlist(request: Request, item: dict):
    ticker = item.get("ticker")
    market = item.get("market")
    if not ticker or not market:
        raise HTTPException(status_code=400, detail="ticker and market are both required")

    supabase = _watchlist_db()
    session_id = request.headers.get("X-Session-Id", MOCK_USER_SESSION)
    try:
        data = {"ticker": ticker, "market": market, "user_session_id": session_id}
        supabase.table("watchlist").insert(data).execute()
    except Exception as e:
        # Postgres 23505: the (user_session_id, ticker) unique constraint fired.
        # Adding a symbol already on the watchlist is a no-op, not a failure, and
        # certainly not a database outage.
        if "23505" in str(e) or "duplicate key" in str(e).lower():
            return {"status": "added"}
        logger.error(f"Watchlist insert failed: {e}")
        raise HTTPException(status_code=503, detail="Watchlist storage unavailable")

    return {"status": "added"}


@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(request: Request, ticker: str):
    supabase = _watchlist_db()
    session_id = request.headers.get("X-Session-Id", MOCK_USER_SESSION)
    try:
        (
            supabase.table("watchlist")
            .delete()
            .eq("user_session_id", session_id)
            .eq("ticker", ticker)
            .execute()
        )
    except Exception as e:
        logger.error(f"Watchlist delete failed: {e}")
        raise HTTPException(status_code=503, detail="Watchlist storage unavailable")

    return {"status": "removed"}

def _session_id(request: Request) -> str:
    """Per-user identity without breaking existing clients.

    Authenticated frontend sends X-Session-Id (Supabase user id).
    Anything that does not send it keeps the legacy mock identity,
    so watchlist/paper data remains reachable pre- and post-auth.
    """
    return request.headers.get("X-Session-Id", MOCK_USER_SESSION)


@router.get("/alerts")
async def get_alerts(request: Request):
    """Live alerts: circuit-breaker flags + recent anomaly agent decisions."""
    from services.realtime.anomaly import anomaly_watcher

    alerts = [{"type": "circuit_breaker", "message": f} for f in anomaly_watcher.active_flags]
    for d in reversed(anomaly_watcher.recent_decisions[-10:]):
        alerts.append({"type": "anomaly", **d})
    return {"alerts": alerts}


@router.get("/portfolio/impact")
async def get_portfolio_impact(request: Request):
    """Wire the portfolio_impact_agent to real holdings + real events.

    Holdings come from the user's open paper trades; events come from
    the live Finnhub feed. The agent reasons over both via real tools
    (no canned strings) and the raw decision is returned.
    """
    from services.agents.portfolio_impact import portfolio_impact_agent

    session_id = _session_id(request)
    prompt = (
        f"Assess portfolio impact for user {session_id}. "
        "Use get_user_holdings for their positions and "
        "get_active_macro_events for the current macro backdrop, then "
        "return position-specific impact assessments as JSON."
    )
    try:
        decision = await portfolio_impact_agent.run(prompt)
        return {"user_session_id": session_id, "impact": decision}
    except Exception as e:
        logger.error(f"Portfolio impact failed: {e}")
        raise HTTPException(status_code=502, detail="Impact analysis unavailable")
