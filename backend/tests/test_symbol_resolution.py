"""Defect 1: market drives symbol resolution, ticker shape never does."""

import pytest

from services.market_data.symbols import (
    UnknownMarketError,
    lookup_market,
    resolve_yf_symbol,
)


def test_aapl_resolves_to_us():
    assert lookup_market("AAPL") == "US"
    assert resolve_yf_symbol("AAPL", "US") == "AAPL"


def test_reliance_resolves_to_nse():
    assert lookup_market("RELIANCE.NS") == "NSE"
    assert resolve_yf_symbol("RELIANCE", "NSE") == "RELIANCE.NS"
    # Already-suffixed input is not double-suffixed.
    assert resolve_yf_symbol("RELIANCE.NS", "NSE") == "RELIANCE.NS"


def test_resolution_depends_on_market_not_string_shape():
    """The regression that started this: a dotless ticker is not automatically NSE.

    The same string resolves differently purely because the market differs, which
    is only possible if the market argument is what drives the mapping.
    """
    assert resolve_yf_symbol("AAPL", "US") == "AAPL"
    assert resolve_yf_symbol("AAPL", "NSE") == "AAPL.NS"

    # And a dotted ticker is not automatically non-US.
    assert resolve_yf_symbol("BRK.B", "US") == "BRK.B"


def test_no_market_is_an_error_not_a_guess():
    with pytest.raises(UnknownMarketError):
        resolve_yf_symbol("AAPL", "")
    with pytest.raises(UnknownMarketError):
        resolve_yf_symbol("AAPL", None)


def test_unlisted_symbol_has_no_market():
    """Unknown means unknown. It must not default to US."""
    assert lookup_market("RWC.AX") is None
    assert lookup_market("NOT_A_REAL_TICKER") is None


@pytest.mark.parametrize(
    "symbol,market,expected",
    [
        ("BTC", "CRYPTO", "BTC-USD"),
        ("ETH", "CRYPTO", "ETH-USD"),
        ("Gold", "COMMODITY", "GC=F"),
        ("Crude Oil", "COMMODITY", "CL=F"),
        ("USD/INR", "FOREX", "INR=X"),
        ("^NSEI", "NSE", "^NSEI"),
        ("^GSPC", "US", "^GSPC"),
        ("TCS", "BSE", "TCS.BO"),
    ],
)
def test_known_mappings(symbol, market, expected):
    assert resolve_yf_symbol(symbol, market) == expected


def test_unmappable_commodity_raises():
    with pytest.raises(UnknownMarketError):
        resolve_yf_symbol("Palladium", "COMMODITY")
