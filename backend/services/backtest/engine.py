"""Backtesting engine: strategies evaluated on closed candles only.

Lookahead discipline (the audit flagged the exact failure modes, so they are
handled here, not documented away):
- The still-forming candle is dropped before any signal is computed. A
  strategy evaluated on today's partial bar reads a high/low/close that has
  not finished happening.
- Signals execute at the NEXT bar's close, never the same bar. Same-bar
  execution assumes you traded at a price before the signal existed.
- A flat 0.1% cost per side is charged on every fill. Zero-cost backtests
  are fantasy accounting.
"""

import logging
import math
from datetime import datetime, timezone

import yfinance as yf

from services.market_data.symbols import resolve_yf_symbol

logger = logging.getLogger(__name__)

COST_PER_SIDE = 0.001

# Bar length in seconds per yfinance interval, for forming-candle detection.
INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1d": 86400,
    "1wk": 7 * 86400,
}


def fetch_closed_bars(query_symbol: str, interval: str = "1d", period: str = "5y") -> list[dict]:
    df = yf.Ticker(query_symbol).history(period=period, interval=interval)
    if df.empty:
        return []
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    bars = [
        {
            "time": int(idx.timestamp()),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
        }
        for idx, row in df.iterrows()
    ]
    # Drop the still-forming candle: its bar period has not elapsed yet.
    bar_len = INTERVAL_SECONDS.get(interval, 86400)
    now = datetime.now(timezone.utc).timestamp()
    if bars and now - bars[-1]["time"] < bar_len:
        bars = bars[:-1]
    return bars


def moving_average(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    acc = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= window:
            acc -= values[i - window]
        if i >= window - 1:
            out[i] = acc / window
    return out


def run_backtest(
    ticker: str,
    market: str,
    strategy: str = "ma_cross",
    fast: int = 20,
    slow: int = 50,
) -> dict:
    query_symbol = resolve_yf_symbol(ticker, market)
    bars = fetch_closed_bars(query_symbol)
    if len(bars) < slow + 2:
        raise ValueError(f"Not enough history for {ticker} ({len(bars)} closed bars)")

    closes = [b["close"] for b in bars]
    times = [b["time"] for b in bars]

    if strategy == "buy_hold":
        position = [1] * len(bars)
    else:  # ma_cross
        fast_ma = moving_average(closes, fast)
        slow_ma = moving_average(closes, slow)
        position = [
            1 if (f is not None and s is not None and f > s) else 0
            for f, s in zip(fast_ma, slow_ma)
        ]

    equity = [1.0]
    position_now = 0
    entry_price = 0.0
    entry_time = 0
    trades: list[dict] = []

    # Signal at bar t executes at bar t+1's close: no lookahead.
    for t in range(1, len(bars)):
        target = position[t - 1]
        px = closes[t]
        ret = closes[t] / closes[t - 1]
        if target != position_now:
            # Pay cost on the flip, then earn/lose at the new position.
            equity.append(equity[-1] * (1 - COST_PER_SIDE))
            if position_now == 1:
                pnl = (px * (1 - COST_PER_SIDE) - entry_price) / entry_price
                trades.append(
                    {
                        "entry_time": entry_time,
                        "exit_time": times[t],
                        "side": "LONG",
                        "entry": round(entry_price, 2),
                        "exit": round(px, 2),
                        "pnl_pct": round(pnl * 100, 2),
                    }
                )
            if target == 1:
                entry_price = px
                entry_time = times[t]
            position_now = target
        equity.append(equity[-1] * (ret if position_now == 1 else 1.0))

    if position_now == 1:
        pnl = (closes[-1] - entry_price) / entry_price
        trades.append(
            {
                "entry_time": entry_time,
                "exit_time": times[-1],
                "side": "LONG (open)",
                "entry": round(entry_price, 2),
                "exit": round(closes[-1], 2),
                "pnl_pct": round(pnl * 100, 2),
            }
        )

    equity_curve = [{"time": t, "value": round(v, 4)} for t, v in zip(times, equity[1:])]

    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = max(max_dd, (peak - v) / peak)

    rets = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity)) if equity[i - 1]]
    sharpe = 0.0
    if len(rets) > 1:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        if var > 0:
            sharpe = round(mean / math.sqrt(var) * math.sqrt(252), 2)

    wins = sum(1 for t in trades if t["pnl_pct"] > 0)
    closed = [t for t in trades if "open" not in t["side"]]
    buy_hold_ret = round((closes[-1] / closes[0] - 1) * 100, 2)

    return {
        "ticker": ticker,
        "market": market,
        "strategy": strategy,
        "params": {"fast": fast, "slow": slow, "cost_per_side_pct": COST_PER_SIDE * 100},
        "bars_used": len(bars),
        "assumptions": "Closed candles only (forming bar dropped). Signals execute at next close. 0.1% cost per side. No slippage, fills at close.",
        "metrics": {
            "total_return_pct": round((equity[-1] - 1) * 100, 2),
            "buy_hold_return_pct": buy_hold_ret,
            "num_trades": len(closed),
            "win_rate_pct": round(wins / len(closed) * 100, 1) if closed else 0.0,
            "max_drawdown_pct": round(max_dd * 100, 2),
            "sharpe_daily_annualised": sharpe,
        },
        "equity_curve": equity_curve,
        "trades": trades[-50:],
    }
