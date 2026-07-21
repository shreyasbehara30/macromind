"""Defect 6: ranged entry zones parse, and hallucinated levels are rejected."""

import pytest

from services.agents.pick_parsing import (
    MAX_ENTRY_DEVIATION,
    parse_price_range,
    parse_single_price,
    validate_against_quote,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("140-150", (140.0, 150.0)),
        ("140 - 150", (140.0, 150.0)),
        ("$140-$150", (140.0, 150.0)),
        ("140–150", (140.0, 150.0)),   # en dash
        ("140—150", (140.0, 150.0)),   # em dash
        ("150-140", (140.0, 150.0)),   # reversed input is ordered
        ("1,400-1,500", (1400.0, 1500.0)),
        ("140", (140.0, 140.0)),
        ("140.55", (140.55, 140.55)),
        (327.49, (327.49, 327.49)),
        ("₹1,303.70", (1303.70, 1303.70)),
    ],
)
def test_parse_price_range(raw, expected):
    assert parse_price_range(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "  ", "N/A", "unknown", "TBD", 0, -5])
def test_unparseable_returns_none(raw):
    assert parse_price_range(raw) is None


def test_parse_single_price_collapses_range_to_midpoint():
    assert parse_single_price("140-150") == 145.0
    assert parse_single_price("170") == 170.0


def test_the_exact_reported_case_is_rejected():
    """AAPL entry 140-150 against a 327.49 quote must never reach the UI."""
    reason = validate_against_quote(
        "AAPL", 140.0, 150.0, target=170.0, stop_loss=130.0, side="LONG", quote_price=327.49
    )
    assert reason is not None
    assert "live price" in reason


def test_plausible_levels_pass():
    reason = validate_against_quote(
        "AAPL", 320.0, 325.0, target=350.0, stop_loss=310.0, side="LONG", quote_price=327.49
    )
    assert reason is None


def test_deviation_boundary():
    price = 100.0
    just_inside = price * (1 + MAX_ENTRY_DEVIATION - 0.01)
    just_outside = price * (1 + MAX_ENTRY_DEVIATION + 0.01)

    assert validate_against_quote(
        "X", just_inside, just_inside, target=just_inside * 1.1,
        stop_loss=just_inside * 0.9, side="LONG", quote_price=price
    ) is None

    assert validate_against_quote(
        "X", just_outside, just_outside, target=just_outside * 1.1,
        stop_loss=just_outside * 0.9, side="LONG", quote_price=price
    ) is not None


def test_incoherent_long_is_rejected():
    """Stop above entry on a long is not a trade."""
    reason = validate_against_quote(
        "AAPL", 100.0, 100.0, target=90.0, stop_loss=110.0, side="LONG", quote_price=100.0
    )
    assert reason is not None
    assert "incoherent" in reason


def test_incoherent_short_is_rejected():
    reason = validate_against_quote(
        "AAPL", 100.0, 100.0, target=110.0, stop_loss=90.0, side="SHORT", quote_price=100.0
    )
    assert reason is not None
    assert "incoherent" in reason


def test_valid_short_passes():
    reason = validate_against_quote(
        "AAPL", 100.0, 100.0, target=90.0, stop_loss=110.0, side="SHORT", quote_price=100.0
    )
    assert reason is None


def test_missing_quote_is_rejected():
    reason = validate_against_quote(
        "AAPL", 100.0, 100.0, target=110.0, stop_loss=90.0, side="LONG", quote_price=0.0
    )
    assert reason is not None
