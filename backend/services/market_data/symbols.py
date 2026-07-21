"""Symbol registry and market-driven ticker resolution.

Two rules hold everywhere in this module:

1. A symbol's market is looked up, never inferred from the shape of the ticker
   string. "AAPL has no dot so it must be NSE" is the bug this module exists to
   prevent.
2. Converting a symbol to a yfinance ticker is driven by the market argument
   alone. The same symbol under a different market resolves differently.

The registry is deliberately small and explicit. It covers the symbols this
application actually references. An unlisted symbol resolves to market None --
that is a real answer meaning "we do not know", and callers must handle it
rather than guessing.
"""

from typing import Dict, Optional

Market = str  # one of MARKETS below

MARKETS = ("NSE", "BSE", "US", "CRYPTO", "COMMODITY", "FOREX")

# symbol -> market. The single source of truth for which venue a symbol trades on.
SYMBOL_MARKETS: Dict[str, Market] = {
    # Indices
    "^NSEI": "NSE",
    "^GSPC": "US",
    "^VIX": "US",
    # NSE equities
    "RELIANCE.NS": "NSE",
    "TCS.NS": "NSE",
    "HDFCBANK.NS": "NSE",
    "INFY.NS": "NSE",
    # US equities
    "AAPL": "US",
    "MSFT": "US",
    "NVDA": "US",
    "TSLA": "US",
    # Crypto
    "BTC": "CRYPTO",
    "ETH": "CRYPTO",
    # Commodities
    "Gold": "COMMODITY",
    "Crude Oil": "COMMODITY",
    # Forex
    "USD/INR": "FOREX",
}

# Explicit yfinance tickers for symbols whose venue ticker is not derivable.
_CRYPTO_YF: Dict[str, str] = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
}

_COMMODITY_YF: Dict[str, str] = {
    "Gold": "GC=F",
    "Crude Oil": "CL=F",
}

_FOREX_YF: Dict[str, str] = {
    "USD/INR": "INR=X",
}


class UnknownMarketError(ValueError):
    """Raised when a symbol cannot be resolved for the market it was given."""


def lookup_market(symbol: str) -> Optional[Market]:
    """Return the registered market for a symbol, or None if unlisted.

    None means unknown. It does not mean US, and it must not be defaulted.
    """
    return SYMBOL_MARKETS.get(symbol)


def resolve_yf_symbol(symbol: str, market: Market) -> str:
    """Map (symbol, market) to a yfinance ticker.

    The market argument decides the mapping. The ticker string is never
    inspected to decide which market it belongs to; it is only checked for an
    already-correct suffix so we do not double-append one.
    """
    if not market:
        raise UnknownMarketError(f"No market supplied for symbol {symbol!r}")

    market = market.upper()

    if market == "US":
        # Indices (^GSPC) and equities (AAPL) are already yfinance tickers.
        return symbol

    if market == "NSE":
        return symbol if symbol.endswith(".NS") or symbol.startswith("^") else f"{symbol}.NS"

    if market == "BSE":
        return symbol if symbol.endswith(".BO") else f"{symbol}.BO"

    if market == "CRYPTO":
        if symbol in _CRYPTO_YF:
            return _CRYPTO_YF[symbol]
        return symbol if symbol.endswith("-USD") else f"{symbol}-USD"

    if market == "COMMODITY":
        if symbol in _COMMODITY_YF:
            return _COMMODITY_YF[symbol]
        raise UnknownMarketError(f"No commodity mapping for symbol {symbol!r}")

    if market == "FOREX":
        if symbol in _FOREX_YF:
            return _FOREX_YF[symbol]
        raise UnknownMarketError(f"No forex mapping for symbol {symbol!r}")

    raise UnknownMarketError(f"Unsupported market {market!r} for symbol {symbol!r}")
