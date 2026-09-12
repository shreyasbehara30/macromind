"""Review III pipeline: classifier -> context_assembler -> impact engine.

This is the wiring that was missing. Three previously dead modules are
connected here in dependency order:

1. classifier populates severity (unblocks everything downstream).
2. context_assembler filters to High/Medium and builds the <live_data> block.
3. impact engine maps to structured impact, adapted to the frontend shape.

The frontend shape (api.ts EventImpactResponse) is:
  chain_reaction: string[]
  stocks: { beneficiaries: [{ticker, reason}], pressure: [{ticker, reason}] }
The engine shape (impact.py EventImpact) is:
  chain_reaction: [{step, description}]
  stocks: [{ticker, name, market, impact, reasoning}] (flat, impact discriminator)
The adapter bridges that gap so neither side has to change.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from core.config import settings
from services.agents.context_assembler import context_assembler
from services.events.classifier import event_classifier, ClassifiedEvent
from services.events.impact import impact_mapping_engine
from services.market_data.service import market_data_service

logger = logging.getLogger(__name__)

# Tickers whose live prices ground the impact prompt. Same set the
# dashboard already serves, so no new provider path is introduced.
CONTEXT_TICKERS = [
    ("^NSEI", "NSE"),
    ("BTC", "CRYPTO"),
    ("^GSPC", "US"),
]


async def fetch_finnhub_news() -> list[dict]:
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": settings.FINNHUB_API_KEY},
            )
            if res.status_code == 200:
                return res.json()
            logger.error(f"Finnhub news returned {res.status_code}")
    except Exception as e:
        logger.error(f"Finnhub news fetch failed: {e}")
    return []


async def fetch_prices_context() -> dict[str, Any]:
    """Best-effort live prices for the impact prompt. Never raises."""

    async def one(symbol: str, market: str) -> tuple[str, Optional[float]]:
        try:
            quote = await market_data_service.get_quote(symbol, market)
            if quote.error or quote.price <= 0:
                return symbol, None
            return symbol, quote.price
        except Exception:
            return symbol, None

    results = await asyncio.gather(
        *(one(sym, mkt) for sym, mkt in CONTEXT_TICKERS),
        return_exceptions=True,
    )
    prices: dict[str, Any] = {}
    for item in results:
        if isinstance(item, Exception):
            continue
        symbol, price = item
        if price is not None:
            prices[symbol] = price
    return prices


VALID_MARKETS = {"NSE", "BSE", "US", "CRYPTO", "COMMODITY", "FOREX"}


def _stock_market(raw: Optional[str], ticker: str) -> Optional[str]:
    """Engine market if it names a real market, else the registry, else None.

    Never guessed from the ticker string: an unknown market stays null and
    the UI renders the ticker without a link rather than a wrong link.
    """
    if raw and raw.upper() in VALID_MARKETS:
        return raw.upper()
    try:
        from services.market_data.symbols import lookup_market

        return lookup_market(ticker)
    except Exception:
        return None


def adapt_impact_to_frontend(title: str, severity: Optional[str], event_impact) -> dict:
    """Convert engine output (EventImpact) to the shape events UI consumes."""
    chain = [
        f"{node.step}: {node.description}" if node.step else node.description
        for node in (event_impact.chain_reaction or [])
    ]
    beneficiaries = [
        {"ticker": s.ticker, "reason": s.reasoning, "market": _stock_market(s.market, s.ticker)}
        for s in (event_impact.stocks or [])
        if (s.impact or "").lower().startswith("benefic")
    ]
    pressure = [
        {"ticker": s.ticker, "reason": s.reasoning, "market": _stock_market(s.market, s.ticker)}
        for s in (event_impact.stocks or [])
        if not (s.impact or "").lower().startswith("benefic")
    ]
    return {
        "title": title,
        "severity": severity,
        "ai_analysis": None,
        "chain_reaction": chain,
        "stocks": {"beneficiaries": beneficiaries, "pressure": pressure},
    }


async def classify_headlines(headlines: list[str]) -> list[ClassifiedEvent]:
    """Classify concurrently; the classifier itself falls back to Low on failure."""
    results = await asyncio.gather(
        *(event_classifier.classify_headline(h) for h in headlines),
        return_exceptions=True,
    )
    classified: list[ClassifiedEvent] = []
    for headline, result in zip(headlines, results):
        if isinstance(result, Exception):
            logger.error(f"Classifier raised for {headline!r}: {result}")
            result = await event_classifier.classify_headline(headline)
        classified.append(result)
    return classified


def to_event_dict(
    raw: dict,
    classified: Optional[ClassifiedEvent],
    index: int,
) -> dict:
    published = raw.get("datetime")
    return {
        "id": str(raw.get("id", index)),
        "severity": classified.severity if classified else None,
        "headline": raw.get("headline"),
        "source": raw.get("source"),
        "timestamp": (
            datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
            if published
            else None
        ),
        "sectors": classified.affected_sectors if classified else [],
        "event_type": classified.event_type if classified else None,
        "summary": classified.summary if classified else None,
    }


async def analyze_event(headline: str) -> dict:
    """Full chain for GET /api/events/{id}/impact.

    1. Classify the headline (severity + sectors).
    2. Assemble RAG context (ranked events + live prices).
    3. Map impact via the engine, adapted to the frontend shape.
    Raises on total failure so the route can fall back to the legacy
    macro_research_agent prompt, which is the current DEMO READY path.
    """
    classified = await event_classifier.classify_headline(headline)
    prices = await fetch_prices_context()
    ranked = context_assembler.retrieve_and_rank(
        [
            {
                "headline": headline,
                "severity": classified.severity,
                "sectors": classified.affected_sectors,
            }
        ],
        prices,
    )
    context_block = context_assembler.augment(ranked)
    engine_out = await impact_mapping_engine.map_impact(
        classified,
        {"prices": prices, "context": context_block},
    )
    adapted = adapt_impact_to_frontend(headline, classified.severity, engine_out)
    adapted["ai_analysis"] = classified.summary
    return adapted
