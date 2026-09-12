"""Backtest + Monte Carlo + projection + depth routes.

All four are computed from real market history/quotes at request time.
Nothing here is a trained forecasting model; the projection and Monte Carlo
outputs are statistical extrapolations and are labelled as such in every
response and on every pixel that renders them.
"""

import logging
import math
import random
from datetime import datetime, timezone

import yfinance as yf
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from services.backtest.engine import fetch_closed_bars, run_backtest
from services.market_data.symbols import MARKETS, resolve_yf_symbol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["Backtesting"])


class BacktestRequest(BaseModel):
    ticker: str
    market: str
    strategy: str = "ma_cross"
    fast: int = 20
    slow: int = 50


class MonteCarloRequest(BaseModel):
    ticker: str
    market: str
    days: int = 30
    paths: int = 200


@router.post("")
async def post_backtest(request: Request, body: BacktestRequest):
    market = body.market.upper()
    if market not in MARKETS:
        raise HTTPException(status_code=400, detail=f"Unsupported market {body.market!r}")
    if body.strategy not in ("ma_cross", "buy_hold"):
        raise HTTPException(status_code=400, detail="strategy must be ma_cross or buy_hold")
    if not (2 <= body.fast < body.slow <= 200):
        raise HTTPException(status_code=400, detail="require 2 <= fast < slow <= 200")
    try:
        return run_backtest(body.ticker, market, body.strategy, body.fast, body.slow)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest failed for {body.ticker}: {e}")
        raise HTTPException(status_code=502, detail="Backtest unavailable")


@router.post("/montecarlo")
async def post_montecarlo(request: Request, body: MonteCarloRequest):
    """Geometric-Brownian-motion fan chart from historical drift/volatility.

    A simulation of what COULD happen given past volatility, not a prediction
    of what will. Paths use daily log-return mean/std of the last year of
    closed candles.
    """
    market = body.market.upper()
    if market not in MARKETS:
        raise HTTPException(status_code=400, detail=f"Unsupported market {body.market!r}")
    days = max(5, min(body.days, 90))
    paths = max(20, min(body.paths, 500))
    try:
        query_symbol = resolve_yf_symbol(body.ticker, market)
        bars = fetch_closed_bars(query_symbol, period="1y")
        if len(bars) < 60:
            raise ValueError(f"Not enough history for {body.ticker}")
        closes = [b["close"] for b in bars]
        logrets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        mu = sum(logrets) / len(logrets)
        var = sum((r - mu) ** 2 for r in logrets) / (len(logrets) - 1)
        sigma = math.sqrt(var)
        last = closes[-1]
        last_time = bars[-1]["time"]
        rng = random.Random(42)  # deterministic seed: same input, same fan
        fan = []
        for _ in range(paths):
            px, path = last, []
            for d in range(1, days + 1):
                px *= math.exp(mu + sigma * rng.gauss(0, 1))
                path.append(round(px, 2))
            fan.append(path)
        finals = sorted(p[-1] for p in fan)

        def pct(q: float) -> float:
            return finals[min(paths - 1, int(q * paths))]

        return {
            "ticker": body.ticker,
            "market": market,
            "last_close": last,
            "last_time": last_time,
            "days": days,
            "paths": paths,
            "daily_vol_pct": round(sigma * 100, 2),
            "median_path": [sorted(fan[i][d] for i in range(paths))[paths // 2] for d in range(days)],
            "p10_path": [sorted(fan[i][d] for i in range(paths))[paths // 10] for d in range(days)],
            "p90_path": [sorted(fan[i][d] for i in range(paths))[(paths * 9) // 10] for d in range(days)],
            "projected_median_pct": round((pct(0.5) / last - 1) * 100, 2),
            "projected_p10_pct": round((pct(0.1) / last - 1) * 100, 2),
            "projected_p90_pct": round((pct(0.9) / last - 1) * 100, 2),
            "disclaimer": "Simulation from historical volatility, not a prediction. Same seed returns the same fan.",
        }
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Monte Carlo failed for {body.ticker}: {e}")
        raise HTTPException(status_code=502, detail="Simulation unavailable")


@router.get("/projection")
async def get_projection(request: Request, symbol: str, market: str, days: int = 30):
    """Statistical baseline projection: 20-day trend extended, ±1σ bands.

    Explicitly not a trained model. Trend = slope of the 20-day moving
    average; bands = one daily standard deviation scaled by sqrt(t).
    """
    mkt = market.upper()
    if mkt not in MARKETS:
        raise HTTPException(status_code=400, detail=f"Unsupported market {market!r}")
    days = max(5, min(days, 90))
    try:
        query_symbol = resolve_yf_symbol(symbol, mkt)
        bars = fetch_closed_bars(query_symbol, period="1y")
        if len(bars) < 60:
            raise ValueError(f"Not enough history for {symbol}")
        closes = [b["close"] for b in bars]
        window = closes[-20:]
        n = len(window)
        mean_x = (n - 1) / 2
        mean_y = sum(window) / n
        slope = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(window)) / sum(
            (i - mean_x) ** 2 for i in range(n)
        )
        logrets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        mu = sum(logrets) / len(logrets)
        sigma = math.sqrt(sum((r - mu) ** 2 for r in logrets) / (len(logrets) - 1))
        last = closes[-1]
        last_time = bars[-1]["time"]
        proj, upper, lower = [], [], []
        for d in range(1, days + 1):
            mid = last + slope * d
            band = last * sigma * math.sqrt(d)
            proj.append(round(mid, 2))
            upper.append(round(mid + band, 2))
            lower.append(round(max(mid - band, 0), 2))
        day = 86400
        return {
            "symbol": symbol,
            "market": mkt,
            "last_close": last,
            "times": [last_time + d * day for d in range(1, days + 1)],
            "projection": proj,
            "upper": upper,
            "lower": lower,
            "method": "20-day trend slope with 1-sigma volatility bands",
            "disclaimer": "Statistical baseline, not a trained forecasting model.",
        }
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Projection failed for {symbol}: {e}")
        raise HTTPException(status_code=502, detail="Projection unavailable")


@router.get("/depth")
async def get_depth(request: Request, symbol: str, market: str):
    """Top-of-book only: live bid/ask + sizes where the quote feed carries them.

    No full L2 ladder exists in this stack's free data feeds, so this endpoint
    does not invent one. `ladder_levels` is explicitly False when only the
    best bid/ask is known.
    """
    mkt = market.upper()
    if mkt not in MARKETS:
        raise HTTPException(status_code=400, detail=f"Unsupported market {market!r}")
    try:
        query_symbol = resolve_yf_symbol(symbol, mkt)
        info = yf.Ticker(query_symbol).info
        bid = info.get("bid")
        ask = info.get("ask")
        if not bid or not ask:
            raise ValueError(f"No top-of-book for {symbol}")
        bid_size = info.get("bidSize") or 0
        ask_size = info.get("askSize") or 0
        mid = (bid + ask) / 2
        return {
            "symbol": symbol,
            "market": mkt,
            "bid": bid,
            "ask": ask,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "spread": round(ask - bid, 4),
            "spread_bps": round((ask - bid) / mid * 10000, 1),
            "mid": round(mid, 2),
            "ladder_levels": False,
            "disclaimer": "Best bid/ask only. No full order-book ladder in this data feed.",
        }
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Depth failed for {symbol}: {e}")
        raise HTTPException(status_code=502, detail="Depth unavailable")
